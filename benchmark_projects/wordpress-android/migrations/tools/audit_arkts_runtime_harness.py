#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TASKS = {
    "01_pages_list": {
        "controller": "PagesController",
        "legacy_controller": "LegacyPagesController",
        "owner": "PagesPageOwner",
        "legacy_owner": "LegacyPagesPageOwner",
        "required_surface": ("openMenu", "chooseTrash", "confirmTrash", "selectAuthor"),
        "base_api": ("PageRecord", "PageRequest", "PagesServiceLeaf", "PagesPersistentInputLeaf",
                     "PagesStore", "PagesPageOwner", "PagesPageRuntime"),
        "fallbacks": ("emptyRequest()", "requests.length >", "rows.length >"),
    },
    "02_unified_support": {
        "controller": "UnifiedSupportController",
        "legacy_controller": "LegacySupportController",
        "owner": "UnifiedSupportPageOwner",
        "legacy_owner": "LegacySupportPageOwner",
        "required_surface": ("sendReply", "openConversation", "renderedAffordances"),
        "base_api": ("SupportConversation", "SupportServiceLeaf", "NetworkLeaf", "AttachmentLeaf",
                     "UnifiedSupportStore", "UnifiedSupportPageOwner", "UnifiedSupportPageRuntime"),
        "fallbacks": ("emptyConversation()", "conversations.length >", "rendered.length >"),
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_report(path: Path, expected_passed: int, expected_role: str | None = None,
                 expected_target: str | None = None) -> None:
    report = load(path)
    summary = report["semantic"]["summary"]
    require(summary == {"passed": expected_passed, "failed": 10 - expected_passed, "notScored": 0, "total": 10},
            f"{path}: unexpected semantic summary {summary}")
    require(report["device"]["apiLevel"] == 23, f"{path}: calibration was not run on API23")
    if expected_role is not None:
        require(report["role"] == expected_role, f"{path}: expected role {expected_role}")
    if expected_target is not None:
        require(report["device"]["target"] == expected_target,
                f"{path}: expected HDC target {expected_target}")
    for row in report["semantic"]["cases"]:
        evidence = row.get("runtimeEvidence")
        require(isinstance(evidence, dict), f"{path}: {row['caseId']} lacks runtime ownership evidence")
        require(evidence.get("pageOwnerId") != evidence.get("controllerOwnerId"),
                f"{path}: {row['caseId']} aliases page and controller ownership IDs")
        require(evidence.get("evaluatorStoreWrites") == 0, f"{path}: {row['caseId']} wrote the store")
        require(evidence.get("detachedControllers") == 0, f"{path}: {row['caseId']} created a detached controller")
        require(isinstance(evidence.get("leafCalls"), list), f"{path}: {row['caseId']} lacks leaf calls")
        if row["key"] == "draft_lifecycle":
            require(evidence.get("pageRecreated") is True, f"{path}: draft lifecycle did not recreate the page")
            require(evidence.get("pageOwnerId") != evidence.get("previousPageOwnerId"),
                    f"{path}: draft lifecycle retained the old page owner")
            controller_retained = evidence.get("controllerOwnerId") == evidence.get("previousControllerOwnerId")
            if report["role"] == "base":
                require(not controller_retained, f"{path}: base unexpectedly retained the target controller")
            elif report["role"] == "final":
                require(controller_retained, f"{path}: draft lifecycle did not retain the controller")


def audit_no_change_report(path: Path, task_id: str, expected_target: str) -> None:
    audit_report(path, 0, expected_role="agent", expected_target=expected_target)
    report = load(path)
    require(report["taskId"] == task_id, f"{path}: wrong taskId")
    require(report.get("diagnostics", {}).get("transport") == "hdc",
            f"{path}: no-change control did not execute over HDC")
    require(report.get("diagnostics", {}).get("productionEntryExecuted") is True,
            f"{path}: production EntryAbility was not executed")
    rows = report["semantic"]["cases"]
    require(all(row["status"] == "fail" for row in rows),
            f"{path}: untouched base must fail by observed semantics")
    for row in rows:
        require([checkpoint.get("label") for checkpoint in row.get("checkpoints", [])] == ["before", "after"],
                f"{path}: {row['caseId']} lacks runtime before/after checkpoints")
        require(isinstance(row.get("effects"), list), f"{path}: {row['caseId']} lacks runtime effects")
        require(row.get("observed") is not None, f"{path}: {row['caseId']} lacks runtime observation")


def audit_hidden_adapter(migrations: Path, task_id: str) -> None:
    task = migrations / task_id
    config = TASKS[task_id]
    tools = migrations / "tools"
    preparer = (tools / "prepare_agent_harness.py").read_text(encoding="utf-8")
    arkts_preparer = preparer[preparer.index("def prepare_arkts"):preparer.index("def main()")]
    require('arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets' in arkts_preparer,
            "ArkTS hidden adapter must use the single final semantic probe")
    require('arkts/final/entry/src/main/ets/entryability/EntryAbility.ets' in arkts_preparer,
            "ArkTS hidden adapter must use the single final EntryAbility template")
    require("candidate_target_sources" not in arkts_preparer and "runtime_role" not in arkts_preparer,
            "ArkTS hidden adapter must not select behavior from candidate source presence or role markers")

    base_root = task / "arkts/base/entry/src/main/ets"
    base_surface = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (base_root / "features").glob("*.ets")
    ) + "\n" + "\n".join(
        path.read_text(encoding="utf-8")
        for path in (base_root / "pages").glob("*PageOwner.ets")
    )
    for name in config["base_api"]:
        require(re.search(rf"export (?:interface|class) {re.escape(name)}\b", base_surface) is not None,
                f"{task_id}: untouched base lacks stable hidden-adapter API {name}")
    require("attachLegacy(" in base_surface,
            f"{task_id}: compatibility owner is not attached to the mounted legacy page owner")

    probe = (task / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets").read_text(encoding="utf-8")
    require(re.search(r"\bany\b", probe) is None, f"{task_id}: hidden probe uses ArkTS any")
    for token in config["fallbacks"]:
        require(token in probe, f"{task_id}: hidden probe lacks arbitrary-candidate fallback {token}")
    event_section = probe[probe.index("export async function runSemanticCase"):]
    require(f"new {config['controller']}" not in event_section,
            f"{task_id}: hidden adapter creates a detached controller")
    require(re.search(r"\.store(?:\(\))?\.[A-Za-z0-9_]+\s*=(?!=)", event_section) is None,
            f"{task_id}: hidden adapter writes derived store state")

    build_wrapper = (tools / "build_arkts_api23.sh").read_text(encoding="utf-8")
    require("--no-daemon" in build_wrapper,
            "disposable arbitrary candidates must not retain a daemon rooted in a deleted checkout")


def audit_task(migrations: Path, task_id: str) -> None:
    task = migrations / task_id
    config = TASKS[task_id]
    contract = load(task / "canonical/transitions.json")
    bindings = load(task / "arkts/bindings.json")
    expected = [(case["caseId"], case["traceDigest"]) for case in contract["cases"]]
    bound = [(case["caseId"], case["traceDigest"]) for case in bindings["cases"]]
    require(bound == expected, f"{task_id}: ArkTS bindings changed canonical case identity or digest")

    for role in ("base", "final"):
        root = task / "arkts" / role / "entry/src/main/ets"
        probe = (root / "evaluator/SemanticProbe.ets").read_text(encoding="utf-8")
        entry = (root / "entryability/EntryAbility.ets").read_text(encoding="utf-8")
        page = (root / "pages/Index.ets").read_text(encoding="utf-8")
        forbidden = (f"new {config['controller']}", f"new {config['legacy_controller']}")
        for token in forbidden:
            require(token not in probe, f"{task_id}/{role}: probe creates detached controller via {token}")
        require(re.search(r"\.store(?:\(\))?\.[A-Za-z0-9_]+\s*=(?!=)", probe) is None,
                f"{task_id}/{role}: probe writes derived store state")
        require("runtimeEvidenceJson" in probe, f"{task_id}/{role}: probe omits runtime ownership evidence")
        require("waitForOwner()" in probe, f"{task_id}/{role}: probe races the ArkUI page owner mount")
        require("prepareSemanticCase(this.semanticCase)" in entry, f"{task_id}/{role}: fixture is not prepared by EntryAbility")
        stage_create = entry[entry.index("onWindowStageCreate"):]
        require(stage_create.index("prepareSemanticCase(this.semanticCase)") < stage_create.index("loadContent('pages/Index'"),
                f"{task_id}/{role}: fixture must be installed before page load")
        expected_owner = config["legacy_owner"] if role == "base" else config["owner"]
        require(f"{expected_owner} =" in page, f"{task_id}/{role}: Index does not own {expected_owner}")

    final_owner_path = next((task / "arkts/final/entry/src/main/ets/pages").glob("*PageOwner.ets"))
    final_owner = final_owner_path.read_text(encoding="utf-8")
    require("waitForOwner(" in final_owner, f"{task_id}: page runtime lacks an owner mount barrier")
    for action in config["required_surface"]:
        require(action in final_owner, f"{task_id}: page owner lacks required action {action}")
    final_probe = (task / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets").read_text(encoding="utf-8")
    event_section = final_probe[final_probe.index("export async function runSemanticCase"):]
    require("controller.store." not in event_section, f"{task_id}: event probe reaches controller.store directly")
    require("const effect:" not in event_section, f"{task_id}: event probe reconstructs effects")

    runner = (task / "arkts/evaluator/run_device_semantic.py").read_text(encoding="utf-8")
    require("runtimeEvidenceJson" in runner or task_id == "02_unified_support",
            f"{task_id}: device scorer does not enforce runtime ownership evidence")
    shared_runner = runner if task_id == "01_pages_list" else \
        (migrations / "01_pages_list/arkts/evaluator/run_device_semantic.py").read_text(encoding="utf-8")
    require('status = "pass" if observed == case["expected"] and invariants_passed else "fail"' in shared_runner,
            f"{task_id}: pass/fail must derive only from runtime observation and canonical invariants")
    require('if args.role == "agent"' not in shared_runner,
            f"{task_id}: agent role marker must not decide semantic status or transport shape")
    if task_id == "02_unified_support":
        base_entry = (task / "arkts/base/entry/src/main/ets/entryability/EntryAbility.ets").read_text(encoding="utf-8")
        base_probe = (task / "arkts/base/entry/src/main/ets/evaluator/SemanticProbe.ets").read_text(encoding="utf-8")
        require("AbilityPageRecreator" in base_entry and "waitForOwnerAfter(owner.ownerId)" in base_probe,
                "02_unified_support/base: draft lifecycle lacks real page recreation")
        entry = (task / "arkts/final/entry/src/main/ets/entryability/EntryAbility.ets").read_text(encoding="utf-8")
        require("loadContent('pages/Index'" in entry and "AbilityPageRecreator" in entry,
                "02_unified_support: draft lifecycle lacks real page recreation")
        require("retainedController" in final_owner, "02_unified_support: page runtime lacks production retained state")
        require("waitForOwnerAfter(owner.ownerId)" in final_probe,
                "02_unified_support: draft lifecycle does not wait for a replacement page owner")
    audit_hidden_adapter(migrations, task_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pages-base-report", type=Path)
    parser.add_argument("--pages-final-report", type=Path)
    parser.add_argument("--support-base-report", type=Path)
    parser.add_argument("--support-final-report", type=Path)
    parser.add_argument("--pages-no-change-report", type=Path)
    parser.add_argument("--support-no-change-report", type=Path)
    parser.add_argument("--hdc-target", default="127.0.0.1:10180")
    args = parser.parse_args()
    for task_id in TASKS:
        audit_task(args.migrations.resolve(), task_id)
    reports = (
        (args.pages_base_report, 0),
        (args.pages_final_report, 10),
        (args.support_base_report, 0),
        (args.support_final_report, 10),
    )
    for path, expected_passed in reports:
        if path is not None:
            audit_report(path.resolve(), expected_passed)
    no_change_reports = (
        (args.pages_no_change_report, "01_pages_list"),
        (args.support_no_change_report, "02_unified_support"),
    )
    for path, task_id in no_change_reports:
        if path is not None:
            audit_no_change_report(path.resolve(), task_id, args.hdc_target)
    print("ArkTS runtime harness audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
