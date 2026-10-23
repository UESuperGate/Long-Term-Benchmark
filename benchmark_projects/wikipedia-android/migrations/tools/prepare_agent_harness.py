#!/usr/bin/env python3
"""Inject evaluator-owned runtime wiring after the candidate agent has exited."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


FORBIDDEN_NAMES = {"transitions.json", "transitions.draft.json", "observer_rules.json", "task.json", "evidence.json"}


def hash_record(root: Path, path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path.relative_to(root)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def audit_candidate(project: Path) -> None:
    for path in project.rglob("*"):
        if any(part in {".benchmark-evaluator", "build", ".hvigor", ".gradle"} for part in path.parts):
            continue
        if path.is_file() and path.name in FORBIDDEN_NAMES:
            raise RuntimeError(f"agent candidate contains evaluator oracle material: {path}")


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build", ".gradle", ".hvigor"))


def _block(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"candidate build is missing {marker}")
    opening = text.find("{", start + len(marker))
    if opening < 0:
        raise RuntimeError(f"candidate build has malformed {marker}")
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1:index]
    raise RuntimeError(f"candidate build has unterminated {marker}")


def candidate_production_roots(project: Path) -> list[Path]:
    app = (project / "app").resolve()
    build = (app / "build.gradle.kts").read_text(encoding="utf-8")
    main = _block(build, 'getByName("main")')
    calls = re.findall(r"kotlin\.srcDirs\((.*?)\)", main, flags=re.DOTALL)
    if not calls:
        raise RuntimeError("candidate main source set has no Kotlin source roots")
    values = [value for call in calls for value in re.findall(r'"([^"]+)"', call)]
    roots: list[Path] = []
    for value in values:
        root = (app / value).resolve()
        if root != app and app not in root.parents:
            raise RuntimeError(f"candidate source root escapes app directory: {value}")
        relative = root.relative_to(app)
        if any(part in {"leaf", "evaluator", ".benchmark-evaluator", "androidTest", "test"} for part in relative.parts):
            continue
        if root.is_dir() and root not in roots:
            roots.append(root)
    if not roots:
        raise RuntimeError("candidate main source set has no production Kotlin roots")
    return roots


def copy_candidate_production(project: Path, target: Path) -> None:
    for index, source in enumerate(candidate_production_roots(project)):
        root_target = target / f"root-{index}"
        for path in source.rglob("*"):
            if not path.is_file() or path.suffix not in {".kt", ".java"}:
                continue
            relative = path.relative_to(source)
            destination = root_target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def prepare_android(task_id: str, project: Path, migration: Path, hidden: Path) -> list[Path]:
    harness = hidden / "android-harness"
    template = migration / "android/native/base"
    harness.mkdir(parents=True)
    (harness / "app/src/main").mkdir(parents=True)
    for name in ("settings.gradle.kts", "build.gradle.kts", "build.sh", "local.properties"):
        shutil.copy2(template / name, harness / name)
    shutil.copy2(template / "app/src/main/AndroidManifest.xml", harness / "app/src/main/AndroidManifest.xml")
    evaluator_main = harness / "evaluator-main"
    evaluator_test = harness / "evaluator-test"
    candidate_sources = harness / "candidate-production"
    copy_candidate_production(project, candidate_sources)
    if task_id == "01_reading_challenge":
        copy_tree(migration / "android/shared/native_leaf/kotlin", evaluator_main)
        runner = "org.wikipedia.benchmark.reading.native.NativeReadingInstrumentation"
        namespace = "org.wikipedia.benchmark.reading.agent"
        exclude = ""
    elif task_id == "02_hybrid_search":
        selected = [
            "androidx/lifecycle", "androidx/paging", "kotlinx/serialization", "org/wikipedia/dataclient",
            "org/wikipedia/search", "retrofit2/http"
        ]
        for relative in selected:
            copy_tree(migration / "android/shared/leaf/kotlin" / relative, evaluator_main / relative)
        copy_tree(migration / "android/shared/native_leaf/kotlin", evaluator_main)
        runner = "org.wikipedia.benchmark.hybrid.native.NativeHybridInstrumentation"
        namespace = "org.wikipedia.benchmark.hybrid.agent"
        exclude = ""
    elif task_id == "03_explore_feed":
        runner = "org.wikipedia.benchmark.explore.native.NativeExploreInstrumentation"
        namespace = "org.wikipedia.benchmark.explore.agent"
        exclude = ""
    else:
        runner = "org.wikipedia.benchmark.saved.native.NativeSavedInstrumentation"
        namespace = "org.wikipedia.benchmark.saved.agent"
        exclude = ""
    copy_tree(migration / "android/shared/native_test/kotlin", evaluator_test)
    candidate_literal = json.dumps(str(candidate_sources))
    main_literal = json.dumps(str(evaluator_main))
    test_literal = json.dumps(str(evaluator_test))
    build = f'''plugins {{ id("com.android.application"); kotlin("android") }}

android {{
    namespace = "{namespace}"
    compileSdk = 37
    defaultConfig {{
        applicationId = "{namespace}"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "{runner}"
    }}
    sourceSets {{
        getByName("main") {{
            manifest.srcFile("src/main/AndroidManifest.xml")
            kotlin.srcDirs({candidate_literal}, {main_literal})
{exclude}        }}
        getByName("androidTest") {{ kotlin.srcDirs({test_literal}) }}
    }}
    compileOptions {{ sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }}
    kotlinOptions {{ jvmTarget = "17" }}
}}

dependencies {{ implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.1") }}
'''
    (harness / "app/build.gradle.kts").write_text(build)
    return [path for path in harness.rglob("*") if path.is_file()]


def method_span(source: str, name: str) -> tuple[re.Match[str], int, int] | None:
    pattern = re.compile(
        rf"(?m)^(?P<indent>[ \t]*)(?P<async>async[ \t]+)?{re.escape(name)}"
        rf"[ \t]*\([^)]*\)[ \t]*(?::[^{{\n]+)?[ \t]*\{{"
    )
    match = pattern.search(source)
    if match is None:
        return None
    opening = source.find("{", match.start(), match.end())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return match, opening, index
    raise RuntimeError(f"ArkTS runtime binding found unterminated method: {name}")


def indent_block(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line.strip() else line for line in value.splitlines())


def wrap_about_to_appear(source: str, launch: str, case_body: str) -> str:
    span = method_span(source, "aboutToAppear")
    if span is None:
        marker = "struct Index {"
        if marker not in source:
            raise RuntimeError("ArkTS page-owner integration requires struct Index")
        source = source.replace(marker, marker + "\n\n  async aboutToAppear(): Promise<void> {\n  }", 1)
        span = method_span(source, "aboutToAppear")
    if span is None:
        raise RuntimeError("ArkTS page-owner integration cannot create aboutToAppear")
    match, opening, closing = span
    if match.group("async") is None:
        signature = f"{match.group('indent')}async aboutToAppear(): Promise<void> "
        source = source[:match.start()] + signature + source[opening:]
        match, opening, closing = method_span(source, "aboutToAppear") or (None, -1, -1)
        if match is None:
            raise RuntimeError("ArkTS page-owner integration cannot make aboutToAppear async")
    original = source[opening + 1:closing].strip("\n")
    nested = indent_block(original, 2) if original.strip() else ""
    body = f"""    const context = getContext(this) as common.UIAbilityContext;
    if ({launch}.caseKey.length > 0) {{
{case_body.rstrip()}
    }} else {{"""
    if nested:
        body += "\n" + nested
    body += "\n    }"
    return source[:opening + 1] + "\n" + body + "\n  " + source[closing:]


def prepend_method_body(source: str, name: str, statement: str) -> str:
    span = method_span(source, name)
    if span is None:
        raise RuntimeError(f"ArkTS runtime binding requires EntryAbility.{name}")
    _, opening, _ = span
    return source[:opening + 1] + "\n" + statement.rstrip() + source[opening + 1:]


def patch_arkts(task_id: str, project: Path, target: Path) -> list[Path]:
    entry = project / "entry/src/main/ets/entryability/EntryAbility.ets"
    index = project / "entry/src/main/ets/pages/Index.ets"
    entry_text = entry.read_text()
    index_text = index.read_text()
    if task_id == "01_reading_challenge":
        launch = "ReadingRuntimeLaunch"
        episode_import = "import { prepareReadingEpisode } from '../.benchmark-evaluator/ReadingRuntimeEpisode';\n"
        case_body = """      const runtime = await prepareReadingEpisode(context, ReadingRuntimeLaunch.caseKey);
      const owner = this.createRuntimeOwner();
      await owner.mount(context, { clock: runtime.clock, effects: runtime.effects });
      const episode = await runtime.run(owner);
      console.info('LTB_RUNTIME:' + encodeURIComponent(JSON.stringify(episode)));"""
    elif task_id == "02_hybrid_search":
        launch = "HybridRuntimeLaunch"
        episode_import = "import { prepareHybridEpisode } from '../.benchmark-evaluator/HybridRuntimeEpisode';\n"
        case_body = """      const runtime = await prepareHybridEpisode(context, HybridRuntimeLaunch.caseKey);
      const owner = this.createRuntimeOwner();
      await owner.mount(context, {
        settings: runtime.settings, transport: runtime.transport,
        feedback: runtime.feedback, standardSearch: runtime.standardSearch
      });
      const episode = await runtime.run(owner);
      console.info('LTB_RUNTIME:' + encodeURIComponent(JSON.stringify(episode)));"""
    elif task_id == "03_explore_feed":
        launch = "ExploreRuntimeLaunch"
        episode_import = "import { prepareExploreEpisode } from '../.benchmark-evaluator/ExploreRuntimeEpisode';\n"
        case_body = """      const runtime = await prepareExploreEpisode(context, ExploreRuntimeLaunch.caseKey);
      const owner = this.createRuntimeOwner();
      await owner.mount(context, { state: runtime.state, persistence: runtime.persistence, leaf: runtime.leaf });
      const episode = await runtime.run(owner);
      const payload = encodeURIComponent(JSON.stringify(episode));
      const chunkSize = 1800;
      const chunkCount = Math.ceil(payload.length / chunkSize);
      for (let index = 0; index < chunkCount; index += 1) {
        console.info('LTB_RUNTIME_CHUNK:' + ExploreRuntimeLaunch.caseKey + ':' + String(index) + ':' +
          String(chunkCount) + ':' + payload.substring(index * chunkSize, (index + 1) * chunkSize));
      }"""
    else:
        launch = "SavedRuntimeLaunch"
        episode_import = "import { prepareSavedEpisode } from '../.benchmark-evaluator/SavedRuntimeEpisode';\n"
        case_body = """      const runtime = await prepareSavedEpisode(context, SavedRuntimeLaunch.caseKey);
      const owner = this.createRuntimeOwner();
      await owner.mount(context, { state: runtime.state, persistence: runtime.persistence, leaf: runtime.leaf });
      const episode = await runtime.run(owner);
      const payload = encodeURIComponent(JSON.stringify(episode));
      const chunkSize = 1800;
      const chunkCount = Math.ceil(payload.length / chunkSize);
      for (let index = 0; index < chunkCount; index += 1) {
        console.info('LTB_RUNTIME_CHUNK:' + SavedRuntimeLaunch.caseKey + ':' + String(index) + ':' +
          String(chunkCount) + ':' + payload.substring(index * chunkSize, (index + 1) * chunkSize));
      }"""
    launch_import = f"import {{ {launch} }} from '../.benchmark-evaluator/{launch}';\n"
    if launch_import.strip() not in entry_text:
        entry_text = launch_import + entry_text
    assignment = f"    {launch}.caseKey = String(want.parameters?.['caseKey'] ?? '');\n"
    entry_text = prepend_method_body(entry_text, "onCreate", assignment)
    common_import = "import { common } from '@kit.AbilityKit';\n"
    imports = episode_import + launch_import
    if common_import.strip() not in index_text:
        imports = common_import + imports
    index_text = imports + index_text
    index_text = wrap_about_to_appear(index_text, launch, case_body)
    entry.write_text(entry_text)
    index.write_text(index_text)
    return [path for path in target.rglob("*") if path.is_file()] + [entry, index]


def prepare_arkts(task_id: str, project: Path, migration: Path,
                  hidden: Path) -> tuple[list[Path], str]:
    source = migration / "evaluator/agent_harness/arkts/common"
    target = project / "entry/src/main/ets/.benchmark-evaluator"
    if target.exists():
        shutil.rmtree(target)
    copy_tree(source, target)
    return patch_arkts(task_id, project, target), "page_owner_integration_abi_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--task-id", choices=("01_reading_challenge", "02_hybrid_search", "03_explore_feed", "04_reading_lists"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    migration = args.migration.resolve()
    calibration_roots = {
        (migration / "arkts/base").resolve(),
        (migration / "arkts/final").resolve(),
        (migration / "android/native/base").resolve(),
        (migration / "android/native/final").resolve(),
    }
    if project in calibration_roots:
        raise RuntimeError("refusing hidden agent injection into a calibration root")
    audit_candidate(project)
    hidden = project / ".benchmark-evaluator"
    if hidden.exists():
        shutil.rmtree(hidden)
    hidden.mkdir()
    variant = "runtime_reflection"
    if args.platform == "android":
        files = prepare_android(args.task_id, project, migration, hidden)
    else:
        files, variant = prepare_arkts(args.task_id, project, migration, hidden)
    injected = [path for path in files if path.is_file()]
    content = "\n".join(path.read_text(errors="ignore") for path in injected)
    if re.search(r"traceDigest|\bexpected\b|\boracle\b", content):
        raise RuntimeError("hidden harness contains expected/oracle material")
    manifest = {
        "schemaVersion": 1,
        "taskId": args.task_id,
        "platform": args.platform,
        "bindingVariant": variant,
        "classification": "evaluator_owned_hidden_probe_and_build_wiring",
        "containsExpectedOracle": False,
        "productionLogicInjected": False,
        "files": [hash_record(project, path) for path in sorted(injected)],
    }
    (hidden / "PREPARED").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
