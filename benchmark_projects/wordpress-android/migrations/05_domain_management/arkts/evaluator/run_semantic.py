#!/usr/bin/env python3
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

MIGRATION = Path(__file__).resolve().parents[2]
CONTRACT_PATH = MIGRATION / "canonical/transitions.json"
DEFAULT_HDC = "/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc"
DEFAULT_TARGET = "127.0.0.1:10178"
MARKER = "LTB_RUNTIME:"


def run(argv: list[str], *, check: bool = True, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, encoding="utf-8", errors="replace", capture_output=True, check=check, timeout=timeout)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "passed": sum(row["status"] == "pass" for row in rows),
        "failed": sum(row["status"] == "fail" for row in rows),
        "notScored": sum(row["status"] == "not_scored" for row in rows),
        "total": len(rows),
    }


def bundle_name(project: Path) -> str:
    match = re.search(r'"bundleName"\s*:\s*"([^"]+)"', (project / "AppScope/app.json5").read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError("candidate bundleName is unavailable")
    return match.group(1)


def find_hap(project: Path) -> Path:
    haps = sorted((project / "entry/build").rglob("*.hap"))
    if len(haps) != 1:
        raise RuntimeError(f"expected exactly one candidate HAP, found {len(haps)}")
    return haps[0]


def source_inventory(project: Path) -> list[dict[str, Any]]:
    root = project / "entry/src/main/ets"
    rows = []
    for path in sorted(root.rglob("*.ets")):
        relative = path.relative_to(root)
        if "evaluator" in relative.parts:
            continue
        rows.append({"path": str(path.relative_to(project)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    if not rows:
        raise RuntimeError("candidate production source inventory is empty")
    return rows


def validate_bindings(contract: dict[str, Any]) -> None:
    bindings = json.loads((MIGRATION / "arkts/bindings.json").read_text(encoding="utf-8"))
    if bindings.get("taskId") != contract.get("taskId") or bindings.get("observationMode") != "runtime_state_transition":
        raise RuntimeError("ArkTS binding header does not match the canonical contract")
    expected = {(case["caseId"], case["traceDigest"]) for case in contract["cases"]}
    actual = {(case.get("caseId"), case.get("traceDigest")) for case in bindings.get("cases", [])}
    if actual != expected:
        raise RuntimeError("ArkTS bindings do not exactly cover canonical identities")


def effect_index(effects: list[dict[str, Any]], name: str) -> int:
    return next((index for index, effect in enumerate(effects) if effect.get("name") == name), -1)


def exact_observation(case: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected = case["expected"]
    if observed.get("state") != expected.get("state") or observed.get("effects") != expected.get("effects", []):
        return False
    names = {effect.get("name") for effect in observed.get("effects", [])}
    return all(name not in names for name in expected.get("absentEffects", []))


def invariant_values(case: dict[str, Any], episode: dict[str, Any]) -> list[bool]:
    key = case["key"]
    given = case["given"]
    before = episode["before"]["state"]
    state = episode["after"]["state"]
    effects = episode["observed"]["effects"]
    calls = episode["runtimeEvidence"]["backendCalls"]
    if key == "loaded_add_domain_entry":
        return [state.get("visibleDomains") == ["alpha.example", "beta.example"], state.get("listState") == "complete" and state.get("addDomainEnabled") is True, calls.get("fetchAllDomains") == 1 and calls.get("createCart") == 0]
    if key == "empty_find_domain_entry":
        return [state.get("listState") == "empty", state.get("findDomainEnabled") is True and state.get("destination") == "new_domain_search", calls.get("searchForDomains") == 0 and calls.get("createCart") == 0]
    if key == "error_retry_recovery":
        return [before.get("listState") == "error", calls.get("fetchAllDomains") == 2, state.get("visibleDomains") == ["recovered.example"]]
    if key == "filter_clear_round_trip":
        return [before.get("listState") == "filtered", state.get("beforeClear", {}).get("visibleDomains") == ["alpha.example"], calls.get("fetchAllDomains") == 1 and state.get("afterClear", {}).get("visibleDomains") == ["alpha.example", "beta.example"]]
    if key == "debounced_latest_search":
        search = next((effect for effect in effects if effect.get("name") == "searchForDomains"), {})
        return [search.get("dispatchAtMs") == 350, state.get("normalizedQuery") == "latest", calls.get("searchForDomains") == 1 and "old.example" not in state.get("visibleDomains", [])]
    if key == "purchase_mode_entry":
        proposal = state.get("selectedProposal", {})
        return [proposal.get("domain") == "chosen.example", proposal == {"productId": 42, "domain": "chosen.example", "supportsPrivacy": True}, calls.get("createCart") == 0 and state.get("purchaseUiState") == "initial"]
    if key == "cart_failure_retry":
        return [before.get("purchaseUiState") == "error_submitting_cart", calls.get("createCart") == 2 and state.get("checkoutDomain") == "retry.example", effect_index(effects, "openDomainCheckout") >= 0]
    if key == "checkout_cancel":
        return ["domain" in given["checkout"], state.get("registrationOutcome") == "canceled" and state.get("purchaseScreenOpen") is False, effect_index(effects, "recordDomainPurchaseCompleted") < 0]
    if key == "checkout_success":
        return ["domain" in given["checkout"], effect_index(effects, "recordDomainPurchaseCompleted") == 0 and effect_index(effects, "openDomainManagement") == 1, calls.get("createCart") == 0]
    return [effect_index(effects, "redirectToExternalBrowser") >= 0, state.get("requestedUrlLoadedInContainedWebView") is False, state.get("containedWebViewUrl") == given["detailsWebView"]["currentUrl"]]


def collect_episode(hdc: str, target: str, bundle: str, key: str, case_id: str,
                    raw_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    token = uuid.uuid4().hex
    prefix = f"{MARKER}{token}:"
    stem = f"{case_id}-{key}"
    start_path = raw_dir / f"{stem}.start.json"
    hilog_path = raw_dir / f"{stem}.hilog.txt"
    episode_path = raw_dir / f"{stem}.episode.json"
    run([hdc, "-t", target, "shell", "aa", "force-stop", bundle], check=False)
    run([hdc, "-t", target, "shell", "hilog", "-r"], check=False)
    started = run([hdc, "-t", target, "shell", "aa", "start", "-a", "EntryAbility", "-b", bundle, "-m", "entry", "--ps", "semanticCase", key, "--ps", "semanticToken", token], check=False)
    start_path.write_text(json.dumps({
        "caseId": case_id, "key": key, "token": token, "returnCode": started.returncode,
        "stdout": started.stdout, "stderr": started.stderr,
    }, indent=2) + "\n", encoding="utf-8")
    if started.returncode != 0 or "successfully" not in (started.stdout + started.stderr):
        raise RuntimeError(f"ability start failed: {(started.stdout + started.stderr).strip()}")
    deadline = time.monotonic() + 20
    raw_hilog = ""
    while time.monotonic() < deadline:
        time.sleep(0.35)
        captured = run([hdc, "-t", target, "shell", "hilog", "-x", "-T", "LTBObserver"], check=False)
        raw_hilog = captured.stdout + captured.stderr
        chunks: dict[int, str] = {}
        total: int | None = None
        for line in raw_hilog.splitlines():
            marker_at = line.find(prefix)
            if marker_at < 0:
                continue
            match = re.match(r"(\d+):(\d+):(.*)$", line[marker_at + len(prefix):])
            if match is not None:
                chunks[int(match.group(1))] = match.group(3)
                total = int(match.group(2))
        if total is not None and len(chunks) == total:
            payload = json.loads("".join(chunks[index] for index in range(total)))
            if payload.get("key") != key:
                raise RuntimeError("runtime payload key differs from requested case")
            episode = json.loads(payload["episodeJson"])
            hilog_path.write_text(raw_hilog, encoding="utf-8")
            episode_path.write_text(json.dumps(episode, indent=2) + "\n", encoding="utf-8")
            return episode, {
                "abilityStart": artifact(start_path),
                "hilog": artifact(hilog_path),
                "episode": artifact(episode_path),
            }
    hilog_path.write_text(raw_hilog, encoding="utf-8")
    raise RuntimeError(f"API23 page-owner episode timed out for {key}")


def not_scored(case: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "not_scored", "observed": None, "invariantChecks": [], "diagnostic": reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent", "control"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", default=os.environ.get("HDC_TARGET", DEFAULT_TARGET))
    parser.add_argument("--hdc", default=os.environ.get("HDC", DEFAULT_HDC))
    parser.add_argument("--raw-dir", type=Path, help="Directory for per-case raw hilog and runtime episodes")
    args = parser.parse_args()
    project = args.project.resolve()
    output = args.output.resolve()
    raw_dir = (args.raw_dir or output.parent / f"{args.role}-runtime-raw").resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    hap: Path | None = None
    bundle = ""
    installed = False
    api_level: int | None = None
    setup_error = ""
    suffix = hashlib.sha256(args.target.encode()).hexdigest()[:16]
    legacy = Path("/tmp/long-term-benchmark-arkts-device.lock").open("a+")
    target_lock = Path(f"/tmp/ltb-arkts-device-{suffix}").open("a+")
    fcntl.flock(legacy.fileno(), fcntl.LOCK_EX)
    fcntl.flock(target_lock.fileno(), fcntl.LOCK_EX)
    try:
        try:
            validate_bindings(contract)
            sources = source_inventory(project)
            hap = find_hap(project)
            if args.target not in run([args.hdc, "list", "targets"]).stdout.split():
                raise RuntimeError(f"HDC target {args.target} is not connected")
            api_text = run([args.hdc, "-t", args.target, "shell", "param", "get", "const.ohos.apiversion"]).stdout.strip()
            api_level = int(api_text)
            if api_level != 23:
                raise RuntimeError(f"expected OpenHarmony API23, observed {api_text!r}")
            bundle = bundle_name(project)
            install = run([args.hdc, "-t", args.target, "install", "-r", str(hap)], check=False)
            if install.returncode != 0 or "successfully" not in (install.stdout + install.stderr):
                raise RuntimeError(f"HAP install failed: {(install.stdout + install.stderr).strip()}")
            installed = True
            for case in contract["cases"]:
                try:
                    episode, raw_evidence = collect_episode(
                        args.hdc, args.target, bundle, case["key"], case["caseId"], raw_dir,
                    )
                    values = invariant_values(case, episode)
                    checks = [{"invariant": name, "passed": bool(values[index]), "evidence": {"before": episode["before"], "after": episode["after"], "effects": episode["observed"]["effects"]}} for index, name in enumerate(case["invariants"])]
                    evidence = episode.get("runtimeEvidence", {})
                    boundary = [
                        episode.get("given") == case.get("given"), episode.get("event") == case.get("event"),
                        episode.get("commonEntryObserved") is True, evidence.get("storeSource") == "Index.DomainPageOwner.controller.store",
                        evidence.get("evaluatorStoreWrites") == 0, evidence.get("detachedControllers") == 0,
                        evidence.get("storageReopened") is True, episode.get("transitionExecuted") is True and episode.get("earlyExit") is False,
                    ]
                    passed = exact_observation(case, episode["observed"]) and all(values) and all(boundary)
                    rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "pass" if passed else "fail", "productionSources": sources, "productionBodies": episode.get("invokedProductionMethods", []), "checkpoints": [{"label": "before", "state": episode["before"]}, {"label": "after", "state": episode["after"]}], "observed": episode["observed"], "effects": episode["observed"]["effects"], "invariantChecks": checks, "runtimeBoundaryChecks": boundary, "runtimeEvidence": evidence, "rawEvidence": raw_evidence})
                except Exception as error:
                    rows.append(not_scored(case, str(error)))
        except Exception as error:
            setup_error = str(error)
            rows = [not_scored(case, setup_error) for case in contract["cases"]]
    finally:
        if installed and bundle:
            run([args.hdc, "-t", args.target, "shell", "aa", "force-stop", bundle], check=False)
        fcntl.flock(target_lock.fileno(), fcntl.LOCK_UN)
        fcntl.flock(legacy.fileno(), fcntl.LOCK_UN)
        target_lock.close(); legacy.close()

    semantic = summary(rows)
    report = {
        "schemaVersion": 2, "taskId": contract["taskId"], "platform": "arkts", "role": args.role,
        "observationMode": "runtime_state_transition", "runtime": "OpenHarmony API23 EntryAbility/ArkUI Index page-owner runtime",
        "device": {"target": args.target, "apiLevel": api_level},
        "codeGeneration": {"passed": bool(sources), "changedProductionFiles": sources},
        "compile": {"passed": hap is not None, "command": ["bash", "build.sh"], "hapSha256": sha256(hap) if hap else None, "hapBytes": hap.stat().st_size if hap else None},
        "semantic": {"summary": semantic, "cases": rows},
        "diagnostics": {"adapter": "temporary_injected_page_owner", "transport": "hdc" if installed else "unavailable", "productionEntryExecuted": installed, "sourceObserver": False, "roleAffectsVerdict": False, "setupError": setup_error or None},
        "provenance": {"contractSha256": sha256(CONTRACT_PATH), "injectionManifestSha256": sha256(MIGRATION / "arkts/evaluator/injection_manifest.json"), "rawEvidenceDirectory": str(raw_dir)},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(semantic))
    return 0 if semantic["notScored"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
