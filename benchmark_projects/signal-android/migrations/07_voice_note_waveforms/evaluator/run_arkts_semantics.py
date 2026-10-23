#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from run_android_semantics import obj, semantic_checks, sha256

HDC = os.environ.get("HDC", str(Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc"))
TARGET = os.environ.get("HDC_TARGET", "127.0.0.1:10178")
HVIGOR = os.environ.get("HVIGORW", "/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")


def hdc(*parts: str, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([HDC, "-t", TARGET, *parts], text=True, capture_output=True, timeout=timeout, check=check)


def bundle_name(project: Path) -> str:
    source = (project / "AppScope/app.json5").read_text()
    try:
        value = json.loads(source)["app"]["bundleName"]
        if isinstance(value, str) and value:
            return value
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    match = re.search(r'["\']?bundleName["\']?\s*:\s*["\']([^"\']+)', source)
    if not match:
        raise RuntimeError("bundleName missing")
    return match.group(1)


def source_inventory(project: Path) -> list[dict[str, Any]]:
    return [{"path": str(path.relative_to(project)), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted((project / "entry/src/main/ets").rglob("*.ets"))]


def prepare(project: Path, migration: Path, contract: dict[str, Any], temporary: Path) -> None:
    shutil.copytree(project, temporary, ignore=shutil.ignore_patterns("build", ".hvigor", "oh_modules"))
    evaluator = temporary / "entry/src/main/ets/evaluator"
    evaluator.mkdir(parents=True, exist_ok=True)
    shutil.copy2(migration / "arkts/evaluator/RuntimeHarness.ets", evaluator / "RuntimeHarness.ets")
    cases = {case["key"]: {"given": case["given"], "event": case["event"]} for case in contract["cases"]}
    encoded = json.dumps(json.dumps(cases, separators=(",", ":"), ensure_ascii=False), ensure_ascii=False)
    (evaluator / "CaseData.ets").write_text(
        "export const CASES: Record<string, Object> = JSON.parse(" + encoded + ") as Record<string, Object>;\n"
    )
    shutil.copy2(migration / "arkts/evaluator/EntryAbility.evaluator.ets",
                 temporary / "entry/src/main/ets/entryability/EntryAbility.ets")


def build(temporary: Path, log_path: Path) -> tuple[Path, dict[str, Any]]:
    env = os.environ.copy()
    env["OHOS_BASE_SDK_HOME"] = str(Path.home() / "Library/OpenHarmony/Sdk")
    env["JAVA_HOME"] = "/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home"
    command = [HVIGOR, "--mode", "module", "-p", "product=default", "-p", "module=entry@default", "assembleHap", "--no-daemon"]
    run = subprocess.run(command, cwd=temporary, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_path.parent.mkdir(parents=True, exist_ok=True); log_path.write_text(run.stdout)
    if run.returncode != 0:
        raise RuntimeError(f"hvigor failed; see {log_path}")
    haps = sorted((temporary / "entry/build").rglob("*.hap"))
    if not haps:
        raise RuntimeError("hvigor produced no HAP")
    hap = haps[-1]
    return hap, {"name": hap.name, "sha256": sha256(hap), "bytes": hap.stat().st_size, "cleanedAfterRecording": True}


def read_episode(bundle: str, key: str, evidence_dir: Path) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for attempt in range(1, 4):
        hdc("shell", "aa", "force-stop", bundle, check=False)
        time.sleep(0.5)
        hdc("shell", "hilog", "-r", check=False)
        start = hdc("shell", "aa", "start", "-a", "EntryAbility", "-b", bundle, "--ps", "caseKey", key, check=False)
        start_text = start.stdout + start.stderr
        (evidence_dir / f"{key}.start.attempt{attempt}.txt").write_text(start_text)
        (evidence_dir / f"{key}.start.txt").write_text(start_text)
        if start.returncode != 0 or "successfully" not in start.stdout:
            failures.append(start_text.strip() or "ability start failed")
            time.sleep(1)
            continue
        deadline = time.monotonic() + 25
        last_hilog = ""
        while time.monotonic() < deadline:
            logs = hdc("shell", "hilog", "-x", "-e", "LTB_RUNTIME_CHUNK", check=False)
            last_hilog = logs.stdout + logs.stderr
            chunks: dict[int, str] = {}; total: int | None = None
            for line in logs.stdout.splitlines():
                marker = f"LTB_RUNTIME_CHUNK:{key}:"
                if marker not in line: continue
                body = line.split(marker, 1)[1]
                parts = body.split(":", 2)
                if len(parts) != 3: continue
                try: index, candidate_total = int(parts[0]), int(parts[1])
                except ValueError: continue
                if total is None or total == candidate_total:
                    total = candidate_total; chunks[index] = parts[2]
            if total is not None and len(chunks) == total:
                (evidence_dir / f"{key}.hilog.attempt{attempt}.txt").write_text(last_hilog)
                (evidence_dir / f"{key}.hilog.txt").write_text(last_hilog)
                return json.loads("".join(chunks[index] for index in range(total)))
            time.sleep(0.25)
        (evidence_dir / f"{key}.hilog.attempt{attempt}.txt").write_text(last_hilog)
        (evidence_dir / f"{key}.hilog.txt").write_text(last_hilog)
        failures.append(f"attempt {attempt} timed out")
    raise RuntimeError(f"API23 runtime episode failed for {key}: {'; '.join(failures)}")


def run(project: Path, role: str, output: Path) -> int:
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    sources = source_inventory(project); bundle = bundle_name(project)
    rows: list[dict[str, Any]] = []; episodes: dict[str, Any] = {}; artifact: dict[str, Any] | None = None
    error = ""; api_level: int | None = None; software = ""; installed = False
    temporary_root = Path(tempfile.mkdtemp(prefix=f"ltb-signal07-arkts-{role}-"))
    temporary = temporary_root / "project"
    hilog_dir = output.with_suffix(".hilog")
    lock_name = hashlib.sha256(TARGET.encode()).hexdigest()[:16]
    externally_locked = os.environ.get("LTB_ARKTS_DEVICE_LOCK_HELD") == "1"
    lock_context = contextlib.nullcontext(None) if externally_locked else open(f"/tmp/ltb-arkts-device-{lock_name}", "a+")
    with lock_context as lock:
        if lock is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if shutil.disk_usage(project).free < 8 * 1024 ** 3: raise RuntimeError("refusing ArkTS build below 8 GiB free")
            prepare(project, migration, contract, temporary)
            hap, artifact = build(temporary, migration / f"provenance/build-logs/arkts-{role}.log")
            api_level = int(hdc("shell", "param", "get", "const.ohos.apiversion").stdout.strip())
            software = hdc("shell", "param", "get", "const.product.software.version", check=False).stdout.strip()
            if api_level != 23: raise RuntimeError(f"expected OpenHarmony API 23, found {api_level}")
            install = hdc("install", "-r", str(hap), timeout=120, check=False)
            if install.returncode != 0 or "successfully" not in install.stdout: raise RuntimeError((install.stdout + install.stderr).strip() or "HAP install failed")
            installed = True
            for case in contract["cases"]:
                try:
                    episode = read_episode(bundle, case["key"], hilog_dir); episodes[case["caseId"]] = episode
                    values = semantic_checks(case["key"], episode)
                    invariant_checks = [{"invariant": text, "passed": values[index], "evidence": {"before": episode.get("before"), "checkpoint": episode.get("checkpoint"), "after": episode.get("after")}} for index, text in enumerate(case["invariants"])]
                    bound = episode.get("given") == case["given"] and episode.get("event") == case["event"] and episode.get("givenEstablished") is True and episode.get("pageOwnerId") == "Index:WaveformPageOwner" and episode.get("commonEntryObserved") is True and episode.get("transitionExecuted") is True and episode.get("storageReopened") is True and bool(episode.get("productionCalls"))
                    passed = bound and all(values) and all(item["passed"] for item in invariant_checks)
                    rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "pass" if passed else "fail", "productionSources": sources, "observed": episode.get("observed"), "checkpoints": [{"label": "before", "state": episode.get("before")}, {"label": "held", "state": episode.get("checkpoint")}, {"label": "after", "state": episode.get("after")}], "invariantChecks": invariant_checks, "runtimeBoundaryChecks": {"canonicalInputBound": bound, "pageOwnerId": episode.get("pageOwnerId"), "productionCalls": episode.get("productionCalls")}})
                except (RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
                    rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "not_scored", "reason": str(failure)})
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
            error = str(failure)
            rows = [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "not_scored", "reason": error} for case in contract["cases"]]
        finally:
            if installed:
                hdc("shell", "aa", "force-stop", bundle, check=False); hdc("uninstall", bundle, check=False)
            shutil.rmtree(temporary_root, ignore_errors=True)
    raw = output.with_suffix(".raw.json"); raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps({"schemaVersion": 1, "taskId": contract["taskId"], "platform": "arkts", "role": role, "target": TARGET, "episodes": episodes, "error": error or None}, indent=2) + "\n")
    count = lambda status: sum(row["status"] == status for row in rows)
    hilog_artifacts = [{"path": str(path.relative_to(output.parent)), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(hilog_dir.glob("*")) if path.is_file()]
    report = {"schemaVersion": 1, "taskId": contract["taskId"], "platform": "arkts", "role": role, "observationMode": "runtime_state_transition", "runtime": "OpenHarmony API23 EntryAbility and mounted ArkUI Index page owner", "compile": {"passed": artifact is not None, "artifacts": [] if artifact is None else [artifact]}, "semantic": {"passed": count("pass"), "failed": count("fail"), "notScored": count("not_scored"), "total": len(rows), "cases": rows}, "diagnostics": {"adapter": "ready" if not error and count("not_scored") == 0 else "unavailable", "transport": "hdc_entryability_hilog", "target": TARGET, "apiLevel": api_level, "softwareVersion": software, "sourceObserver": False, "rawEvidence": {"path": raw.name, "sha256": sha256(raw), "bytes": raw.stat().st_size}, "rawHilog": hilog_artifacts}}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if not error and count("not_scored") == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--project", type=Path, required=True); parser.add_argument("--role", choices=("base", "final", "agent"), required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    return run(args.project.resolve(), args.role, args.output.resolve())


if __name__ == "__main__": raise SystemExit(main())
