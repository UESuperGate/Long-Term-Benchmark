"""Task08 Android admission policy. Domain projections are never runtime scores.

The old adapter executed some real SDK calls, but copied its before/after state
from a case-key oracle. No reviewed end-to-end executor has replaced it yet.
Keep this gate closed until a source-bound RoomFlow/UI executor is verified.
"""

WITHDRAWAL = "task08_android_projection_withdrawal_v1"
REASON = (
    "Task08 Android calibration withdrawn: baseObservation/canonicalExpected "
    "projected unexecuted state; loaded timelines, RoomFlow navigation and "
    "composer/UI binding require independent runtime evidence."
)


def legacy_projection(row):
    for checkpoint in row.get("checkpoints", []):
        state = checkpoint.get("state", {})
        if ("focusedApiAvailable" in state or "threadRouteEntered" in state or
                "productionPrefix" in state or
                "real room/controller/timeline; composer" in str(state.get("observationBoundary", "")) or
                "JoinedRustRoom.createTimeline(Threaded) -> TimelineController -> RustTimeline" ==
                state.get("productionBoundary")):
            return True
    return False


def validate_report_evidence(report, contract=None):
    if report.get("taskId") != "08_threads" or report.get("platform") != "android":
        raise ValueError("Task08 Android runtime policy used for another task/platform")
    scored = [row for row in report.get("semantic", {}).get("cases", [])
              if row.get("status") in {"pass", "fail"}]
    if any(legacy_projection(row) for row in scored):
        raise ValueError(REASON)
    if scored:
        # A caller adding a marker cannot opt an unreviewed evaluator into scoring.
        raise ValueError("Task08 Android: no reviewed complete RoomFlow/UI runtime executor; " + REASON)
    return True
