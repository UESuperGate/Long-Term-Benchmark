from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def effects_match(actual: list[Any], expected: list[Any]) -> bool:
    remaining = list(actual)
    for item in expected:
        index = next((i for i, candidate in enumerate(remaining) if contains(candidate, item)), None)
        if index is None:
            return False
        remaining.pop(index)
    return True


def effect_names(episode: dict[str, Any]) -> list[str]:
    effects = episode.get("observed", {}).get("effects", [])
    return [str(item.get("name", item.get("leaf", ""))) for item in effects if isinstance(item, dict)]


def core_matches(case: dict[str, Any], episode: dict[str, Any]) -> bool:
    actual = episode.get("observed", {})
    expected = case["expected"]
    structural = {key: value for key, value in expected.items() if key not in {"effects", "absentEffects"}}
    names = " ".join(effect_names(episode)).lower()
    return (contains(actual, structural)
            and effects_match(actual.get("effects", []), expected.get("effects", []))
            and all(str(token).lower() not in names for token in expected.get("absentEffects", [])))


def invariant_values(key: str, episode: dict[str, Any]) -> list[bool]:
    before = episode.get("before", {})
    after = episode.get("after", {})
    state = after.get("state", {})
    persistence = after.get("persistence", {})
    effects = after.get("effects", [])
    names = effect_names(episode)
    history = after.get("historyDays", [])
    decision = after.get("decision", {})
    decision_after = after.get("decisionAfterRelaunch", {})
    if key == "first_eligibility_records_impression":
        return [history == ["2026-08-25", "2026-08-26"],
                decision.get("shouldShow") is True and "queryDistinctReadingDaysWithinHistoryCutoff" in names,
                persistence.get("impressions") == 1 and state.get("visible") is True]
    if key == "maybe_later_requires_two_return_days":
        return [persistence.get("impressions") == 1,
                any(item.get("name") == "countDistinctReturnReadingDays" and item.get("count") == 1 for item in effects),
                decision.get("shouldShow") is False and state.get("accountEncouragementVisible") is False]
    if key == "close_permanently_dismisses":
        return [before.get("state", {}).get("visible") is True,
                persistence.get("impressions") == 100 and episode.get("storageReopened") is True,
                decision_after.get("shouldShow") is False and state.get("accountEncouragementVisible") is False]
    if key == "create_account_success_finishes_and_suppresses":
        return ["launchRegistrationFirstAuthentication" in names and "finishAccountEncouragementAfterLoginResult" in names,
                state.get("account") == "registered",
                persistence.get("impressions") == 1 and decision_after.get("shouldShow") is False]
    if key == "registered_account_is_suppressed":
        return [len(history) == 2 and decision.get("shouldShow") is False,
                names and names[0] == "readPermanentAccountState" and "queryDistinctReadingDaysWithinHistoryCutoff" not in names,
                decision.get("evaluated") is True and state.get("accountEncouragementVisible") is False]
    if key == "external_article_deep_link_is_suppressed":
        return [episode.get("ordinaryLaunchPositiveControl") is True,
                persistence.get("impressions") == 0 and after.get("routing", {}).get("encouragementConsidered") is False,
                state.get("surface") == "article" and state.get("article") == "en:Ada_Lovelace"]
    if key == "stale_history_does_not_qualify":
        return [history == ["2025-08-31", "2025-09-01"],
                any(item.get("name") == "queryDistinctReadingDaysWithinHistoryCutoff" and item.get("qualifyingDays") == 0 for item in effects),
                persistence.get("impressions") == 0 and persistence.get("lastImpressionDate") == ""]
    if key == "invalid_persisted_date_fails_closed":
        return [any(item.get("name") == "parsePersistedLastImpressionDate" and item.get("result") == "invalid" for item in effects),
                "countDistinctReturnReadingDays" not in names,
                decision.get("completedWithoutException") is True and state.get("surface") == "main"]
    if key == "two_return_days_trigger_second_impression":
        return [all(day > "2026-08-30" for day in history), len(set(history)) == 2,
                persistence.get("impressions") == 2 and persistence.get("lastImpressionDate") == "2026-09-02"]
    return [persistence.get("impressions") == 2,
            "countDistinctReturnReadingDays" not in names and decision.get("shouldShow") is False,
            persistence.get("lastImpressionDate") == "2026-08-30"]


def score_case(case: dict[str, Any], episode: dict[str, Any]) -> dict[str, Any]:
    values = invariant_values(case["key"], episode)
    checks = [{"invariant": text, "passed": bool(values[index]), "evidence": {
        "before": episode.get("before", {}), "after": episode.get("after", {})
    }} for index, text in enumerate(case.get("invariants", []))]
    observed = episode.get("observed", {})
    boundary = [
        {"check": "canonical given/event reached the evaluator adapter", "passed": episode.get("given") == case["given"] and episode.get("event") == case["event"]},
        {"check": "real page owner executed production methods", "passed": episode.get("commonEntryObserved") is True and bool(episode.get("invokedProductionMethods"))},
        {"check": "production feature is available", "passed": observed.get("featureAvailable") is True},
        {"check": "production persistence was reopened", "passed": episode.get("storageReopened") is True},
        {"check": "transition completed without evaluator early exit", "passed": episode.get("transitionExecuted") is True and episode.get("earlyExit") is False},
    ]
    passed = core_matches(case, episode) and all(item["passed"] for item in checks + boundary)
    return {"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
            "status": "pass" if passed else "fail", "observed": observed,
            "invariantChecks": checks, "runtimeBoundaryChecks": boundary}


def source_inventory(root: Path, suffixes: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes and "build" not in p.parts):
        data = path.read_bytes()
        rows.append({"path": str(path.relative_to(root)), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    return rows


def write_report(output: Path, task_id: str, platform: str, role: str, rows: list[dict[str, Any]],
                 sources: list[dict[str, Any]], runtime: dict[str, Any], episodes: list[dict[str, Any]]) -> None:
    summary = {"total": len(rows), "pass": sum(row["status"] == "pass" for row in rows),
               "fail": sum(row["status"] == "fail" for row in rows),
               "notScored": sum(row["status"] == "not_scored" for row in rows)}
    report = {"schemaVersion": 2, "taskId": task_id, "platform": platform, "role": role,
              "observationMode": "runtime_state_transition", "summary": summary,
              "runtime": runtime, "sources": sources, "cases": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    output.with_name(output.stem + ".raw.json").write_text(json.dumps({"episodes": episodes}, indent=2, ensure_ascii=False) + "\n")
