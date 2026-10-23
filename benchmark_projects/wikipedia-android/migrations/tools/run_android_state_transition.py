#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


ADB = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb"
DEVICE = os.environ.get("ANDROID_SERIAL", "emulator-5554")


def contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def application_id(project: Path) -> str:
    text = (project / "app/build.gradle.kts").read_text(encoding="utf-8")
    match = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("applicationId missing from app/build.gradle.kts")
    return match.group(1)


def adb(*parts: str, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(ADB), "-s", DEVICE, *parts], text=True, capture_output=True, timeout=timeout, check=check)


def encoded(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def effect_matches(actual: list[Any], expected: list[Any]) -> bool:
    remaining = list(actual)
    for item in expected:
        index = next((i for i, candidate in enumerate(remaining) if contains(candidate, item)), None)
        if index is None:
            return False
        remaining.pop(index)
    return True


def absent_effects_hold(actual: list[Any], absent: list[str]) -> bool:
    material = json.dumps(actual, sort_keys=True).lower()
    return all(name.lower() not in material for name in absent)


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _effect_names(episode: dict[str, Any]) -> list[str]:
    effects = list_value(object_value(episode.get("observed")).get("effects"))
    return [str(item.get("name", item.get("leaf", ""))) for item in effects if isinstance(item, dict)]


def invariant_values(task: str, key: str, episode: dict[str, Any]) -> list[bool]:
    if not episode.get("transitionExecuted"):
        return []
    before = object_value(episode.get("before"))
    before_state = object_value(before.get("state"))
    observed = object_value(episode.get("observed"))
    state = object_value(observed.get("state"))
    persistence = object_value(observed.get("persistence"))
    effects = list_value(observed.get("effects"))
    first_effect = object_value(effects[0]) if effects else {}
    names = _effect_names(episode)
    if task == "03_explore_feed":
        checks = {
            "personalized_preference_restored": [persistence.get("homePreference") == "PERSONALIZED", state.get("selectedTab") == "FOR_YOU", names == ["loadForYouContent"]],
            "switch_tab_lazy_load_preserves_community": [before_state.get("community") == state.get("community"), names == ["loadForYouContent"], object_value(state.get("community")).get("cards") == ["DAY_HEADER:0", "FEATURED_ARTICLE:Ada_Lovelace"]],
            "community_initial_retry_same_day": [bool(effects) and first_effect.get("date") == "2026-05-28", object_value(state.get("community")).get("phase") == "content", object_value(state.get("community")).get("error") is None],
            "community_inline_retry_preserves_content": [list_value(object_value(state.get("community")).get("cards"))[:2] == ["DAY_HEADER:0", "FEATURED_ARTICLE:Ada_Lovelace"], bool(effects) and first_effect.get("logicalAge") == 1, len(effects) == 1],
            "unavailable_language_falls_back": [state.get("activeLanguage") == "en", state.get("forYou") == before_state.get("forYou"), persistence.get("homeLanguage") == "en"],
            "foryou_same_day_cache_restored_and_filtered": [persistence.get("cacheDate") == "2026-05-28", "Ada_Lovelace" not in json.dumps(state), bool(object_value(state.get("forYou")).get("modules"))],
            "interest_edit_refreshes_foryou": [persistence.get("interestArticles") == ["en:Ada_Lovelace"], bool(effects) and first_effect.get("value") == 100, object_value(state.get("forYou")).get("phase") == "loading"],
            "unchanged_interest_edit_is_noop": [before_state.get("selectedTab") == "FOR_YOU", bool(effects) and first_effect.get("result") == "RESULT_OK", len(effects) == 1 and persistence.get("forYouCacheUnchanged") is True],
            "foryou_initial_retry_same_batch": [before_state.get("forYouError") == "IOException", bool(effects) and first_effect.get("batch") == 0, state.get("forYouModules") == ["BASED_ON_INTEREST:0"]],
            "foryou_all_modules_hidden_propagates": [persistence.get("hiddenModules") == ["BASED_ON_INTEREST", "BECAUSE_YOU_READ", "CONTINUE_READING"], state.get("forYouEmptyState") == "ALL_MODULES_HIDDEN", state.get("manageModulesDestination") == "FOR_YOU_MODULES", state.get("forYouVisibleModules") == []],
        }
        return checks.get(key, [])
    if key == "all_articles_deduplicates_memberships":
        rows = [row for row in list_value(state.get("articleRows")) if isinstance(row, dict)]
        return [len(rows) == 3,
                next((row.get("containingCollections") for row in rows if row.get("article") == "en:Ada_Lovelace"), None) == ["Saved", "People"],
                persistence.get("roomMembershipsUnchanged") is True]
    if key == "collections_tab_uses_own_sort_and_excludes_default":
        return [state.get("sortMode") == 0, persistence.get("articleSortMode") == 1 and persistence.get("collectionSortMode") == 0, state.get("defaultCollectionVisible") is False]
    if key == "all_articles_search_is_debounced_and_scoped":
        return [state.get("searchQuery") == "cafe", bool(effects) and first_effect.get("delayMillis") == 150, state.get("rows") == [{"type": "article", "article": "en:Cafe", "displayTitle": "Café"}]]
    if key == "default_only_filter_uses_all_memberships":
        return [state.get("articleRows") == ["en:Default_only"],
                "en:Default_and_travel" not in list_value(state.get("articleRows")),
                persistence.get("articleMembershipsUnchanged") is True]
    if key == "select_all_targets_visible_deduplicated_rows":
        ids = list_value(object_value(state.get("selection")).get("selectedPageIds"))
        return [ids == [11, 12], len(set(ids)) == 2, 13 not in ids]
    if key == "offline_redirect_failure_saves_original_and_propagates":
        memberships = object_value(persistence.get("memberships"))
        return [object_value(object_value(episode.get("given")).get("article")).get("apiTitle") == "Original_Title", bool(effects) and first_effect.get("exception") == "IOException", "en:Original_Title" in memberships, object_value(state.get("savedSurface")).get("articleRows") == ["en:Original_Title"]]
    if key == "cancel_named_unsave_is_noop":
        return [object_value(before_state.get("saveSheet")).get("pendingConfirmation") is True, names == ["dismissConfirmationOnly"], before.get("persistence") == persistence]
    if key == "delete_deduplicated_article_undo_restores_memberships":
        memberships = object_value(persistence.get("memberships"))
        return [before_state.get("visibleArticleRows") == ["en:Grace_Hopper"], memberships.get("en:Ada_Lovelace") == ["Saved", "People"], len(list_value(state.get("articleRows"))) == 2]
    if key == "missing_collection_toggle_is_noop":
        return [object_value(object_value(episode.get("given")).get("queuedCollectionToggle")).get("collectionId") == "observed-created-People-id", persistence.get("roomCollections") == [{"title": "Saved", "isDefault": True}], effects == []]
    if key == "login_then_refresh_retries_sync_to_completion":
        given = object_value(episode.get("given"))
        intermediate = object_value(state.get("intermediate"))
        return [object_value(given.get("previousRefreshAttempt")).get("syncStarted") is False, object_value(given.get("account")).get("isLoggedIn") is True, intermediate.get("isRefreshing") is True, len(list_value(intermediate.get("articleRows"))) == 1, object_value(state.get("final")).get("isRefreshing") is False]
    return []


def unavailable_rows(contract: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    return [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
             "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [], "reason": reason}
            for case in contract["cases"]]


def run(project: Path, migration: Path, role: str, output: Path, runner: str) -> int:
    contract = json.loads((migration / "canonical/transitions.json").read_text(encoding="utf-8"))
    app_apk = project / "app/build/outputs/apk/debug/app-debug.apk"
    test_apk = project / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
    package = application_id(project)
    test_package = f"{package}.test"
    source_root = project / "candidate-production" if role == "agent" else project / "app/src/main/upstream/kotlin"
    sources = [{"path": str(path.relative_to(project if role == "agent" else migration)), "sha256": sha256(path), "bytes": path.stat().st_size}
               for path in sorted(source_root.rglob("*.kt"))]
    rows: list[dict[str, Any]] = []
    raw_episodes: list[dict[str, Any]] = []
    error = ""
    device_api = None
    installed = False
    lock = open("/tmp/long-term-benchmark-android-device.lock", "a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    try:
        if not app_apk.is_file() or not test_apk.is_file():
            raise RuntimeError("native app or instrumentation APK is missing")
        device_api = int(adb("shell", "getprop", "ro.build.version.sdk").stdout.strip())
        if device_api != 37:
            raise RuntimeError(f"expected API 37 device, found API {device_api}")
        adb("install", "-r", "-t", str(app_apk), timeout=120)
        adb("install", "-r", "-t", str(test_apk), timeout=120)
        installed = True
        for case in contract["cases"]:
            invocation = ["shell", "am", "instrument", "-w", "-e", "caseKey", case["key"],
                          "-e", "given", encoded(case["given"]), "-e", "event", encoded(case["event"]),
                          f"{test_package}/{runner}"]
            call = adb(*invocation, timeout=60, check=False)
            if (call.returncode != 0 or "INSTRUMENTATION_CODE: 0" not in call.stdout
                    or "Process crashed" in call.stdout):
                rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                             "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [],
                             "reason": (call.stdout + call.stderr).strip() or "instrumentation failed"})
                raw_episodes.append({"caseId": case["caseId"], "instrumentation": call.stdout + call.stderr})
                continue
            episode = object_value(json.loads(adb("exec-out", "run-as", package, "cat", "files/runtime-episode.json").stdout))
            if episode.get("key") != case["key"] or episode.get("given") != case["given"] or episode.get("event") != case["event"]:
                rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                             "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [],
                             "reason": "runtime episode does not bind the requested case/given/event"})
                raw_episodes.append({"caseId": case["caseId"], "episode": episode, "instrumentation": call.stdout})
                continue
            raw_episodes.append({"caseId": case["caseId"], "episode": episode, "instrumentation": call.stdout})
            actual = object_value(episode.get("observed"))
            expected = case["expected"]
            core = (contains(actual.get("state", {}), expected.get("state", {}))
                    and contains(actual.get("persistence", {}), expected.get("persistence", {}))
                    and effect_matches(list_value(actual.get("effects")), expected.get("effects", []))
                    and absent_effects_hold(list_value(actual.get("effects")), expected.get("absentEffects", [])))
            values = invariant_values(contract["taskId"], case["key"], episode)
            invariant_checks = [{"invariant": text, "passed": values[i] if i < len(values) else False,
                                 "evidence": {"before": object_value(episode.get("before")),
                                              "after": object_value(episode.get("after")),
                                              "effects": list_value(actual.get("effects"))}}
                                for i, text in enumerate(case.get("invariants", []))]
            bound = (episode.get("givenEstablished") is True and episode.get("commonEntryObserved") is True
                     and episode.get("entryOwner") in {"ExploreActionPrefix", "SavedActionPrefix"}
                     and episode.get("storageReopened") is True and bool(episode.get("invokedProductionMethods")))
            passed = bound and episode.get("transitionExecuted") is True and core and all(item["passed"] for item in invariant_checks)
            rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                         "status": "pass" if passed else "fail", "productionSources": sources,
                         "entryOwner": episode.get("entryOwner"),
                         "invokedProductionMethods": list_value(episode.get("invokedProductionMethods")),
                         "checkpoints": [{"label": "given", "state": episode.get("given")},
                                         {"label": "before", "state": episode.get("before")},
                                         {"label": "event", "state": episode.get("event")},
                                         {"label": "after", "state": episode.get("after")}],
                         "observed": actual, "invariantChecks": invariant_checks,
                         "transitionExecuted": episode.get("transitionExecuted"), "earlyExit": episode.get("earlyExit", ""),
                         "deviceEvidence": {"serial": DEVICE, "apiLevel": device_api, "runner": runner}})
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
        error = str(failure)
        rows = unavailable_rows(contract, error)
    finally:
        if installed:
            adb("uninstall", test_package, check=False)
            adb("uninstall", package, check=False)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    count = lambda status: sum(row["status"] == status for row in rows)
    raw_output = output.with_suffix(".raw.json")
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text(json.dumps({"schemaVersion": 1, "taskId": contract["taskId"], "role": role, "episodes": raw_episodes}, indent=2) + "\n")
    report = {"schemaVersion": 1, "taskId": contract["taskId"], "platform": "android", "role": role,
              "observationMode": "runtime_state_transition", "runtime": "api37_android_instrumentation_focused_production_action_prefix",
              "codeGeneration": {"passed": None, "changedProductionFiles": []},
              "compile": {"passed": app_apk.is_file() and test_apk.is_file(), "command": ["bash", "{project}/build.sh"],
                          "artifacts": [{"path": str(path.relative_to(project)), "sha256": sha256(path), "bytes": path.stat().st_size}
                                        for path in (app_apk, test_apk) if path.is_file()]},
              "semantic": {"passed": count("pass"), "failed": count("fail"), "notScored": count("not_scored"), "total": len(rows), "cases": rows},
              "diagnostics": {"adapter": "ready" if not error else "unavailable", "transport": "adb_instrumentation",
                              "deviceSerial": DEVICE, "deviceApi": device_api, "sourceObserver": False,
                              "runtimeCompile": {"passed": app_apk.is_file() and test_apk.is_file()},
                              "rawEvidence": {"path": raw_output.name, "sha256": sha256(raw_output), "bytes": raw_output.stat().st_size}}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if not error and count("not_scored") == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", required=True)
    args = parser.parse_args()
    return run(args.project.resolve(), args.migration.resolve(), args.role, args.output.resolve(), args.runner)


if __name__ == "__main__":
    raise SystemExit(main())
