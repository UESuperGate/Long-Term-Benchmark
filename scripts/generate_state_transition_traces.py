#!/usr/bin/env python3
"""Generate platform-neutral evaluator traces from semantic binding manifests."""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
from pathlib import Path
from typing import Any

from generate_state_binding_manifests import (
    extract_case_id,
    extract_indented_block,
    split_cases,
    split_transition_blocks,
)


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", Path(__file__).resolve().parents[1]))
BINDINGS = ROOT / "state_tests" / "bindings"
TRACES = ROOT / "state_tests" / "traces"
STATE_TESTS = ROOT / "state_tests"


def selector_facts(selectors: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        facts.extend(f"{bucket}:{token}" for token in selectors.get(bucket) or [])
    facts.extend(f"property:{key}={value}" for key, value in (selectors.get("properties") or {}).items())
    return sorted(set(facts))


def state_constraints(task_id: str) -> dict[str, dict[str, Any]]:
    source = next(STATE_TESTS.glob(f"elementx-state-test*{task_id.split('_', 1)[-1].replace('_', '-')}*.yaml"), None)
    if source is None:
        source = next(
            path for path in sorted(STATE_TESTS.glob("elementx-state-test*.yaml"))
            if f"id: {task_id}" in path.read_text(encoding="utf-8-sig")
        )
    constraints: dict[str, dict[str, Any]] = {}
    for _, raw in split_cases(source.read_text(encoding="utf-8-sig")):
        transitions = split_transition_blocks(raw)
        constraints[extract_case_id(raw)] = {
            "givenStateYaml": textwrap.dedent(extract_indented_block(raw, "given_state", 4)).strip(),
            "toStateYaml": [
                textwrap.dedent(extract_indented_block(transition["raw"], "to_state", 8)).strip()
                for transition in transitions
            ],
        }
    return constraints


def trace_case(case: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
    phases = [{
        "phase": "initial",
        "ordinal": 0,
        "event": "",
        "stateConstraintYaml": constraints.get("givenStateYaml", ""),
        "selectors": case.get("selectors") or {},
        "expectedFacts": selector_facts(case.get("selectors") or {}),
    }]
    for transition in case.get("transitionSelectors") or []:
        ordinal = int(transition.get("ordinal") or len(phases))
        event = str(transition.get("event") or "")
        facts = selector_facts(transition)
        to_states = constraints.get("toStateYaml") or []
        phases.append({
            "phase": f"transition_{ordinal}",
            "ordinal": ordinal,
            "event": event,
            "stateConstraintYaml": to_states[ordinal - 1] if ordinal <= len(to_states) else "",
            "selectors": {
                key: transition.get(key) or ({} if key == "properties" else [])
                for key in ("visible", "hidden", "enabled", "disabled", "properties")
            },
            "expectedFacts": sorted([f"transition:{ordinal}:{event}", *[f"transition:{ordinal}:{fact}" for fact in facts]]),
        })
    canonical = json.dumps(phases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "caseId": case["caseId"],
        "caseTitle": case.get("caseTitle", ""),
        "functionalArea": case.get("functionalArea", ""),
        "fixtureKind": case.get("fixtureKind", ""),
        "traceDigest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "phases": phases,
    }


def main() -> int:
    TRACES.mkdir(parents=True, exist_ok=True)
    index = []
    for path in sorted(BINDINGS.glob("*.binding.json")):
        if path.name == "state_binding_manifest_index.json":
            continue
        binding = json.loads(path.read_text(encoding="utf-8-sig"))
        task_id = str(binding["task"]["id"])
        constraints = state_constraints(task_id)
        payload = {
            "version": 1,
            "platformNeutral": True,
            "evaluatorOwned": True,
            "task": binding["task"],
            "cases": [trace_case(case, constraints.get(str(case["caseId"]), {})) for case in binding.get("cases") or []],
        }
        out = TRACES / f"{task_id}.trace.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        index.append({"taskId": task_id, "path": str(out.relative_to(ROOT)), "caseCount": len(payload["cases"])})
        print(f"Wrote {out}")
    (TRACES / "trace_index.json").write_text(
        json.dumps({"version": 1, "platformNeutral": True, "traces": index}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
