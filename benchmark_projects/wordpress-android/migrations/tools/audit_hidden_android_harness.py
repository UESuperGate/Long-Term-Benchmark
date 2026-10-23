#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TASKS = {
    "01_pages_list": {
        "targetPackage": "org.wordpress.android.ui.pagesrs",
        "targetDeclarations": (
            "PagesRsListViewModel", "PageRsFluxCBridge", "PageRsTreeBuilder", "PageRsMenuActions",
        ),
    },
    "02_unified_support": {
        "targetPackage": "org.wordpress.android.support.unified",
        "targetDeclarations": (
            "UnifiedSupportViewModel", "UnifiedSupportRepository", "AttachmentStateValidator",
            "EncryptedAppLogsUploader", "TempAttachmentsUtil",
        ),
    },
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise RuntimeError(diagnostic)


def audit_sources(project: Path, prepared: dict) -> dict:
    task = TASKS[prepared["taskId"]]
    hidden = project / ".benchmark-evaluator"
    main = hidden / "main"
    android_test = hidden / "androidTest"
    source_files = sorted(path for path in hidden.rglob("*") if path.suffix in {".kt", ".java"})
    require(source_files, "hidden Android harness contains no source files")
    require(all(path.is_relative_to(main) or path.is_relative_to(android_test) for path in source_files),
            "hidden Android source exists outside the declared main/androidTest roots")

    package_pattern = re.compile(
        rf"^\s*package\s+{re.escape(task['targetPackage'])}(?:\.|\s*$)", re.MULTILINE
    )
    declaration_pattern = re.compile(
        r"\b(?:class|object|interface|fun)\s+(?:" + "|".join(map(re.escape, task["targetDeclarations"])) + r")\b"
    )
    violations: list[str] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(project).as_posix()
        runtime_owner = path.is_relative_to(main / "runtime-owner") and path.name in {
            "PagesRuntimeOwnerActivity.kt", "PagesBaseOwnerActivity.kt",
            "SupportRuntimeOwnerActivity.kt", "SupportBaseOwnerActivity.kt",
            "PreviewStubs.kt", "EvaluatorLeaf.kt", "EvaluatorContentProvider.kt",
            "CoilComposeStubs.kt", "ImageRequest.kt", "VideoFrameDecoder.kt",
        }
        if (package_pattern.search(text) and not runtime_owner) or declaration_pattern.search(text):
            violations.append(relative)
        if path.is_relative_to(main):
            if not (path.is_relative_to(main / "stubs") or path.is_relative_to(main / "runtime-owner")):
                violations.append(f"{relative}: main injection is outside stubs/runtime-owner")
            evaluator_package = re.search(r"^\s*package\s+evaluator(?:\.|\s*$)", text, re.MULTILINE)
            controlled_support_leaf = (
                prepared["taskId"] == "02_unified_support"
                and path.is_relative_to(main / "runtime-owner/evaluator/support/leaf")
            )
            base_owner = path.name in {"PagesBaseOwnerActivity.kt", "SupportBaseOwnerActivity.kt"}
            if (evaluator_package and not controlled_support_leaf and not base_owner) or "fun runCase(" in text:
                violations.append(f"{relative}: evaluator runtime code leaked into app main")
    require(not violations, "hidden harness contains target production/runtime implementation: " + ", ".join(violations))
    require(any(path.is_relative_to(android_test) and "fun runCase(" in path.read_text(encoding="utf-8")
                for path in source_files), "androidTest runtime adapter is missing")
    require(any(path.is_relative_to(android_test) and path.name == "SemanticInstrumentation.kt" for path in source_files),
            "Android instrumentation entrypoint is missing")
    build = (project / "build.gradle.kts").read_text(encoding="utf-8")
    require('srcDir(".benchmark-evaluator/androidTest")' in build,
            "hidden Android instrumentation is not wired into the androidTest source set")
    require('srcDir(".benchmark-evaluator/main")' in build,
            "hidden Android owner is not wired into the main source set")
    require("../evaluator/" not in build,
            "candidate build still depends on evaluator sources outside the hidden harness")
    require(".benchmark-scaffold/main" not in build,
            "visible compilation scaffold remains wired after hidden harness preparation")
    forbidden_device_stubs = [
        path.relative_to(project).as_posix()
        for path in source_files
        if path.is_relative_to(main / "stubs")
        and path.relative_to(main / "stubs").parts[0] in {"android", "androidx"}
    ]
    require(not forbidden_device_stubs,
            "host framework stubs leaked into the device APK: " + ", ".join(forbidden_device_stubs))
    return {
        "hiddenSourceFiles": len(source_files),
        "mainStubFiles": sum(path.is_relative_to(main) for path in source_files),
        "androidTestAdapterFiles": sum(path.is_relative_to(android_test) for path in source_files),
        "targetProductionImplementations": 0,
    }


