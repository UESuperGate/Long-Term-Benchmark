#!/usr/bin/env python3
"""Audit the Wikipedia ArkTS runtime harness ownership and leaf boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS = ROOT / "benchmark_projects/wikipedia-android/migrations"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, passed: bool, evidence: str) -> dict[str, object]:
    return {"name": name, "passed": passed, "evidence": evidence}


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    reading = MIGRATIONS / "01_reading_challenge"
    hybrid = MIGRATIONS / "02_hybrid_search"
    tool = (MIGRATIONS / "tools/prepare_agent_harness.py").read_text()
    reading_episode_path = reading / "evaluator/agent_harness/arkts/common/ReadingRuntimeEpisode.ets"
    hybrid_episode_path = hybrid / "evaluator/agent_harness/arkts/common/HybridRuntimeEpisode.ets"
    reading_episode = reading_episode_path.read_text()
    hybrid_episode = hybrid_episode_path.read_text()
    reading_base_page = (reading / "arkts/base/entry/src/main/ets/pages/Index.ets").read_text()
    reading_page = (reading / "arkts/final/entry/src/main/ets/pages/Index.ets").read_text()
    hybrid_base_page = (hybrid / "arkts/base/entry/src/main/ets/pages/Index.ets").read_text()
    hybrid_page = (hybrid / "arkts/final/entry/src/main/ets/pages/Index.ets").read_text()
    reading_base_abi_path = reading / "arkts/base/entry/src/main/ets/integration/ReadingPageIntegration.ets"
    reading_final_abi_path = reading / "arkts/final/entry/src/main/ets/integration/ReadingPageIntegration.ets"
    hybrid_base_abi_path = hybrid / "arkts/base/entry/src/main/ets/integration/HybridPageIntegration.ets"
    hybrid_final_abi_path = hybrid / "arkts/final/entry/src/main/ets/integration/HybridPageIntegration.ets"
    reading_evaluator_path = reading / "evaluator/run_arkts_semantics.py"
    hybrid_evaluator_path = hybrid / "evaluator/run_arkts_semantics.py"
    reading_evaluator = reading_evaluator_path.read_text()
    hybrid_evaluator = hybrid_evaluator_path.read_text()
    http_leaf_path = hybrid / "arkts/final/entry/src/main/ets/model/HttpSearchLeaf.ets"
    http_leaf = http_leaf_path.read_text()
    reading_contract = load(reading / "canonical/transitions.json")
    hybrid_contract = load(hybrid / "canonical/transitions.json")
    reading_bindings = load(reading / "arkts/bindings.json")
    hybrid_bindings = load(hybrid / "arkts/bindings.json")
    reading_base_report = load(reading / "results/arkts-base.json")
    reading_final_report = load(reading / "results/arkts-final.json")
    hybrid_base_report = load(hybrid / "results/arkts-base.json")
    hybrid_final_report = load(hybrid / "results/arkts-final.json")
    control_root = ROOT / "eval_runs/multi_project_no_change_runtime_v2_20261022/wikipedia-android"
    reading_control_path = control_root / "01_reading_challenge/arkts-agent.json"
    hybrid_control_path = control_root / "02_hybrid_search/arkts-agent.json"
    reading_control = load(reading_control_path)
    hybrid_control = load(hybrid_control_path)

    results = [
        check("reading episode never constructs a detached production store",
              "new ReadingChallengeStore" not in reading_episode,
              "store construction is confined to Index.initialize"),
        check("hybrid episode never constructs a detached page store or view model",
              "new HybridSearchPageStore" not in hybrid_episode and
              "new HybridSearchViewModel" not in hybrid_episode,
              "Index owns HybridSearchPageStore and the store owns HybridSearchViewModel"),
        check("one role-neutral hidden adapter accepts arbitrary candidates",
              "--binding-variant" not in tool and
              'source = migration / "evaluator/agent_harness/arkts/common"' in tool and
              not (reading / "evaluator/agent_harness/arkts/base").exists() and
              not (reading / "evaluator/agent_harness/arkts/final").exists() and
              not (hybrid / "evaluator/agent_harness/arkts/base").exists() and
              not (hybrid / "evaluator/agent_harness/arkts/final").exists(),
              "prepare_agent_harness copies common only and never receives or infers a role"),
        check("hidden lifecycle wrapper preserves the candidate normal path",
              "original = source[opening + 1:closing]" in tool and
              "} else {" in tool and "return;" not in
              tool[tool.index("def patch_arkts"):tool.index("def prepare_arkts")],
              "case execution is conditional and the original aboutToAppear body remains in else"),
        check("reading final keeps revision-2 enrollment effects",
              "this.effects.heartbeat(this.state);" in
              (reading / "arkts/final/entry/src/main/ets/model/ReadingChallengeStore.ets").read_text() and
              "this.effects.updateWidget();" in
              (reading / "arkts/final/entry/src/main/ets/model/ReadingChallengeStore.ets").read_text(),
              "ReadingChallengeStore.enroll dispatches heartbeat and widget leaves"),
        check("hybrid controls only JSON transport below production HttpSearchLeaf",
              "interface SearchJsonTransport" in http_leaf and
              "new HttpSearchLeaf(input.transport as SearchJsonTransport)" in hybrid_page and
              "HybridIntegrationJsonTransport as SearchJsonTransport" in hybrid_episode and
              "implements SearchJsonTransport" in hybrid_episode,
              "URL construction and response mapping remain in HttpSearchLeaf"),
        check("hybrid effects derive from transport call records",
              "function searchEffects(calls: HttpCall[])" in hybrid_episode and
              "leafCalls: calls" in hybrid_episode and "function effectsFor" not in hybrid_episode,
              "effects are reduced from recorded URL calls rather than case-id literals"),
        check("public page-owner ABIs are stable across base and final",
              sha256(reading_base_abi_path) == sha256(reading_final_abi_path) and
              "createRuntimeOwner(): ReadingPageOwner" in reading_base_page and
              "createRuntimeOwner(): ReadingPageOwner" in reading_page and
              sha256(hybrid_base_abi_path) == sha256(hybrid_final_abi_path) and
              "createRuntimeOwner(): HybridPageOwner" in hybrid_base_page and
              "createRuntimeOwner(): HybridPageOwner" in hybrid_page,
              "both tasks expose an identical base/final page-owner integration contract"),
        check("page-owner actions are the rendered production actions",
              all(value in reading_page for value in
                  ("this.joinChallenge()", "this.openArticle()", "this.refreshChallengeSurface()")) and
              all(value in hybrid_page for value in
                  ("this.openHybrid()", "this.submitSearch()", "this.retrySearch()",
                   "this.rateResult(", "this.optOut()")),
              "runtime owners and rendered controls dispatch the same Index methods"),
        check("verdicts require runtime observations rather than file presence",
              all("contains(episode[\"observed\"], case[\"expected\"])" in source and
                  "runtime_checks" in source and "file_presence" not in source
                  for source in (reading_evaluator, hybrid_evaluator)),
              "both evaluators combine expected observations, invariants, and runtime boundary checks"),
    ]

    reading_cases = {case["caseId"]: case["traceDigest"] for case in reading_contract["cases"]}
    hybrid_cases = {case["caseId"]: case["traceDigest"] for case in hybrid_contract["cases"]}
    reading_bound = {case["caseId"]: case["traceDigest"] for case in reading_bindings["cases"]}
    hybrid_bound = {case["caseId"]: case["traceDigest"] for case in hybrid_bindings["cases"]}
    results.extend([
        check("reading active binding matches all canonical identities and digests",
              reading_cases == reading_bound and len(reading_cases) == 10,
              "10/10 case IDs and trace digests match"),
        check("hybrid active binding matches all canonical identities and digests",
              hybrid_cases == hybrid_bound and len(hybrid_cases) == 10,
              "10/10 case IDs and trace digests match"),
        check("reading revision-2 enroll digest and exact effects remain active",
              next(case for case in reading_contract["cases"] if case["caseId"] == "rc_enroll")["expected"]["effects"] ==
              ["heartbeat_requested", "widget_update_requested"] and
              reading_cases["rc_enroll"] == "018d71bd80e6f6e69ec196f67835a3288c6ec3eebb55c5d1ba4b170c5d94a7f2",
              "revision-2 contract is unchanged"),
        check("API23 calibration has exact polarity with no unscored cases",
              reading_base_report["semantic"] | {"cases": []} ==
              {"passed": 0, "failed": 10, "notScored": 0, "total": 10, "cases": []} and
              reading_final_report["semantic"] | {"cases": []} ==
              {"passed": 10, "failed": 0, "notScored": 0, "total": 10, "cases": []} and
              hybrid_base_report["semantic"] | {"cases": []} ==
              {"passed": 0, "failed": 10, "notScored": 0, "total": 10, "cases": []} and
              hybrid_final_report["semantic"] | {"cases": []} ==
              {"passed": 10, "failed": 0, "notScored": 0, "total": 10, "cases": []},
              "both tasks are base 0/10 and final 10/10 with no unscored cases"),
        check("all final cases passed runtime boundary checks",
              all(case["status"] == "pass" and case.get("transitionExecuted") is True and
                  all(item["passed"] for item in case.get("runtimeBoundaryChecks", []))
                  for report in (reading_final_report, hybrid_final_report)
                  for case in report["semantic"]["cases"]),
              "20/20 final cases executed and passed ownership/transport boundaries"),
        check("untouched-base arbitrary candidates execute and fail semantically",
              all(report["semantic"] | {"cases": []} ==
                  {"passed": 0, "failed": 10, "notScored": 0, "total": 10, "cases": []}
                  for report in (reading_control, hybrid_control)) and
              all(case["status"] == "fail" and case.get("transitionExecuted") is True and
                  all(item["passed"] for item in case.get("runtimeBoundaryChecks", []))
                  for report in (reading_control, hybrid_control)
                  for case in report["semantic"]["cases"]),
              "no-change reading and hybrid both ran 10 runtime episodes with zero not_scored"),
    ])

    source_paths = [
        MIGRATIONS / "tools/prepare_agent_harness.py",
        MIGRATIONS / "tools/build_arkts_calibration.py",
        MIGRATIONS / "tools/test_arkts_runtime_harness.py",
        reading_episode_path,
        hybrid_episode_path,
        reading_base_abi_path,
        reading_final_abi_path,
        hybrid_base_abi_path,
        hybrid_final_abi_path,
        http_leaf_path,
        reading_evaluator_path,
        hybrid_evaluator_path,
        reading_control_path,
        hybrid_control_path,
    ]
    report = {
        "schemaVersion": 1,
        "scope": "wikipedia ArkTS runtime semantic harness",
        "passed": all(item["passed"] for item in results),
        "checks": results,
        "sources": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size}
                    for path in source_paths],
    }
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
