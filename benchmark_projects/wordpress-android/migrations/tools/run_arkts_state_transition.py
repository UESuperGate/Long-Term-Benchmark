#!/usr/bin/env python3
"""Score WordPress focused ArkTS candidates from API23 page-owner episodes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


DEFAULT_HDC = "/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc"
DEFAULT_TARGET = "127.0.0.1:10178"
MARKER = "LTB_RUNTIME:"


def run(argv: list[str], *, check: bool = True, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, text=True, encoding="utf-8", errors="replace", capture_output=True,
        check=check, timeout=timeout,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "passed": sum(row["status"] == "pass" for row in rows),
        "failed": sum(row["status"] == "fail" for row in rows),
        "notScored": sum(row["status"] == "not_scored" for row in rows),
        "total": len(rows),
    }


def bundle_name(project: Path) -> str:
    path = project / "AppScope/app.json5"
    if not path.is_file():
        raise RuntimeError("candidate AppScope/app.json5 is missing")
    match = re.search(r'"bundleName"\s*:\s*"([^"]+)"', path.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError("candidate bundleName is unavailable")
    return match.group(1)


def find_hap(project: Path) -> Path:
    haps = sorted((project / "entry/build").rglob("*.hap")) if (project / "entry/build").is_dir() else []
    if len(haps) != 1:
        raise RuntimeError(f"expected exactly one candidate HAP, found {len(haps)}")
    return haps[0]


def source_inventory(project: Path) -> list[dict[str, Any]]:
    root = project / "entry/src/main/ets"
    if not root.is_dir():
        raise RuntimeError("candidate production source root is missing")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.ets")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in {"evaluator", "test"} for part in relative.parts):
            continue
        rows.append({
            "path": str(path.relative_to(project)), "sha256": sha256(path), "bytes": path.stat().st_size,
        })
    if not rows:
        raise RuntimeError("candidate production source inventory is empty")
    return rows


def validate_bindings(migration: Path, contract: dict[str, Any]) -> dict[str, Any]:
    path = migration / "arkts/bindings.json"
    if not path.is_file():
        raise RuntimeError("ArkTS runtime bindings are missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("taskId") != contract.get("taskId"):
        raise RuntimeError("binding taskId does not match canonical contract")
    if data.get("observationMode") != "runtime_state_transition":
        raise RuntimeError("binding is not runtime_state_transition")
    bound = {(row.get("caseId"), row.get("traceDigest")) for row in data.get("cases", [])}
    canonical = {(row.get("caseId"), row.get("traceDigest")) for row in contract.get("cases", [])}
    if bound != canonical:
        raise RuntimeError("binding does not exactly cover canonical caseId/traceDigest identities")
    return data


def effect_names(effects: list[dict[str, Any]]) -> set[str]:
    return {str(effect.get("name")) for effect in effects if effect.get("name") is not None}


def exact_observation(case: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected = case["expected"]
    effects = observed.get("effects")
    if observed.get("state") != expected.get("state") or effects != expected.get("effects", []):
        return False
    names = effect_names(effects if isinstance(effects, list) else [])
    return all(name not in names for name in expected.get("absentEffects", []))


def unique_group_ids(state: dict[str, Any]) -> list[int]:
    return [item for section in state.get("sections", []) for item in section.get("localIds", [])]


def site_invariants(key: str, case: dict[str, Any], episode: dict[str, Any]) -> list[bool]:
    state = episode["after"]["state"]
    effects = episode["observed"]["effects"]
    methods = episode.get("invokedProductionMethods", [])
    given = case["given"]
    ids = unique_group_ids(state)
    sections = {section["name"]: section["localIds"] for section in state.get("sections", [])}
    if key == "grouped_open":
        return [len(ids) == len(set(ids)) == len(given["storeSites"]), not set(sections.get("pinned", [])) & set(sections.get("recent", [])), state.get("selectedLocalId") == given.get("selectedLocalId")]
    if key == "search_clear":
        return ["enterSearchQuery" in methods, ids == [10, 11, 12], not set(sections.get("pinned", [])) & set(sections.get("recent", []))]
    if key == "pin_mode_row_noop":
        return ["enterPinMode" in methods, state.get("actionMode") == "pin" and state.get("activeLocalId") == 20, "writePinnedPreferences" not in effect_names(effects)]
    if key == "pin_persist_reopen":
        return [all(name in methods for name in ("enterPinMode", "togglePin", "closePicker")), state.get("persistedPinnedLocalIds") == [22], ids.count(22) == 1 and 22 not in sections.get("recent", [])]
    if key == "unpin_regroup":
        return [31 in sections.get("recent", []), len(ids) == len(set(ids)), state.get("actionMode") == "pin"]
    if key == "select_recent_propagation":
        recent = sections.get("recent") or [None]
        return ["selectSite" in methods, recent[0] == 43, not set(sections.get("pinned", [])) & set(sections.get("recent", []))]
    if key == "refresh_failure_retry":
        return ["manualRefresh" in methods and state.get("refreshing") is False, ids == [51, 52, 53, 54], "selectSite" not in effect_names(effects)]
    if key == "wpcom_long_press_noop":
        return [effects == [], state.get("visibleLocalIds") == [60, 61], state.get("activeLocalId") == given.get("activeLocalId")]
    if key == "restore_search_pin_mode":
        evidence = episode["runtimeEvidence"]
        return [evidence.get("pageRecreated") is True and state.get("searchQuery") == "needle" and state.get("actionMode") == "pin", not effect_names(effects) & {"writePinnedPreferences", "writeRecentPreferences"}, state.get("rowSelectionEnabled") is False]
    return [state.get("selectionOutcome") == {"status": "selected", "localId": 82}, state.get("pinEditingVisible") is False and state.get("addSiteVisible") is False, effect_names(effects) == {"writeRecentPreferences", "publishSiteSelection", "closePicker"}]


def stats_invariants(key: str, case: dict[str, Any], episode: dict[str, Any]) -> list[bool]:
    state = episode["after"]["state"]
    effects = episode["observed"]["effects"]
    names = effect_names(effects)
    methods = episode.get("invokedProductionMethods", [])
    if key == "metric_replot_persist":
        return [state.get("persistedMetric") == "visitors", state.get("chartTotal") == 700 and state.get("chartPointValues") == [300, 400], "fetchStatsForPeriod" not in names]
    if key == "hourly_fallback_restore":
        return [state.get("persistedMetric") == "visitors", state.get("selectedMetric") == "visitors", state.get("period") == "last_7_days" and state.get("chartState") == "loaded"]
    if key == "explicit_hourly_unavailable":
        return [state.get("chartState") == "unavailable", state.get("bottomStats", {}).get("state") == "loaded", state.get("persistedMetric") == "visitors"]
    if key == "bar_soft_select":
        return [state.get("committedPeriod") == "last_7_days", state.get("chartHeader") == {"current": 1000, "previous": 800, "difference": 200} and state.get("bottomValues", {}).get("views") == 1000, "fetchStatsForPeriod" not in names]
    if key == "bar_drill_commit":
        return [all(name in methods for name in ("loadPeriodData", "tapChartBucket")), state.get("selectedBar") is None, names == {"saveSiteStatsConfiguration", "fetchStatsForPeriod", "propagatePeriodToVisibleCards"}]
    if key == "future_bucket_noop":
        return [state.get("selectedBar") is None, state.get("wholePeriodAverage") == 3500, state.get("effectivePeriod") == state.get("committedPeriod") == "this_week"]
    if key == "period_origin_restore":
        evidence = episode["runtimeEvidence"]
        return [evidence.get("pageRecreated") is True and "recreateStatsSurface" in methods, state.get("restoredOrigin") == "last_30_days", state.get("canNavigateForwardAfterNavigation") is False]
    if key == "cached_revalidation_recovery":
        given = case["given"]
        return ["backgroundRevalidation" in methods, set(given.get("requestIdentity", {})) == {"surface", "siteId", "today", "period", "variant"}, state.get("views") == 7100 and state.get("needsRevalidation") is False]
    if key == "pull_refresh_inflight_isolation":
        return [effects and effects[0].get("name") == "invalidateCachedStatsBeforeRefresh", "storeOlderRequestResult" not in names, state.get("refreshingAfterCompletion") is False and state.get("visibleViews") == 7200]
    regions = state.get("regions", {})
    return [regions.get("isPlanGated") is True and case["given"].get("userCanViewStats") is True, not (regions.get("isPlanGated") and regions.get("isAuthError")), state.get("countriesStatePreserved") == case["given"].get("countriesState")]


def invariant_checks(task_id: str, case: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, Any]]:
    values = site_invariants(case["key"], case, episode) if task_id == "03_site_picker" else stats_invariants(case["key"], case, episode)
    if len(values) != len(case["invariants"]):
        raise RuntimeError(f"invariant adapter cardinality mismatch for {case['caseId']}")
    return [
        {"invariant": name, "passed": bool(values[index]), "evidence": {"before": episode["before"], "after": episode["after"], "effects": episode["observed"]["effects"]}}
        for index, name in enumerate(case["invariants"])
    ]


def collect_episode(hdc: str, target: str, bundle: str, key: str) -> dict[str, Any]:
    token = uuid.uuid4().hex
    prefix = f"{MARKER}{token}:"
    run([hdc, "-t", target, "shell", "aa", "force-stop", bundle], check=False)
    run([hdc, "-t", target, "shell", "hilog", "-r"], check=False)
    started = run([
        hdc, "-t", target, "shell", "aa", "start", "-a", "EntryAbility", "-b", bundle, "-m", "entry",
        "--ps", "semanticCase", key, "--ps", "semanticToken", token,
    ], check=False)
    if started.returncode != 0 or "successfully" not in (started.stdout + started.stderr):
        raise RuntimeError(f"ability start failed: {(started.stdout + started.stderr).strip()}")
    deadline = time.monotonic() + 20
    last_log = ""
    while time.monotonic() < deadline:
        time.sleep(0.35)
        captured = run([hdc, "-t", target, "shell", "hilog", "-x", "-T", "LTBObserver"], check=False)
        last_log = captured.stdout + captured.stderr
        chunks: dict[int, str] = {}
        total: int | None = None
        for line in last_log.splitlines():
            marker_at = line.find(prefix)
            if marker_at < 0:
                continue
            match = re.match(r"(\d+):(\d+):(.*)$", line[marker_at + len(prefix):])
            if match is None:
                continue
            chunks[int(match.group(1))] = match.group(3)
            total = int(match.group(2))
        if total is not None and len(chunks) == total:
            payload = json.loads("".join(chunks[index] for index in range(total)))
            if payload.get("key") != key:
                raise RuntimeError("runtime payload key differs from requested case")
            episode = json.loads(payload["episodeJson"])
            if episode.get("caseKey") != key:
                raise RuntimeError("runtime episode case key differs from requested case")
            return episode
    diagnostic = "\n".join(line for line in last_log.splitlines() if "LTB" in line)[-4000:]
    raise RuntimeError(f"API23 page-owner episode timed out for {key}; {diagnostic}")


def unavailable_rows(contract: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    return [{
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": None, "invariantChecks": [], "diagnostic": reason,
    } for case in contract["cases"]]


def write_report(output: Path, report: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    contract = json.loads((migration / "canonical/transitions.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    bundle = ""
    hap: Path | None = None
    api_level: int | None = None
    software_version = ""
    installed = False
    error = ""
    suffix = hashlib.sha256(args.target.encode("utf-8")).hexdigest()[:16]
    legacy = Path("/tmp/long-term-benchmark-arkts-device.lock").open("a+")
    target_lock = Path(f"/tmp/ltb-arkts-device-{suffix}").open("a+")
    fcntl.flock(legacy.fileno(), fcntl.LOCK_EX)
    fcntl.flock(target_lock.fileno(), fcntl.LOCK_EX)
    try:
        validate_bindings(migration, contract)
        sources = source_inventory(project)
        hap = find_hap(project)
        listed = run([args.hdc, "list", "targets"]).stdout.split()
        if args.target not in listed:
            raise RuntimeError(f"HDC target {args.target} is not connected")
        api_text = run([args.hdc, "-t", args.target, "shell", "param", "get", "const.ohos.apiversion"]).stdout.strip()
        api_level = int(api_text)
        if api_level != 23:
            raise RuntimeError(f"expected OpenHarmony API23, observed {api_text!r}")
        software_version = run([args.hdc, "-t", args.target, "shell", "param", "get", "const.product.software.version"]).stdout.strip()
        bundle = bundle_name(project)
        installed_run = run([args.hdc, "-t", args.target, "install", "-r", str(hap)], check=False)
        if installed_run.returncode != 0 or "successfully" not in (installed_run.stdout + installed_run.stderr):
            raise RuntimeError(f"HAP install failed: {(installed_run.stdout + installed_run.stderr).strip()}")
        installed = True
        expected_source = "Index.SitePickerPageOwner.controller.store" if contract["taskId"] == "03_site_picker" else "Index.NewStatsPageOwner.controller.store"
        recreate_key = "restore_search_pin_mode" if contract["taskId"] == "03_site_picker" else "period_origin_restore"
        for case in contract["cases"]:
            try:
                episode = collect_episode(args.hdc, args.target, bundle, case["key"])
                evidence = episode.get("runtimeEvidence", {})
                boundary = [
                    ("canonical given is evaluator supplied", episode.get("given") == case.get("given") and episode.get("givenEstablished") is True),
                    ("canonical event identity is dispatched", episode.get("event") == case.get("event")),
                    ("Index owns the observed page controller", bool(evidence.get("pageOwnerId")) and bool(evidence.get("controllerOwnerId")) and episode.get("commonEntryObserved") is True),
                    ("observation comes from the page-owned store", evidence.get("storeSource") == expected_source),
                    ("evaluator does not write store or construct detached controller", evidence.get("evaluatorStoreWrites") == 0 and evidence.get("detachedControllers") == 0),
                    ("ArkData Preferences is reopened after the event", evidence.get("storageReopened") is True),
                    ("production event method is in invocation trace", case["event"]["name"] in episode.get("invokedProductionMethods", [])),
                    ("production path completes", episode.get("transitionExecuted") is True and episode.get("earlyExit") is False),
                ]
                if case["key"] == recreate_key:
                    boundary.append(("canonical recreation mounts a new Index owner", evidence.get("pageRecreated") is True and evidence.get("previousPageOwnerId") != evidence.get("pageOwnerId") and evidence.get("previousControllerOwnerId") != evidence.get("controllerOwnerId")))
                checks = invariant_checks(contract["taskId"], case, episode)
                observed = episode["observed"]
                passed = exact_observation(case, observed) and all(check["passed"] for check in checks) and all(value for _, value in boundary)
                rows.append({
                    "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                    "status": "pass" if passed else "fail", "productionSources": sources,
                    "productionBodies": episode.get("invokedProductionMethods", []),
                    "checkpoints": [{"label": "given", "state": case["given"]}, {"label": "before", "state": episode["before"]}, {"label": "event", "state": case["event"]}, {"label": "after", "state": episode["after"]}],
                    "observed": observed, "effects": observed.get("effects", []),
                    "invariantChecks": checks,
                    "runtimeBoundaryChecks": [{"check": name, "passed": bool(value)} for name, value in boundary],
                    "runtimeEvidence": evidence,
                })
            except Exception as case_error:
                rows.append({
                    "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                    "status": "not_scored", "productionSources": sources, "observed": None,
                    "invariantChecks": [], "runtimeBoundaryChecks": [], "diagnostic": str(case_error),
                })
    except Exception as setup_error:
        error = str(setup_error)
        rows = unavailable_rows(contract, error)
    finally:
        if installed and bundle:
            run([args.hdc, "-t", args.target, "shell", "aa", "force-stop", bundle], check=False)
        fcntl.flock(target_lock.fileno(), fcntl.LOCK_UN)
        fcntl.flock(legacy.fileno(), fcntl.LOCK_UN)
        target_lock.close()
        legacy.close()
    semantic = summary(rows)
    report = {
        "schemaVersion": 2, "taskId": contract["taskId"], "platform": "arkts", "role": args.role,
        "observationMode": "runtime_state_transition",
        "runtime": "OpenHarmony API23 EntryAbility/ArkUI Index page-owner runtime",
        "device": {"target": args.target, "apiLevel": api_level, "softwareVersion": software_version},
        "codeGeneration": {"passed": bool(sources), "changedProductionFiles": sources},
        "compile": {"passed": hap is not None, "command": ["bash", "build.sh"],
                    "hapSha256": sha256(hap) if hap is not None else None,
                    "hapBytes": hap.stat().st_size if hap is not None else None},
        "semantic": {"summary": semantic, "cases": rows},
        "diagnostics": {
            "adapter": "api23_index_page_owner", "transport": "hdc" if not error else "unavailable",
            "productionEntryExecuted": installed, "productionPageLoaded": "pages/Index" if installed else None,
            "sourceObserver": False, "roleAffectsVerdict": False, "pageOwnershipEnforced": True,
            "binding": "ready" if not error else "unavailable", "setupError": error or None,
        },
    }
    write_report(output, report)
    return 0 if semantic["notScored"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
