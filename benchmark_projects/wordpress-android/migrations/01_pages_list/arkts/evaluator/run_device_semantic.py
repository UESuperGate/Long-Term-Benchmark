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

DEFAULT_HDC = "/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc"
DEFAULT_TARGET = "127.0.0.1:5557"
MARKER = "LTB_RUNTIME:"


def run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, encoding="utf-8", errors="replace", capture_output=True, check=check)


def with_arkts_device_lock(function):
    def locked() -> int:
        target = os.environ.get("HDC_TARGET", DEFAULT_TARGET)
        suffix = hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]
        legacy_lock = Path("/tmp/long-term-benchmark-arkts-device.lock").open("a+")
        device_lock = Path(f"/tmp/ltb-arkts-device-{suffix}").open("a+")
        fcntl.flock(legacy_lock.fileno(), fcntl.LOCK_EX)
        try:
            fcntl.flock(device_lock.fileno(), fcntl.LOCK_EX)
            try:
                return function()
            finally:
                fcntl.flock(device_lock.fileno(), fcntl.LOCK_UN)
        finally:
            device_lock.close()
            fcntl.flock(legacy_lock.fileno(), fcntl.LOCK_UN)
            legacy_lock.close()

    return locked


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_bundle(project: Path) -> str:
    app = json.loads((project / "AppScope/app.json5").read_text(encoding="utf-8"))
    return app["app"]["bundleName"]


def find_hap(project: Path) -> Path:
    haps = sorted((project / "entry/build").glob("**/*.hap"))
    if not haps:
        raise RuntimeError("no built HAP found; run the declared buildCommand first")
    return haps[0]


def production_sources(project: Path) -> list[dict[str, str]]:
    relative_paths = [
        Path("entry/src/main/ets/features/PagesController.ets"),
        Path("entry/src/main/ets/pages/Index.ets"),
        Path("entry/src/main/ets/pages/PagesPageOwner.ets"),
        Path("entry/src/main/ets/entryability/EntryAbility.ets"),
    ]
    return [{"path": str(path), "sha256": sha256(project / path)} for path in relative_paths]


def semantic_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "passed": sum(row["status"] == "pass" for row in rows),
        "failed": sum(row["status"] == "fail" for row in rows),
        "notScored": sum(row["status"] == "not_scored" for row in rows),
        "total": len(rows),
    }


def collect_payload(hdc: str, target: str, bundle: str, key: str) -> dict[str, Any]:
    token = uuid.uuid4().hex
    prefix = f"{MARKER}{token}:"
    run([hdc, "-t", target, "shell", "hilog", "-r"], check=False)
    run([hdc, "-t", target, "shell", "aa", "force-stop", bundle], check=False)
    time.sleep(0.15)
    started = run([
        hdc, "-t", target, "shell", "aa", "start", "-a", "EntryAbility", "-b", bundle, "-m", "entry",
        "--ps", "semanticCase", key, "--ps", "semanticToken", token,
    ], check=False)
    if started.returncode != 0 or "successfully" not in (started.stdout + started.stderr):
        raise RuntimeError(f"ability start failed: {(started.stdout + started.stderr).strip()}")

    deadline = time.monotonic() + 8.0
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
            encoded = line[marker_at + len(prefix):]
            match = re.match(r"(\d+):(\d+):(.*)$", encoded)
            if match is None:
                continue
            index = int(match.group(1))
            total = int(match.group(2))
            chunks[index] = match.group(3)
        if total is not None and len(chunks) == total:
            raw = "".join(chunks[index] for index in range(total))
            return json.loads(raw)
    diagnostic = "\n".join(line for line in last_log.splitlines() if "LTB" in line)[-2000:]
    raise RuntimeError(f"device observer timed out for {key}; LTB log: {diagnostic}")


def unavailable_report(task_id: str, role: str, diagnostic: str, contract: dict[str, Any]) -> dict[str, Any]:
    rows = [{
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": None, "invariantChecks": [], "diagnostic": diagnostic,
    } for case in contract["cases"]]
    return {
        "schemaVersion": 1, "taskId": task_id, "platform": "arkts", "role": role,
        "observationMode": "runtime_state_transition", "runtime": "OpenHarmony API23 EntryAbility/ArkUI device runtime",
        "device": {"target": os.environ.get("HDC_TARGET", DEFAULT_TARGET), "apiLevel": None},
        "codeGeneration": {"passed": None, "changedProductionFiles": []},
        "compile": {"passed": None, "command": ["bash", "build.sh"]},
        "semantic": {"summary": semantic_summary(rows), "cases": rows},
        "diagnostics": {"adapter": "device_hilog_probe", "transport": "unavailable", "productionEntryExecuted": False},
    }


