#!/usr/bin/env python3
"""Generate an auditable Element X Android FOSS release module inventory."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANDROID = ROOT / "_sources" / "element-x-android"
DEFAULT_OUTPUT = ROOT / "elementx_harmony_full" / "verification" / "android-module-inventory.json"
DEFAULT_MAP = ROOT / "elementx_harmony_full" / "verification" / "migration-map.json"
ROOT_BUILD_FILES = {
    "annotations/build.gradle.kts",
    "app/build.gradle.kts",
    "appconfig/build.gradle.kts",
    "appicon/element/build.gradle.kts",
    "appicon/enterprise/build.gradle.kts",
    "appnav/build.gradle.kts",
    "codegen/build.gradle.kts",
}
DISCOVERED_ROOTS = {"enterprise", "features", "libraries", "services", "tests"}
TEST_PARTS = {"test", "tests"}
DEPENDENCY_RE = re.compile(r"projects(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
PROJECT_RE = re.compile(r"project\(\s*[\"'](:[^\"']+)[\"']\s*\)")
SCOPE_RE = re.compile(
    r"(?:[\"'](?P<quoted>[A-Za-z][A-Za-z0-9]*)[\"']|(?P<plain>[A-Za-z][A-Za-z0-9]*))\s*\("
)
TEST_SCOPE_PARTS = ("test", "androidtest", "screenshot")
MANUAL_FIELDS = (
    "disposition",
    "reason",
    "target_modules",
    "target_paths",
    "target_symbols",
    "tests",
    "notes",
    "reviewed_by",
    "reviewed_at",
)
DEPENDENCY_INJECTION_PATH = "plugins/src/main/kotlin/extension/DependencyInjectionExtensions.kt"


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def git_text(repo: Path, tag: str, path: str) -> str:
    return run_git(repo, "show", f"{tag}:{path}")


def git_object(repo: Path, tag: str, path: str) -> str:
    return run_git(repo, "rev-parse", f"{tag}:{path}")


def module_id(source_path: str) -> str:
    return ":" + source_path.replace("/", ":")


def accessor_part(value: str) -> str:
    words = re.split(r"[-_]", value)
    return words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])


def project_accessor(module: str) -> str:
    return "projects." + ".".join(accessor_part(part) for part in module.lstrip(":").split(":"))


def discover_build_files(repo: Path, tag: str) -> list[str]:
    names = run_git(repo, "ls-tree", "-r", "--name-only", tag).splitlines()
    result: list[str] = []
    for path in names:
        if path in ROOT_BUILD_FILES or (
            path.endswith("/build.gradle.kts") and path.split("/", 1)[0] in DISCOVERED_ROOTS
        ):
            result.append(path)
    return sorted(result)


def classify_module(source_path: str) -> tuple[str, str, str]:
    parts = PurePosixPath(source_path).parts
    group = parts[0]
    leaf = parts[-1]
    if any(part in TEST_PARTS for part in parts):
        return "test", "test_only", "test source set"
    if source_path == "appicon/enterprise" or group == "enterprise":
        return "enterprise", "enterprise_only", "not part of the FOSS release"
    if source_path == "libraries/rustsdk":
        return "debug_adapter", "debug_local", "local debug Rust SDK wrapper"
    if source_path == "codegen":
        return "code_generation", "build_required", "KSP code generation dependency"

    if source_path == "app":
        role = "application"
    elif source_path in {"appnav", "appconfig", "appicon/element"}:
        role = "application_support"
    elif source_path == "annotations":
        role = "annotations"
    elif leaf == "api":
        role = "api"
    elif leaf in {"impl", "impl-foss", "compose", "noop"}:
        role = "implementation"
    else:
        role = "shared_runtime"
    return role, "runtime_required", "reachable FOSS production module"


def source_counts(repo: Path, tag: str, source_path: str) -> tuple[int, int]:
    names = run_git(repo, "ls-tree", "-r", "--name-only", tag, "--", f"{source_path}/src/main")
    lines = names.splitlines()
    return sum(name.endswith(".kt") for name in lines), sum(name.endswith(".java") for name in lines)


def dependency_scope(line: str, reference_start: int) -> str:
    matches = list(SCOPE_RE.finditer(line[:reference_start]))
    if not matches:
        return "implementation"
    match = matches[-1]
    return match.group("quoted") or match.group("plain") or "implementation"


def dependency_condition(line: str, scope: str) -> str:
    lowered = line.lower()
    if scope.lower().startswith("gplay"):
        return "foss:gplay"
    if "unifiedpush" in lowered:
        return "foss:unifiedpush"
    if "release" in scope.lower():
        return "release"
    if "debug" in scope.lower():
        return "debug"
    return "always"


def macro_expansions(helper_text: str, module_ids: set[str]) -> dict[str, list[tuple[str, int]]]:
    expansions: dict[str, list[tuple[str, int]]] = {}
    lines = helper_text.splitlines()
    for name in ("allLibrariesImpl", "allServicesImpl"):
        start = next(
            index for index, line in enumerate(lines)
            if re.search(rf"fun DependencyHandlerScope\.{name}\b", line)
        )
        end = next(
            (
                index for index in range(start + 1, len(lines))
                if re.match(r"(?:private )?fun DependencyHandlerScope\.", lines[index])
            ),
            len(lines),
        )
        targets: list[tuple[str, int]] = []
        for index in range(start, end):
            targets.extend(
                (match.group(1), index + 1)
                for match in PROJECT_RE.finditer(lines[index])
                if match.group(1) in module_ids
            )
        expansions[name] = targets

    for name, prefix, suffix in (
        ("allFeaturesImpl", ":features:", ":impl"),
        ("allFeaturesApi", ":features:", ":api"),
    ):
        definition_line = next(
            index + 1 for index, line in enumerate(lines)
            if re.search(rf"fun DependencyHandlerScope\.{name}\b", line)
        )
        expansions[name] = [
            (module, definition_line)
            for module in sorted(module_ids)
            if module.startswith(prefix) and module.endswith(suffix)
        ]
    return expansions


def parse_edges(
    source_id: str,
    build_file: str,
    build_blob: str,
    text: str,
    accessor_to_id: dict[str, str],
    expansions: dict[str, list[tuple[str, int]]],
    helper_blob: str,
) -> list[dict[str, object]]:
    edges: dict[tuple[str, str, str, int], dict[str, object]] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        references: list[tuple[int, str]] = []
        references.extend(
            (match.start(), accessor_to_id[match.group(0)])
            for match in DEPENDENCY_RE.finditer(line)
            if match.group(0) in accessor_to_id
        )
        references.extend((match.start(), match.group(1)) for match in PROJECT_RE.finditer(line))
        for start, target in references:
            scope = dependency_scope(line, start)
            if any(part in scope.lower() for part in TEST_SCOPE_PARTS):
                continue
            condition = dependency_condition(line, scope)
            key = (target, scope, condition, line_number)
            edges[key] = {
                "source": source_id,
                "target": target,
                "scope": scope,
                "condition": condition,
                "evidence": {
                    "path": build_file,
                    "blob": build_blob,
                    "line": line_number,
                },
            }

    macro_calls: list[tuple[str, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if "allFeaturesImpl(project)" in line:
            macro_calls.append(("allFeaturesImpl", line_number))
        if "allFeaturesApi(project)" in line:
            macro_calls.append(("allFeaturesApi", line_number))
        if "allLibrariesImpl()" in line:
            macro_calls.append(("allLibrariesImpl", line_number))
        if "allServicesImpl()" in line:
            macro_calls.append(("allServicesImpl", line_number))
    for macro, invocation_line in macro_calls:
        for target, definition_line in expansions[macro]:
            key = (target, "implementation", "always", invocation_line)
            edges.setdefault(
                key,
                {
                    "source": source_id,
                    "target": target,
                    "scope": "implementation",
                    "condition": "always",
                    "evidence": {
                        "path": "plugins/src/main/kotlin/extension/DependencyHandleScope.kt",
                        "blob": helper_blob,
                        "line": definition_line,
                        "expansion": macro,
                        "invoked_from": {
                            "path": build_file,
                            "blob": build_blob,
                            "line": invocation_line,
                        },
                    },
                },
            )
    return sorted(edges.values(), key=lambda edge: (str(edge["target"]), str(edge["scope"]), int(edge["evidence"]["line"])))


def add_dependency_injection_edges(
    edges: list[dict[str, object]],
    source_id: str,
    build_file: str,
    build_blob: str,
    build_text: str,
    injection_blob: str,
) -> list[dict[str, object]]:
    invocation_line = next(
        (number for number, line in enumerate(build_text.splitlines(), start=1) if "setupDependencyInjection()" in line),
        None,
    )
    if invocation_line is None:
        return edges
    for target, scope, helper_line in (
        (":annotations", "implementation", 38),
        (":codegen", "ksp", 40),
    ):
        edges.append(
            {
                "source": source_id,
                "target": target,
                "scope": scope,
                "condition": "compose convention plugin",
                "evidence": {
                    "path": DEPENDENCY_INJECTION_PATH,
                    "blob": injection_blob,
                    "line": helper_line,
                    "injected_from": {
                        "path": build_file,
                        "blob": build_blob,
                        "line": invocation_line,
                    },
                },
            }
        )
    return sorted(edges, key=lambda edge: (str(edge["target"]), str(edge["scope"]), int(edge["evidence"]["line"])))


def reachable(root: str, module_ids: set[str], modules: list[dict[str, object]]) -> list[str]:
    adjacency = {
        str(module["module_id"]): {
            str(edge["target"])
            for edge in module.get("dependencies", [])
            if str(edge["target"]) in module_ids
        }
        for module in modules
    }
    seen: set[str] = set()
    pending = [root]
    while pending:
        current = pending.pop()
        if current in seen or current not in module_ids:
            continue
        seen.add(current)
        pending.extend(adjacency.get(current, set()) - seen)
    return sorted(seen)


def build_inventory(repo: Path, tag: str) -> dict[str, object]:
    commit = run_git(repo, "rev-parse", f"{tag}^{{commit}}")
    build_files = discover_build_files(repo, tag)
    all_ids = {module_id(str(PurePosixPath(path).parent)) for path in build_files}
    accessor_to_id = {project_accessor(mid): mid for mid in all_ids}
    injection_blob = git_object(repo, tag, DEPENDENCY_INJECTION_PATH)
    helper_path = "plugins/src/main/kotlin/extension/DependencyHandleScope.kt"
    helper_blob = git_object(repo, tag, helper_path)
    expansions = macro_expansions(git_text(repo, tag, helper_path), all_ids)
    required: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []

    for build_file in build_files:
        source_path = str(PurePosixPath(build_file).parent)
        source_id = module_id(source_path)
        role, classification, rationale = classify_module(source_path)
        build_blob = git_object(repo, tag, build_file)
        kotlin_count, java_count = source_counts(repo, tag, source_path)
        item: dict[str, object] = {
            "module_id": source_id,
            "source_module": source_path,
            "source_path": source_path,
            "build_file": build_file,
            "role": role,
            "classification": classification,
            "group": source_path.split("/", 1)[0],
            "domain": source_path.split("/")[1] if "/" in source_path else source_path,
            "main_kotlin_files": kotlin_count,
            "main_java_files": java_count,
            "evidence": {
                "tag": tag,
                "commit": commit,
                "build_file_blob": build_blob,
                "source_tree_blob": git_object(repo, tag, source_path),
            },
        }
        if classification in {"runtime_required", "build_required"}:
            build_text = git_text(repo, tag, build_file)
            direct_edges = parse_edges(
                source_id,
                build_file,
                build_blob,
                build_text,
                accessor_to_id,
                expansions,
                helper_blob,
            )
            item["dependencies"] = add_dependency_injection_edges(
                direct_edges,
                source_id,
                build_file,
                build_blob,
                build_text,
                injection_blob,
            )
            required.append(item)
        else:
            item["exclusion_reason"] = rationale
            excluded.append(item)

    required.sort(key=lambda item: str(item["module_id"]))
    excluded.sort(key=lambda item: str(item["module_id"]))
    runtime_ids = [str(item["module_id"]) for item in required if item["classification"] == "runtime_required"]
    build_ids = [str(item["module_id"]) for item in required]
    runtime_reachable = reachable(":app", set(runtime_ids), required)
    build_reachable = reachable(":app", set(build_ids), required)
    known_ids = set(build_ids) | {str(item["module_id"]) for item in excluded}
    dangling = sorted(
        {
            str(edge["target"])
            for item in required
            for edge in item.get("dependencies", [])
            if str(edge["target"]) not in known_ids
        }
    )
    edge_count = sum(len(item.get("dependencies", [])) for item in required)
    now = datetime.now(timezone.utc).isoformat()
    settings_path = "settings.gradle.kts"
    return {
        "schema_version": "2.0",
        "generated_at": now,
        "source": {
            "repository": str(repo.resolve()),
            "tag": tag,
            "commit": commit,
            "variant": "fossRelease",
            "settings_file": settings_path,
            "settings_blob": git_object(repo, tag, settings_path),
            "dependency_helper": helper_path,
            "dependency_helper_blob": helper_blob,
            "dependency_injection_file": DEPENDENCY_INJECTION_PATH,
            "dependency_injection_blob": injection_blob,
        },
        "android_tag": tag,
        "android_commit": commit,
        "variant": "fossRelease",
        "module_count": len(required),
        "runtime_module_count": len(runtime_ids),
        "build_module_count": len(build_ids),
        "main_kotlin_file_count": sum(int(item["main_kotlin_files"]) for item in required),
        "main_java_file_count": sum(int(item["main_java_files"]) for item in required),
        "graph": {
            "root": ":app",
            "gradle_subprojects": len(build_files),
            "runtime_closure": len(runtime_ids),
            "build_closure": len(build_ids),
            "runtime_module_ids": runtime_ids,
            "build_module_ids": build_ids,
            "runtime_reachable_from_root": runtime_reachable,
            "build_reachable_from_root": build_reachable,
            "runtime_unreachable": sorted(set(runtime_ids) - set(runtime_reachable)),
            "build_unreachable": sorted(set(build_ids) - set(build_reachable)),
            "dependency_edge_count": edge_count,
            "dangling_internal_dependencies": dangling,
        },
        "modules": required,
        "excluded_modules": excluded,
    }


def initial_mapping(module: dict[str, object]) -> dict[str, object]:
    return {
        "module_id": module["module_id"],
        "source_module": module["source_module"],
        "source_path": module["source_path"],
        "role": module["role"],
        "classification": module["classification"],
        "disposition": "unmapped",
        "reason": "",
        "target_modules": [],
        "target_paths": [],
        "target_symbols": [],
        "tests": [],
        "notes": "",
    }


def merge_migration_map(inventory: dict[str, object], existing: dict[str, object] | None) -> dict[str, object]:
    existing = existing or {}
    old_items = {
        str(item.get("source_module")): item
        for item in existing.get("mappings", [])
        if isinstance(item, dict) and item.get("source_module")
    }
    mappings: list[dict[str, object]] = []
    for module in inventory["modules"]:
        item = initial_mapping(module)
        old = old_items.get(str(module["source_module"]), {})
        for field in MANUAL_FIELDS:
            if field in old:
                item[field] = old[field]
        mappings.append(item)
    source = inventory["source"]
    return {
        "schema_version": "2.0",
        "generated_at": inventory["generated_at"],
        "source": {
            "tag": source["tag"],
            "commit": source["commit"],
            "variant": source["variant"],
            "inventory_schema_version": inventory["schema_version"],
        },
        "required_module_count": len(mappings),
        "mappings": mappings,
    }


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--android", type=Path, default=DEFAULT_ANDROID)
    parser.add_argument("--tag", default="v26.04.0")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--migration-map", type=Path, default=DEFAULT_MAP)
    args = parser.parse_args()

    inventory = build_inventory(args.android, args.tag)
    migration_map = merge_migration_map(inventory, load_json(args.migration_map))
    write_json(args.output, inventory)
    write_json(args.migration_map, migration_map)
    graph = inventory["graph"]
    print(
        f"Wrote {graph['runtime_closure']} runtime / {graph['build_closure']} build modules "
        f"for {args.tag} to {args.output}"
    )
    print(f"Updated {len(migration_map['mappings'])} migration entries in {args.migration_map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
