#!/usr/bin/env python3
"""Static guardrails for the two Wikipedia Android semantic harnesses."""

from __future__ import annotations

import argparse
from pathlib import Path


def require(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"{label}: missing {needle!r}")


def forbid(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle in text:
        failures.append(f"{label}: forbidden {needle!r}")


def audit(root: Path) -> list[str]:
    migrations = root / "benchmark_projects/wikipedia-android/migrations"
    reading = migrations / "01_reading_challenge"
    hybrid = migrations / "02_hybrid_search"
    failures: list[str] = []

    reading_episode = (reading / "android/shared/native_test/kotlin/org/wikipedia/benchmark/reading/native/NativeReadingEpisode.kt").read_text()
    reading_page = (reading / "android/final/src/upstream/kotlin/org/wikipedia/widgets/readingchallenge/ReadingChallengePageActionPrefix.kt").read_text()
    page_load = (reading / "android/final/src/upstream/kotlin/org/wikipedia/page/PageLoadCompleteActionPrefix.kt").read_text()
    reading_prefs = (reading / "android/shared/native_leaf/kotlin/org/wikipedia/settings/Prefs.kt").read_text()
    require(reading_episode, "ReadingChallengePageActionPrefix(context)", "reading episode", failures)
    require(reading_page, "enrollment.enroll(currentDate)", "reading enrollment owner", failures)
    require(reading_page, "pageLoadComplete.onPageLoadComplete(currentDate)", "reading article owner", failures)
    require(page_load, "challengeRepository.updateOnArticleRead(currentDate)", "page-load prefix", failures)
    for forbidden in ("Class.forName", "updateOnArticleRead(", "resolveState(", "runCatching"):
        forbid(reading_episode, forbidden, "reading episode", failures)
    for required in ("SharedPreferences", "fun reopen", ".commit()"):
        require(reading_prefs, required, "reading prefs", failures)

    hybrid_episode = (hybrid / "android/shared/native_test/kotlin/org/wikipedia/benchmark/hybrid/native/NativeHybridEpisode.kt").read_text()
    hybrid_page = (hybrid / "android/final/src/upstream/kotlin/org/wikipedia/search/HybridSearchPageActionPrefix.kt").read_text()
    hybrid_leaf = (hybrid / "android/shared/leaf/kotlin/org/wikipedia/search/RuntimeSearchLeaves.kt").read_text()
    hybrid_prefs = (hybrid / "android/shared/native_leaf/kotlin/org/wikipedia/settings/Prefs.kt").read_text()
    require(hybrid_episode, "HybridSearchPageActionPrefix(effectLeaf)", "hybrid episode", failures)
    require(hybrid_episode, 'if (key != "enable_supported")', "hybrid enable ordering", failures)
    require(hybrid_episode, '"retry_recovers" -> {', "hybrid retry event", failures)
    for forbidden in ("Class.forName", "SearchResultsViewModel(", "aggregateStatus", "aggregateAttempts", "sections = when", "retryAvailable ="):
        forbid(hybrid_episode, forbidden, "hybrid episode", failures)
    for required in ("val sections = when", "retryAvailable =", "notice = when", "viewModel.loadHybridSearchResults()"):
        require(hybrid_page, required, "hybrid page owner", failures)
    for required in ("fun operationEffects", "fun channelEffects", "fun attemptEffects", "fun calls"):
        require(hybrid_leaf, required, "hybrid leaf log", failures)
    for required in ("SharedPreferences", "fun reopen", ".commit()"):
        require(hybrid_prefs, required, "hybrid prefs", failures)

    for task, owner in ((reading, "ReadingChallengePageActionPrefix"), (hybrid, "HybridSearchPageActionPrefix")):
        runner = (task / "evaluator/run_android_semantics.py").read_text()
        require(runner, 'episode["invokedProductionMethods"]', f"{owner} runner", failures)
        require(runner, 'episode["transitionExecuted"]', f"{owner} runner", failures)
        require(runner, 'raw_output = args.output.with_suffix(".raw.json")', f"{owner} runner", failures)
        forbid(runner, '[step["name"]', f"{owner} runner", failures)

    visible = (migrations / "tools/prepare_visible_scaffold.py").read_text()
    hidden = (migrations / "tools/prepare_agent_harness.py").read_text()
    require(visible, 'source_dir.mkdir(parents=True, exist_ok=True)', "visible scaffold", failures)
    forbid(visible, "shutil.copy", "visible scaffold", failures)
    forbid(visible, ".unlink(", "visible scaffold", failures)
    require(hidden, "candidate_production_roots(project)", "hidden source collector", failures)
    require(hidden, 'candidate source root escapes app directory', "hidden source collector", failures)
    forbid(hidden, 'source = project / "app/src/main"', "hidden source collector", failures)

    legacy = list((reading / "android/shared/evaluator").rglob("*.kt")) + list((hybrid / "android/shared/evaluator").rglob("*.kt"))
    if legacy:
        failures.append("detached evaluator Kotlin remains: " + ", ".join(str(path) for path in legacy))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    failures = audit(args.root.resolve())
    if failures:
        print("\n".join(f"FAIL: {failure}" for failure in failures))
        return 1
    print("Android runtime harness audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
