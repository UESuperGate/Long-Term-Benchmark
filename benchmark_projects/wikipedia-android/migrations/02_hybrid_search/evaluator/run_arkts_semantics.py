#!/usr/bin/env python3
"""Install the API 23 ArkUI app and score page-triggered hybrid-search episodes."""

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


HDC = os.environ.get("HDC", "/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc")
TARGET = os.environ.get("HDC_TARGET", "127.0.0.1:10178")
MARKER = "LTB_RUNTIME:"


def contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hdc(*parts: str, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([HDC, "-t", TARGET, *parts], text=True, capture_output=True, timeout=timeout, check=check)


def bundle_name(project: Path) -> str:
    text = (project / "AppScope/app.json5").read_text()
    match = re.search(r"bundleName\s*:\s*['\"]([^'\"]+)", text)
    if not match:
        raise RuntimeError("bundleName missing from AppScope/app.json5")
    return match.group(1)


def checks(case: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, Any]]:
    before, after, observed = episode["before"], episode["after"], episode["observed"]
    state, prior = after.get("state", {}), before.get("state", {})
    effects = observed.get("effects", [])
    key = case["key"]
    if key == "enable_supported":
        values = [state.get("query") == prior.get("query"), effects == []]
    elif key == "concurrent_dispatch":
        values = [{item.get("leaf") for item in effects} == {"lexical_http", "semantic_http"}, state.get("phase") == "loading"]
    elif key == "both_sources_lexical_first":
        values = [state.get("lexicalTitles") == ["Paris", "Paris,_Texas"], all("#" in title for title in state.get("semanticTitles", [])), state.get("sections") == ["lexical", "semantic"]]
    elif key == "both_sources_semantic_first":
        values = [bool(state.get("lexicalTitles")) and bool(state.get("semanticTitles")), state.get("sections") == ["semantic", "lexical"]]
    elif key == "lexical_failure_fallback":
        values = [state.get("semanticTitles") == ["History_of_Paris#Origins"], state.get("phase") == "success"]
    elif key == "semantic_failure_fallback":
        values = [state.get("lexicalTitles") == ["Paris"] and state.get("semanticTitles") == [], state.get("sections") == ["lexical"]]
    elif key == "both_fail":
        values = [state.get("phase") == "error" and not state.get("lexicalTitles") and not state.get("semanticTitles"), state.get("query") == "Paris"]
    elif key == "retry_recovers":
        values = [prior.get("phase") == "error" and state.get("phase") == "success", [item.get("attempt") for item in effects] == [2, 2]]
    elif key == "feedback_mapping":
        values = [state.get("semanticTitles") == prior.get("semanticTitles"), bool(effects) and effects[0].get("payload", {}).get("position") == 1]
    else:
        values = [state.get("query") == prior.get("query"), after.get("persistence", {}).get("hybridEnabled") is False]
    return [{
        "invariant": text,
        "passed": values[index],
        "evidence": {"before": before, "after": after, "effects": effects},
    } for index, text in enumerate(case["invariants"])]


def boundary_checks(episode: dict[str, Any]) -> list[dict[str, Any]]:
    before, after, observed = episode["before"], episode["after"], episode["observed"]
    calls = observed.get("leafCalls", [])
    owner = before.get("pageOwnerId")
    url_checks = []
    for call in calls:
        parsed = urllib.parse.urlparse(call.get("url", ""))
        query = urllib.parse.parse_qs(parsed.query)
        leaf = call.get("leaf")
        if leaf == "semantic_http":
            url_checks.append(parsed.netloc == "semantic-search.wmcloud.org" and
                              query.get("query") == ["Paris"] and query.get("k") == ["3"] and
                              query.get("table") == ["frwiki_sections"] and
                              query.get("include_text") == ["true"])
        else:
            expected_mode = "prefix" if leaf == "prefix_http" else "text"
            url_checks.append(parsed.netloc == "fr.wikipedia.org" and
                              query.get("action") == ["query"] and query.get("format") == ["json"] and
                              query.get("gsrwhat") == [expected_mode] and query.get("gsrsearch") == ["Paris"])
    effects = observed.get("effects", [])
    http_effects_backed = all(
        effect.get("leaf") not in {"prefix_http", "fulltext_http", "lexical_http", "semantic_http"} or
        (effect.get("leaf") == "semantic_http" and any(call.get("leaf") == "semantic_http" for call in calls)) or
        (effect.get("leaf") in {"prefix_http", "fulltext_http"} and
         any(call.get("leaf") == effect.get("leaf") for call in calls)) or
        (effect.get("leaf") == "lexical_http" and
         any(call.get("leaf") in {"prefix_http", "fulltext_http"} for call in calls))
        for effect in effects
    )
    semantic_mapping = not after.get("state", {}).get("semanticTitles") or (
        any(call.get("leaf") == "semantic_http" and call.get("status") == "completed" for call in calls) and
        all("#" in title for title in after["state"]["semanticTitles"])
    )
    values = [
        ("one mounted Index owner supplies before, event, and after state",
         bool(owner) and owner == after.get("pageOwnerId") == observed.get("pageOwnerId")),
        ("observed state is read from the page-owned HybridSearchPageStore",
         observed.get("state") == after.get("state")),
        ("every controlled transport call has the production HttpSearchLeaf URL mapping",
         all(url_checks)),
        ("reported HTTP effects are backed by controlled transport call records", http_effects_backed),
        ("semantic transport payloads are mapped to section-qualified titles by HttpSearchLeaf", semantic_mapping),
    ]
    return [{"check": name, "passed": passed} for name, passed in values]