def audit_no_change_report(report_path: Path) -> dict:
    report = load(report_path)
    summary = report.get("semantic", {}).get("summary", {})
    require(report.get("role") == "agent", "no-change smoke report must use role=agent")
    require(summary == {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
            f"no-change agent is not strict base-all-fail: {summary}")
    cases = report["semantic"]["cases"]
    for case in cases:
        require(case.get("status") == "fail", f"{case.get('caseId')}: expected a semantic fail")
        require(isinstance(case.get("observed"), dict),
                f"{case.get('caseId')}: base owner runtime observation is missing")
        require(len(case.get("checkpoints", [])) >= 2, f"{case.get('caseId')}: before/after checkpoints missing")
        require(case.get("effects") == [], f"{case.get('caseId')}: no-change candidate emitted target effects")
        sources = case.get("productionSources", [])
        require(sources and all(source.get("sha256") for source in sources),
                f"{case.get('caseId')}: production source hashes missing")
        require(isinstance(case.get("invariantChecks"), list),
                f"{case.get('caseId')}: invariant field is missing")
    return {"report": str(report_path), "summary": summary, "casesAudited": len(cases)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--no-change-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    project = args.project.resolve()
    prepared_path = project / ".benchmark-evaluator/PREPARED"
    require(prepared_path.is_file(), "hidden harness PREPARED manifest is missing")
    prepared = load(prepared_path)
    require(prepared.get("platform") == "android", "hidden harness audit only accepts Android")
    require(prepared.get("containsExpectedOracle") is False, "hidden harness declares oracle material")
    require(prepared.get("productionLogicInjected") is False, "hidden harness declares production injection")
    require("selectedRuntimeAdapter" not in prepared, "hidden harness exposes a base/final role marker")
    require(
        prepared.get("androidMainInjection")
        == "controlled_leaves_compilation_stubs_and_optional_compatibility_owner",
        "main injection does not declare the runtime owner boundary",
    )
    require(prepared.get("androidRuntimeAdapterSourceSet") == "androidTest", "runtime adapter is not test-only")
    receipt = prepared.get("visibleAbiReceipt")
    require(isinstance(receipt, dict) and receipt.get("sha256"), "verified visible ABI receipt is missing")
    runner = (
        Path(__file__).resolve().parent.parent
        / prepared["taskId"]
        / "android/focused-runtime/evaluator/run_semantic.py"
    )
    runner_text = runner.read_text(encoding="utf-8")
    require('"status": "not_scored"' in runner_text,
            "infrastructure failures are not preserved as not_scored")
    require('status = "pass" if actual.get("observed") == case["expected"]' in runner_text,
            "semantic verdict is not derived from exact runtime observation")
    for token in ("target_absent", "targetPathDirectlyVerifiedAbsent", "targetActionReachable"):
        require(token not in runner_text, f"runner contains source-presence verdict token {token}")

    if prepared["taskId"] == "01_pages_list":
        public_runtime = (
            Path(__file__).resolve().parent.parent
            / "01_pages_list/android/focused-runtime/evaluator/public-owner-runtime/evaluator/pages/PagesPublicOwnerRuntimeMain.kt"
        ).read_text(encoding="utf-8")
        for token in (
            "PagesRuntimeOwnerActivity.open", "CollectionLeaf.install", "DefaultWpServiceProvider.instance",
        ):
            require(token in public_runtime, f"public-owner runtime is missing {token}")
        for token in ('"status" to', "source presence", "target_absent"):
            require(token not in public_runtime, f"public-owner runtime contains verdict shortcut {token}")

    result = {
        "schemaVersion": 1,
        "taskId": prepared["taskId"],
        "status": "pass",
        "productionLogicInjected": False,
        "candidateProductionSourceCount": len(prepared.get("candidateProductionSources", [])),
        "sourceAudit": audit_sources(project, prepared),
    }
    if args.no_change_report:
        result["noChangeAgent"] = audit_no_change_report(args.no_change_report.resolve())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
