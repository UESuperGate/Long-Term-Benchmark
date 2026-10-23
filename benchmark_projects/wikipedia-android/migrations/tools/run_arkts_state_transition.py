#!/usr/bin/env python3
"""Score evaluator-owned API23 ArkUI state-transition episodes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any


DEFAULT_HDC = "/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc"
DEFAULT_TARGET = "127.0.0.1:10178"
MARKER = "LTB_RUNTIME:"
CHUNK_MARKER = "LTB_RUNTIME_CHUNK:"


def contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains(actual[key], value) for key, value in expected.items()
        )
    return actual == expected


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hdc(binary: str, target: str, *parts: str, timeout: int = 30,
        check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [binary, "-t", target, *parts], text=True, capture_output=True,
        timeout=timeout, check=check,
    )


def list_targets(binary: str) -> list[str]:
    run = subprocess.run(
        [binary, "list", "targets"], text=True, capture_output=True,
        timeout=30, check=True,
    )
    return [line.strip() for line in run.stdout.splitlines() if line.strip() and line.strip() != "[Empty]"]


def bundle_name(project: Path) -> str:
    path = project / "AppScope/app.json5"
    if not path.is_file():
        raise RuntimeError("candidate AppScope/app.json5 is missing")
    match = re.search(r"bundleName\s*:\s*['\"]([^'\"]+)", path.read_text())
    if not match:
        raise RuntimeError("bundleName missing from candidate AppScope/app.json5")
    return match.group(1)


def source_inventory(project: Path) -> list[dict[str, Any]]:
    root = project / "entry/src/main/ets"
    if not root.is_dir():
        return []
    files = []
    for path in sorted(root.rglob("*.ets")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in {"evaluator", "test"} for part in relative.parts):
            continue
        files.append({
            "path": str(path.relative_to(project)),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        })
    return files


def validate_bindings(migration: Path, contract: dict[str, Any]) -> dict[str, Any]:
    path = migration / "arkts/bindings.json"
    if not path.is_file():
        raise RuntimeError("ArkTS runtime bindings are missing")
    data = json.loads(path.read_text())
    if data.get("taskId") != contract.get("taskId"):
        raise RuntimeError("ArkTS binding taskId does not match canonical contract")
    bound = {(item.get("caseId"), item.get("traceDigest")) for item in data.get("cases", [])}
    canonical = {(item.get("caseId"), item.get("traceDigest")) for item in contract.get("cases", [])}
    if bound != canonical:
        raise RuntimeError("ArkTS bindings do not exactly cover canonical caseId/traceDigest identities")
    if data.get("observationMode") != "runtime_state_transition":
        raise RuntimeError("ArkTS bindings are not runtime state-transition bindings")
    return data


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for nested in value.values() for text in flatten_strings(nested)]
    if isinstance(value, list):
        return [text for nested in value for text in flatten_strings(nested)]
    return [value] if isinstance(value, str) else []


def effect_absence(expected: dict[str, Any], effects: list[dict[str, Any]]) -> bool:
    observed_tokens = set(flatten_strings(effects))
    return all(token not in observed_tokens for token in expected.get("absentEffects", []))


def exact_projection(case: dict[str, Any], observed: dict[str, Any]) -> bool:
    observed = object_value(observed)
    required = case["expected"]
    projection = {
        "state": required.get("state", {}),
        "persistence": required.get("persistence", {}),
        "effects": required.get("effects", []),
    }
    return contains(observed, projection) and effect_absence(required, list_value(observed.get("effects")))


def value_at(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def explore_invariants(key: str, before: dict[str, Any], after: dict[str, Any],
                       effects: list[dict[str, Any]]) -> list[bool]:
    prior = object_value(before.get("state"))
    state = object_value(after.get("state"))
    prior_persistence = object_value(before.get("persistence"))
    persistence = object_value(after.get("persistence"))
    effects = [item for item in list_value(effects) if isinstance(item, dict)]
    if key == "personalized_preference_restored":
        return [
            prior_persistence.get("homePreference") == "PERSONALIZED",
            state.get("selectedTab") == "FOR_YOU" and prior.get("selectedTab") == "COMMUNITY",
            effects == [{"name": "loadForYouContent", "attempt": 1, "language": "en"}],
        ]
    if key == "switch_tab_lazy_load_preserves_community":
        return [
            prior.get("community") == state.get("community"),
            prior.get("selectedTab") == "COMMUNITY" and state.get("selectedTab") == "FOR_YOU" and len(effects) == 1,
            value_at(state, "community", "cards") == value_at(prior, "community", "cards"),
        ]
    if key == "community_initial_retry_same_day":
        return [
            len(effects) == 1 and effects[0].get("date") == "2026-05-28",
            value_at(prior, "community", "phase") == "error" and value_at(state, "community", "phase") == "content",
            value_at(state, "community", "error") is None and len(value_at(state, "community", "cards") or []) == 2,
        ]
    if key == "community_inline_retry_preserves_content":
        prior_cards = value_at(prior, "community", "cards") or []
        cards = value_at(state, "community", "cards") or []
        return [
            cards[:len(prior_cards)] == prior_cards,
            len(effects) == 1 and effects[0].get("logicalAge") == 1 and effects[0].get("date") == "2026-05-27",
            bool(effects) and effects[0].get("attemptForLogicalAge") == 2 and cards.count("DAY_HEADER:1") == 1,
        ]
    if key == "unavailable_language_falls_back":
        return [
            state.get("activeLanguage") in list_value(prior.get("configuredLanguages")),
            value_at(state, "community", "language") == "en" and value_at(state, "community", "phase") == "loading",
            prior.get("forYou") == state.get("forYou"),
        ]
    if key == "foryou_same_day_cache_restored_and_filtered":
        modules = value_at(state, "forYou", "modules") or []
        cards = value_at(modules[0], "cards") if modules and isinstance(modules[0], dict) else []
        return [
            object_value(prior_persistence.get("forYouCache")).get("date") == persistence.get("cacheDate") and persistence.get("cacheLanguage") == "en",
            "Ada_Lovelace" not in cards and persistence.get("hiddenCards") == ["Ada_Lovelace"],
            len(modules) == 1 and cards == ["Grace_Hopper"],
        ]
    if key == "interest_edit_refreshes_foryou":
        return [
            persistence.get("interestArticles") == ["en:Ada_Lovelace"],
            any(effect.get("name") == "activityResult" and effect.get("value") == 100 for effect in effects),
            value_at(prior, "interestEditor", "interestsUpdated") is True and any(effect.get("name") == "refreshForYouContent" for effect in effects),
        ]
    if key == "unchanged_interest_edit_is_noop":
        return [
            value_at(prior, "interestEditor", "initialSelections") == value_at(prior, "interestEditor", "currentSelections"),
            effects == [{"name": "finishPersonalization", "result": "RESULT_OK"}],
            state.get("forYouModules") == prior.get("forYouModules") and persistence.get("forYouCacheUnchanged") is True,
        ]
    if key == "foryou_initial_retry_same_batch":
        return [
            prior.get("forYouError") == "IOException" and prior.get("forYouPhase") == "error",
            effects and effects[0].get("batch") == 0 and effects[0].get("attempt") == 2,
            state.get("forYouPhase") == "content" and state.get("communityPhase") == prior.get("communityPhase"),
        ]
    return [
        set(list_value(persistence.get("hiddenModules"))) == {"BASED_ON_INTEREST", "BECAUSE_YOU_READ", "CONTINUE_READING"},
        state.get("forYouEmptyState") == "ALL_MODULES_HIDDEN" and state.get("forYouVisibleModules") == [],
        state.get("manageModulesDestination") == "FOR_YOU_MODULES",
        state.get("forYouBackingModulesPresent") is True,
    ]


def saved_invariants(key: str, before: dict[str, Any], after: dict[str, Any],
                     effects: list[dict[str, Any]]) -> list[bool]:
    prior = object_value(before.get("state"))
    state = object_value(after.get("state"))
    prior_persistence = object_value(before.get("persistence"))
    persistence = object_value(after.get("persistence"))
    effects = [item for item in list_value(effects) if isinstance(item, dict)]
    if key == "all_articles_deduplicates_memberships":
        rows = [row for row in list_value(state.get("articleRows")) if isinstance(row, dict)]
        return [
            {row.get("article") for row in rows} == {"en:Ada_Lovelace", "en:Paris", "fr:Paris"},
            next((row.get("containingCollections") for row in rows if row.get("article") == "en:Ada_Lovelace"), None) == ["Saved", "People"],
            len(list_value(prior.get("roomLists"))) == 3 and effects == [{"name": "collectListsWithPagesFlow"}],
        ]
    if key == "collections_tab_uses_own_sort_and_excludes_default":
        return [
            state.get("sortMode") == 0 and persistence.get("articleSortMode") == 1,
            persistence.get("collectionSortMode") == 0 and persistence.get("articleSortMode") == 1,
            state.get("defaultCollectionVisible") is False and prior.get("roomLists") == state.get("roomLists"),
        ]
    if key == "all_articles_search_is_debounced_and_scoped":
        return [
            state.get("searchQuery") == "cafe" and state.get("searchActive") is True,
            effects == [{"name": "debouncedContentReduction", "delayMillis": 150, "accentInsensitive": True}],
            state.get("rows") == [{"type": "article", "article": "en:Cafe", "displayTitle": "Café"}] and persistence.get("roomMembershipsUnchanged") is True,
        ]
    if key == "default_only_filter_uses_all_memberships":
        memberships = object_value(prior.get("articleMemberships"))
        return [
            memberships.get("en:Default_and_travel") == ["Saved", "Travel"],
            state.get("articleRows") == ["en:Default_only"],
            persistence.get("articleMembershipsUnchanged") is True,
        ]
    if key == "select_all_targets_visible_deduplicated_rows":
        ids = value_at(state, "selection", "selectedPageIds") or []
        visible = [row.get("id") for row in list_value(prior.get("visibleArticleRows")) if isinstance(row, dict)]
        return [ids == visible, len(ids) == len(set(ids)), 13 not in ids]
    if key == "offline_redirect_failure_saves_original_and_propagates":
        return [
            value_at(prior, "article", "apiTitle") == "Original_Title",
            effects and effects[0] == {"leaf": "redirect_metadata_http", "status": "failed", "exception": "IOException"},
            persistence.get("memberships") == {"en:Original_Title": ["Saved"]},
            [effect.get("name") for effect in effects[1:]] == ["addPagesToListIfNotExist", "roomFlowPropagation"],
        ]
    if key == "cancel_named_unsave_is_noop":
        return [
            value_at(prior, "saveSheet", "pendingConfirmation") is True and "People" in object_value(prior_persistence.get("memberships")),
            effects == [{"name": "dismissConfirmationOnly"}],
            persistence.get("memberships") == prior_persistence.get("memberships") and value_at(state, "saveSheet", "dismissed") is False,
        ]
    if key == "delete_deduplicated_article_undo_restores_memberships":
        rows = [row for row in list_value(state.get("articleRows")) if isinstance(row, dict)]
        memberships = object_value(persistence.get("memberships"))
        return [
            prior.get("visibleArticleRows") == ["en:Grace_Hopper"] and "en:Ada_Lovelace" in object_value(prior_persistence.get("memberships")),
            memberships.get("en:Ada_Lovelace") == ["Saved", "People"] and sum(row.get("article") == "en:Ada_Lovelace" for row in rows) == 1,
            memberships.get("en:Grace_Hopper") == ["Saved"],
        ]
    if key == "missing_collection_toggle_is_noop":
        return [
            value_at(prior, "queuedCollectionToggle", "title") == "People",
            all(item.get("title") != "People" for item in list_value(prior_persistence.get("roomCollections")) if isinstance(item, dict)),
            effects == [] and persistence == prior_persistence,
        ]
    rows = [row for row in list_value(value_at(state, "intermediate", "articleRows")) if isinstance(row, dict)]
    return [
        value_at(prior, "previousRefreshAttempt", "outcome") == "login_prompt" and prior.get("isRefreshing") is False,
        value_at(prior, "account", "isLoggedIn") is True and value_at(prior, "account", "isTemporary") is False,
        value_at(state, "intermediate", "isRefreshing") is True and any(effect.get("name") == "roomFlowPropagation" and effect.get("whileRefreshing") is True for effect in effects),
        sum(row.get("article") == "en:Synced_Article" for row in rows) == 1 and rows[0].get("containingCollections") == ["Saved", "Research"],
        value_at(state, "final", "isRefreshing") is False and bool(effects) and effects[-1].get("name") == "consumeReadingListSyncEvent",
    ]


def invariant_checks(task_id: str, case: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, Any]]:
    before = object_value(episode.get("before"))
    after = object_value(episode.get("after"))
    effects = list_value(object_value(episode.get("observed")).get("effects"))
    if task_id == "03_explore_feed":
        values = explore_invariants(case["key"], before, after, effects)
    else:
        values = saved_invariants(case["key"], before, after, effects)
    if len(values) != len(case["invariants"]):
        raise RuntimeError(f"invariant adapter cardinality mismatch for {case['caseId']}")
    return [
        {
            "invariant": text,
            "passed": bool(values[index]),
            "evidence": {"before": before, "after": after, "effects": effects},
        }
        for index, text in enumerate(case["invariants"])
    ]


def boundary_checks(case: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, Any]]:
    episode = object_value(episode)
    before = object_value(episode.get("before"))
    after = object_value(episode.get("after"))
    observed = object_value(episode.get("observed"))
    owner = before.get("pageOwnerId")
    methods = episode.get("invokedProductionMethods", [])
    values = [
        ("canonical given was established by the evaluator input prefix", episode.get("given") == case.get("given") and episode.get("givenEstablished") is True),
        ("canonical event identity and parameters were dispatched", episode.get("event") == case.get("event")),
        ("one mounted Index page owner supplies before, event, and after state", bool(owner) and owner == after.get("pageOwnerId") == observed.get("pageOwnerId") and episode.get("commonEntryObserved") is True),
        ("candidate feature is bound through the page-owned production store", before.get("featureAvailable") is True and after.get("featureAvailable") is True),
        ("observed state is read from the page owner after the real event", observed.get("state") == after.get("state") and episode.get("transitionExecuted") is True),
        ("Preferences was reopened and agrees with the production owner", observed.get("persistence") == after.get("persistence") == after.get("ownerPersistence") and episode.get("storageReopened") is True),
        ("the canonical event entrypoint is present in the production invocation trace", case.get("event", {}).get("name") in methods),
        ("the production path completed without an evaluator early exit", episode.get("earlyExit") is False),
    ]
    return [{"check": name, "passed": passed} for name, passed in values]


def read_episode(binary: str, target: str, bundle: str, case: dict[str, Any]) -> dict[str, Any]:
    key = case["key"]
    hdc(binary, target, "shell", "aa", "force-stop", bundle, check=False)
    hdc(binary, target, "shell", "hilog", "-r", check=False)
    start = hdc(
        binary, target, "shell", "aa", "start", "-a", "EntryAbility", "-b", bundle,
        "--ps", "caseKey", key, check=False,
    )
    if start.returncode != 0 or "successfully" not in start.stdout:
        raise RuntimeError((start.stdout + start.stderr).strip() or "ability start failed")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        logs = hdc(binary, target, "shell", "hilog", "-x", "-e", "LTB_RUNTIME", check=False)
        chunks: dict[int, str] = {}
        chunk_total: int | None = None
        for line in logs.stdout.splitlines():
            if CHUNK_MARKER not in line:
                continue
            body = line.split(CHUNK_MARKER, 1)[1].strip()
            parts = body.split(":", 3)
            if len(parts) != 4 or parts[0] != key:
                continue
            try:
                index = int(parts[1])
                total = int(parts[2])
            except ValueError:
                continue
            if total <= 0 or index < 0 or index >= total:
                continue
            if chunk_total is None or chunk_total == total:
                chunk_total = total
                chunks[index] = parts[3]
        if chunk_total is not None and len(chunks) == chunk_total:
            payload = urllib.parse.unquote("".join(chunks[index] for index in range(chunk_total)))
            try:
                episode = json.loads(payload)
            except json.JSONDecodeError:
                episode = {}
            if episode.get("caseKey") == key:
                return episode
        lines = [line for line in logs.stdout.splitlines() if MARKER in line]
        for line in reversed(lines):
            payload = urllib.parse.unquote(line.split(MARKER, 1)[1].strip())
            try:
                episode = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if episode.get("caseKey") == key:
                return episode
        time.sleep(0.25)
    raise RuntimeError(f"API23 page-owner episode timed out for {case['caseId']}")


def unavailable_rows(contract: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    return [
        {
            "caseId": case["caseId"], "key": case["key"],
            "traceDigest": case["traceDigest"], "status": "not_scored",
            "observed": {}, "checkpoints": [], "invariantChecks": [],
            "runtimeBoundaryChecks": [], "reason": reason,
        }
        for case in contract["cases"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent", "control"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", default=os.environ.get("HDC_TARGET", DEFAULT_TARGET))
    parser.add_argument("--hdc", default=os.environ.get("HDC", DEFAULT_HDC))
    args = parser.parse_args()
    project = args.project.resolve()
    migration = args.migration.resolve()
    output = args.output.resolve()
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    sources = source_inventory(project)
    haps = sorted((project / "entry/build").rglob("*.hap")) if (project / "entry/build").is_dir() else []
    hap = haps[-1] if haps else None
    rows: list[dict[str, Any]] = []
    episodes: dict[str, Any] = {}
    error = ""
    api_level: int | None = None
    software_version = ""
    bundle = ""
    installed = False
    binding_variant = ""
    lock_name = hashlib.sha256(args.target.encode()).hexdigest()[:16]
    lock_path = Path(f"/tmp/ltb-arkts-device-{lock_name}")
    lock_handle = lock_path.open("a+")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    try:
        bindings = validate_bindings(migration, contract)
        binding_variant = str(bindings.get("bindingVariant", ""))
        if hap is None:
            raise RuntimeError("API23 HAP is missing; candidate binding/build is unavailable")
        if args.target not in list_targets(args.hdc):
            raise RuntimeError(f"HDC target {args.target} is not connected")
        api_level = int(hdc(args.hdc, args.target, "shell", "param", "get", "const.ohos.apiversion").stdout.strip())
        if api_level != 23:
            raise RuntimeError(f"expected API 23 device, found API {api_level}")
        software_version = hdc(
            args.hdc, args.target, "shell", "param", "get", "const.product.software.version"
        ).stdout.strip()
        bundle = bundle_name(project)
        install = hdc(args.hdc, args.target, "install", "-r", str(hap), timeout=90, check=False)
        if install.returncode != 0 or "successfully" not in install.stdout:
            raise RuntimeError((install.stdout + install.stderr).strip() or "HAP install failed")
        installed = True
        for case in contract["cases"]:
            try:
                episode = object_value(read_episode(args.hdc, args.target, bundle, case))
                episodes[case["caseId"]] = episode
                invariants = invariant_checks(contract["taskId"], case, episode)
                runtime = boundary_checks(case, episode)
                projection = exact_projection(case, object_value(episode.get("observed")))
                passed = projection and all(item["passed"] for item in invariants) and all(
                    item["passed"] for item in runtime
                )
                rows.append({
                    "caseId": case["caseId"], "key": case["key"],
                    "traceDigest": case["traceDigest"],
                    "status": "pass" if passed else "fail",
                    "productionSources": sources,
                    "invokedProductionMethods": episode.get("invokedProductionMethods", []),
                    "checkpoints": [
                        {"label": "given", "state": episode.get("given")},
                        {"label": "before", "state": episode.get("before")},
                        {"label": "event", "state": episode.get("event")},
                        {"label": "after", "state": episode.get("after")},
                    ],
                    "observed": episode.get("observed", {}),
                    "projectionMatched": projection,
                    "invariantChecks": invariants,
                    "runtimeBoundaryChecks": runtime,
                    "transitionExecuted": episode.get("transitionExecuted") is True,
                    "deviceEvidence": {
                        "serial": args.target, "apiLevel": api_level,
                        "softwareVersion": software_version,
                        "entryAbility": "EntryAbility", "surface": "ArkUI Index page",
                    },
                })
            except (KeyError, IndexError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
                rows.append({
                    "caseId": case["caseId"], "key": case["key"],
                    "traceDigest": case["traceDigest"], "status": "not_scored",
                    "observed": {}, "checkpoints": [], "invariantChecks": [],
                    "runtimeBoundaryChecks": [], "reason": str(failure),
                })
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
        error = str(failure)
        rows = unavailable_rows(contract, error)
    finally:
        if installed:
            hdc(args.hdc, args.target, "shell", "aa", "force-stop", bundle, check=False)
            hdc(args.hdc, args.target, "uninstall", bundle, check=False)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()

    def count(status: str) -> int:
        return sum(row["status"] == status for row in rows)

    artifact = [] if hap is None else [{
        "path": str(hap.relative_to(project)), "sha256": sha256(hap), "bytes": hap.stat().st_size,
    }]
    report = {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "platform": "arkts",
        "role": args.role,
        "observationMode": "runtime_state_transition",
        "runtime": "api23_entryability_arkui_page_owner",
        "codeGeneration": {"passed": None, "changedProductionFiles": []},
        "compile": {
            "passed": hap is not None,
            "command": ["hvigorw", "--mode", "module", "-p", "product=default", "-p", "module=entry@default", "assembleHap", "--no-daemon"],
            "artifacts": artifact,
        },
        "semantic": {
            "passed": count("pass"), "failed": count("fail"),
            "notScored": count("not_scored"), "total": len(rows), "cases": rows,
        },
        "diagnostics": {
            "adapter": "ready" if not error and count("not_scored") == 0 else "unavailable",
            "transport": "hdc_entryability_hilog",
            "bindingVariant": binding_variant,
            "deviceSerial": args.target,
            "deviceApi": api_level,
            "deviceSoftwareVersion": software_version,
            "deviceLock": str(lock_path),
            "runtimeCompile": {"passed": hap is not None},
            "sourceObserver": False,
            "roleAffectsVerdict": False,
            "error": error or None,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    raw = {
        "schemaVersion": 1, "taskId": contract["taskId"], "project": str(project),
        "target": args.target, "apiLevel": api_level, "softwareVersion": software_version,
        "episodes": episodes, "error": error or None,
    }
    raw_path = output.with_name(output.stem + ".raw.json")
    raw_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
    return 0 if not error and count("not_scored") == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
