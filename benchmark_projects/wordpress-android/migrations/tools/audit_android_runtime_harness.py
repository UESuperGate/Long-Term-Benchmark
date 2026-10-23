#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TASKS = {
    "01_pages_list": {
        "owner": "PagesRuntimeOwnerActivity",
        "runtime": "evaluator/final-runtime/evaluator/pages/PagesRuntimeMain.kt",
        "owner_path": "evaluator/final-main/org/wordpress/android/ui/pagesrs/PagesRuntimeOwnerActivity.kt",
        "required_runtime": (
            "OwnerSession", "openPage(", "rowIds(owner, PageRsListTab.TRASHED)",
            "waitFor { collection.refreshCalls == 1 }",
        ),
        "forbidden_runtime": ("targetActionReachable", '"trashedRows" to listOf',),
    },
    "02_unified_support": {
        "owner": "SupportRuntimeOwnerActivity",
        "runtime": "evaluator/final-runtime/evaluator/support/SupportRuntimeMain.kt",
        "owner_path": "evaluator/final-main/org/wordpress/android/support/unified/ui/SupportRuntimeOwnerActivity.kt",
        "required_runtime": ("OwnerSession", ".recreate()", "accessibilityStrings", "renderSelectedDetail"),
        "forbidden_runtime": ("setNewConversation(", "ConversationStatus.fromStatus", "fun surface()"),
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_repository(root: Path) -> dict:
    migrations = root / "benchmark_projects/wordpress-android/migrations"
    task_results = {}
    for task_id, config in TASKS.items():
        focused = migrations / task_id / "android/focused-runtime"
        runner = (focused / "evaluator/run_semantic.py").read_text(encoding="utf-8")
        runtime_path = focused / config["runtime"]
        owner_path = focused / config["owner_path"]
        runtime = runtime_path.read_text(encoding="utf-8")
        owner = owner_path.read_text(encoding="utf-8")
        build = (focused / "final/build.gradle.kts").read_text(encoding="utf-8")

        for token in ("target_absent", "targetPathDirectlyVerifiedAbsent", "targetActionReachable"):
            require(token not in runner, f"{task_id}: runner contains source-presence verdict token {token}")
        require("actual.get(\"observed\") == case[\"expected\"]" in runner,
                f"{task_id}: runner does not score exact runtime observations")
        require('srcDir("../evaluator/final-main")' in build,
                f"{task_id}: application owner is not compiled into main")
        require('srcDir("../evaluator/final-runtime")' in build,
                f"{task_id}: case adapter is not isolated in androidTest")
        require("ViewModelProvider(this" in owner,
                f"{task_id}: owner does not own its production ViewModel")
        require(config["owner"] in runtime, f"{task_id}: runtime does not enter the application owner")
        for token in config["required_runtime"]:
            require(token in runtime, f"{task_id}: missing runtime ownership evidence {token}")
        for token in config["forbidden_runtime"]:
            require(token not in runtime, f"{task_id}: forbidden evaluator behavior {token}")
        if task_id == "02_unified_support":
            require("UnifiedConversationDetailScreen(" in owner,
                    "02_unified_support: owner does not render the production detail screen")
            require("UnifiedConversationDetailScreen.kt" in build,
                    "02_unified_support: production detail screen is excluded from the APK")
            candidate_owner_path = focused / (
                "evaluator/candidate-v1-main/org/wordpress/android/support/unified/ui/"
                "SupportRuntimeOwnerActivity.kt"
            )
            candidate_runtime_path = focused / (
                "evaluator/candidate-v1-runtime/evaluator/support/SupportRuntimeMain.kt"
            )
            candidate_owner = candidate_owner_path.read_text(encoding="utf-8")
            candidate_runtime = candidate_runtime_path.read_text(encoding="utf-8")
            require("UnifiedConversationDetailScreen(" in candidate_owner,
                    "02_unified_support: candidate-v1 owner does not render candidate Compose UI")
            require("viewModel.sendReply" in candidate_owner,
                    "02_unified_support: candidate-v1 owner does not dispatch to production state")
            require('waitFor("closed semantics")' not in candidate_runtime,
                    "02_unified_support: candidate-v1 runtime waits on a passing assertion")
            require('waitFor("attachment deletion leaf event")' not in candidate_runtime,
                    "02_unified_support: candidate-v1 runtime turns a deletion failure into NS")
            arbitrary_candidate_adapter = {
                "path": str(candidate_runtime_path.relative_to(root)),
                "sha256": sha256(candidate_runtime_path),
                "ownerPath": str(candidate_owner_path.relative_to(root)),
                "ownerSha256": sha256(candidate_owner_path),
                "abiProfile": "candidate-v1",
                "verdictShortcuts": 0,
            }

        else:
            arbitrary_candidate_adapter = None
        if task_id == "01_pages_list":
            public_runtime_path = focused / (
                "evaluator/public-owner-runtime/evaluator/pages/PagesPublicOwnerRuntimeMain.kt"
            )
            public_runtime = public_runtime_path.read_text(encoding="utf-8")
            for token in (
                "PagesRuntimeOwnerActivity.open", "CollectionLeaf.install",
                "DefaultWpServiceProvider.instance", "fun runCase(",
            ):
                require(token in public_runtime, f"{task_id}: public-owner adapter lacks {token}")
            for token in ('"status" to', "target_absent", "source presence"):
                require(token not in public_runtime,
                        f"{task_id}: public-owner adapter contains verdict shortcut {token}")
            arbitrary_candidate_adapter = {
                "path": str(public_runtime_path.relative_to(root)),
                "sha256": sha256(public_runtime_path),
                "ownerRedeclaration": False,
                "verdictShortcuts": 0,
            }

        reports = {}
        for role, expected in (("base", {"passed": 0, "failed": 10, "notScored": 0, "total": 10}),
                               ("final", {"passed": 10, "failed": 0, "notScored": 0, "total": 10})):
            report_path = migrations / task_id / "provenance" / f"android-runtime-owner-{role}.json"
            report = load(report_path)
            require(report["semantic"]["summary"] == expected,
                    f"{task_id}/{role}: unexpected API37 polarity {report['semantic']['summary']}")
            require(report["device"] == {"serial": "emulator-5554", "apiLevel": 37},
                    f"{task_id}/{role}: calibration device is not API37 emulator-5554")
            require(all(case["status"] != "not_scored" for case in report["semantic"]["cases"]),
                    f"{task_id}/{role}: unscored case remains")
            reports[role] = {"path": str(report_path.relative_to(root)), "sha256": sha256(report_path)}

        task_results[task_id] = {
            "status": "pass",
            "applicationOwner": config["owner"],
            "detachedViewModels": 0,
            "directDerivedStateWrites": 0,
            "sourcePresenceVerdicts": 0,
            "arbitraryCandidateAdapter": arbitrary_candidate_adapter,
            "reports": reports,
        }
    return {"schemaVersion": 1, "status": "pass", "tasks": task_results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_repository(args.root.resolve())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