@with_arkts_device_lock
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()

    project = args.project.resolve()
    contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
    output = args.output.resolve()
    hdc = os.environ.get("HDC", DEFAULT_HDC)
    target = os.environ.get("HDC_TARGET", DEFAULT_TARGET)
    try:
        listed = run([hdc, "list", "targets"]).stdout.split()
        if target not in listed:
            raise RuntimeError(f"HDC target {target} is not connected")
        api_text = run([hdc, "-t", target, "shell", "param", "get", "const.ohos.apiversion"]).stdout.strip()
        if api_text != "23":
            raise RuntimeError(f"expected OpenHarmony API23, observed {api_text!r}")
        hap = find_hap(project)
        installed = run([hdc, "-t", target, "install", "-r", str(hap)], check=False)
        if installed.returncode != 0 or "successfully" not in (installed.stdout + installed.stderr):
            raise RuntimeError(f"HAP install failed: {(installed.stdout + installed.stderr).strip()}")
        bundle = project_bundle(project)
        sources = production_sources(project)
    except Exception as error:
        report = unavailable_report(contract["taskId"], args.role, str(error), contract)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 2

    rows: list[dict[str, Any]] = []
    for case in contract["cases"]:
        try:
            payload = collect_payload(hdc, target, bundle, case["key"])
            if payload.get("key") != case["key"]:
                raise RuntimeError("runtime payload key does not match requested case")
            observed = json.loads(payload["observedJson"])
            checks = json.loads(payload["invariantChecksJson"])
            runtime_evidence = json.loads(payload["runtimeEvidenceJson"])
            if not runtime_evidence.get("pageOwnerId") or not runtime_evidence.get("controllerOwnerId"):
                raise RuntimeError("page/controller ownership evidence is missing")
            if contract["taskId"] == "02_unified_support":
                expected_store_source = "LegacySupportPageOwner.controller.store" if args.role == "base" else "UnifiedSupportPageOwner.controller.store"
            else:
                expected_store_source = "LegacyPagesPageOwner.controller.store" if args.role == "base" else "PagesPageOwner.controller.store"
            if runtime_evidence.get("storeSource") != expected_store_source:
                raise RuntimeError("observation did not come from the mounted page owner")
            if runtime_evidence.get("evaluatorStoreWrites") != 0 or runtime_evidence.get("detachedControllers") != 0:
                raise RuntimeError("evaluator bypassed page ownership")
            if not isinstance(runtime_evidence.get("leafCalls"), list):
                raise RuntimeError("external leaf call log is missing")
            if case["key"] == "draft_lifecycle":
                if runtime_evidence.get("pageRecreated") is not True:
                    raise RuntimeError("draft lifecycle did not recreate the production page")
                if runtime_evidence.get("previousPageOwnerId") == runtime_evidence.get("pageOwnerId"):
                    raise RuntimeError("draft lifecycle reused the old page owner")
                same_controller = runtime_evidence.get("previousControllerOwnerId") == runtime_evidence.get("controllerOwnerId")
                if args.role == "base" and same_controller:
                    raise RuntimeError("base draft lifecycle unexpectedly retained the target controller")
                if args.role == "final" and not same_controller:
                    raise RuntimeError("draft lifecycle did not retain the production controller")
            checks_by_name = {check["invariant"]: check for check in checks}
            invariants_passed = all(
                name in checks_by_name and checks_by_name[name].get("passed") is True
                for name in case["invariants"]
            )
            status = "pass" if observed == case["expected"] and invariants_passed else "fail"
            rows.append({
                "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                "status": status, "productionSources": sources,
                "productionBodies": payload["productionBodies"],
                "checkpoints": [
                    {"label": "before", "state": json.loads(payload["beforeJson"])},
                    {"label": "after", "state": json.loads(payload["afterJson"])},
                ],
                "observed": observed, "effects": json.loads(payload["effectsJson"]),
                "invariantChecks": checks, "runtimeEvidence": runtime_evidence,
            })
        except Exception as error:
            rows.append({
                "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                "status": "not_scored", "productionSources": sources, "observed": None,
                "invariantChecks": [], "diagnostic": str(error),
            })

    report = {
        "schemaVersion": 1, "taskId": contract["taskId"], "platform": "arkts", "role": args.role,
        "observationMode": "runtime_state_transition", "runtime": "OpenHarmony API23 EntryAbility/ArkUI device runtime",
        "device": {"target": target, "apiLevel": 23},
        "codeGeneration": {"passed": True, "changedProductionFiles": []},
        "compile": {"passed": True, "command": ["bash", "build.sh"], "hapSha256": sha256(hap), "hapBytes": hap.stat().st_size},
        "semantic": {"summary": semantic_summary(rows), "cases": rows},
        "diagnostics": {"adapter": "device_hilog_probe", "transport": "hdc", "productionEntryExecuted": True,
            "productionPageLoaded": "pages/Index", "pageOwnershipEnforced": True,
            "externalLeafLogRequired": True, "draftRecreationEnforced": contract["taskId"] == "02_unified_support"},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if all(row["status"] != "not_scored" for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