def read_episode(bundle: str, key: str) -> dict[str, Any]:
    hdc("shell", "aa", "force-stop", bundle, check=False)
    hdc("shell", "hilog", "-r")
    start = hdc("shell", "aa", "start", "-a", "EntryAbility", "-b", bundle, "--ps", "caseKey", key, check=False)
    if start.returncode != 0 or "successfully" not in start.stdout:
        raise RuntimeError((start.stdout + start.stderr).strip() or "ability start failed")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        logs = hdc("shell", "hilog", "-x", "-e", "LTB_RUNTIME", check=False)
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
    raise RuntimeError(f"device observer timed out for {key}")


def unavailable_rows(contract: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    return [{
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [], "reason": reason,
    } for case in contract["cases"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.project = args.project.resolve()
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    haps = sorted((args.project / "entry/build").rglob("*.hap"))
    hap = haps[-1] if haps else None
    production = sorted(path for path in (args.project / "entry/src/main/ets").rglob("*.ets") if "/evaluator/" not in str(path))
    sources = [{"path": str(path.relative_to(args.project)), "sha256": sha256(path)} for path in production]
    rows: list[dict[str, Any]] = []
    error = ""
    api_level = None
    bundle = ""
    installed = False
    lock_name = hashlib.sha256(TARGET.encode()).hexdigest()[:16]
    lock_handle = open(f"/tmp/ltb-arkts-device-{lock_name}", "a+")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    if hap is None:
        error = "API23 HAP is missing; run buildCommand before semanticCommand"
    else:
        try:
            targets = hdc("list", "targets").stdout.splitlines()
            if TARGET not in [value.strip() for value in targets]:
                raise RuntimeError(f"HDC target {TARGET} is not connected")
            api_level = int(hdc("shell", "param", "get", "const.ohos.apiversion").stdout.strip())
            if api_level != 23:
                raise RuntimeError(f"expected API 23 device, found API {api_level}")
            bundle = bundle_name(args.project)
            install = hdc("install", "-r", str(hap), timeout=90, check=False)
            if install.returncode != 0 or "successfully" not in install.stdout:
                raise RuntimeError((install.stdout + install.stderr).strip() or "HAP install failed")
            installed = True
            for case in contract["cases"]:
                try:
                    episode = read_episode(bundle, case["key"])
                    invariant_checks = checks(case, episode)
                    runtime_checks = boundary_checks(episode)
                    passed = contains(episode["observed"], case["expected"]) and \
                        all(row["passed"] for row in invariant_checks) and \
                        all(row["passed"] for row in runtime_checks)
                    rows.append({
                        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                        "status": "pass" if passed else "fail", "productionSources": sources,
                        "invokedProductionMethods": [step["name"] for step in case.get("setup", [])] + [case["event"]["name"]],
                        "checkpoints": [{"label": "before", "state": episode["before"]}, {"label": "after", "state": episode["after"]}],
                        "observed": episode["observed"], "invariantChecks": invariant_checks, "transitionExecuted": True,
                        "runtimeBoundaryChecks": runtime_checks,
                        "deviceEvidence": {"serial": TARGET, "apiLevel": api_level, "entryAbility": "EntryAbility", "surface": "ArkUI"},
                    })
                except (RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
                    rows.append({
                        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                        "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [], "reason": str(failure),
                    })
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
            error = str(failure)
        finally:
            if installed:
                hdc("shell", "aa", "force-stop", bundle, check=False)
                hdc("uninstall", bundle, check=False)
    if error:
        rows = unavailable_rows(contract, error)
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    lock_handle.close()
    count = lambda status: sum(row["status"] == status for row in rows)
    report = {
        "schemaVersion": 1, "taskId": contract["taskId"], "platform": "arkts", "role": args.role,
        "observationMode": "runtime_state_transition", "runtime": "api23_entryability_arkui_device",
        "codeGeneration": {"passed": None, "changedProductionFiles": []},
        "compile": {"passed": hap is not None, "command": ["hvigorw", "--mode", "module", "-p", "product=default", "-p", "module=entry@default", "assembleHap", "--no-daemon"],
                    "artifacts": [] if hap is None else [{"path": str(hap.relative_to(args.project)), "sha256": sha256(hap), "bytes": hap.stat().st_size}]},
        "semantic": {"passed": count("pass"), "failed": count("fail"), "notScored": count("not_scored"), "total": len(rows), "cases": rows},
        "diagnostics": {"adapter": "ready" if not error and count("not_scored") == 0 else "unavailable", "transport": "hdc_entryability_hilog",
                        "deviceSerial": TARGET, "deviceApi": api_level, "runtimeCompile": {"passed": hap is not None}, "sourceObserver": False},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if not error and count("not_scored") == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
