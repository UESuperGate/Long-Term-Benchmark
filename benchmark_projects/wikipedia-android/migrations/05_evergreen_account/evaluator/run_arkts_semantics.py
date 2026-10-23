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
import urllib.parse
from pathlib import Path

from score_common import score_case, source_inventory, write_report

DEFAULT_HDC = "/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc"
DEFAULT_TARGET = "127.0.0.1:10178"
MARKER = "LTB_EVERGREEN_CHUNK:"


class RuntimeEpisodeError(RuntimeError):
    def __init__(self, message: str, raw_hilog: str = "") -> None:
        super().__init__(message)
        self.raw_hilog = raw_hilog


def hdc(binary: str, target: str, *args: str, timeout: int = 90, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([binary, "-t", target, *args], text=True, errors="replace",
                          capture_output=True, timeout=timeout, check=check)


def bundle_name(project: Path) -> str:
    text = (project / "AppScope/app.json5").read_text()
    return re.search(r"bundleName\s*:\s*['\"]([^'\"]+)", text).group(1)  # type: ignore[union-attr]


def validate_bindings(migration: Path, contract: dict) -> None:
    bindings = json.loads((migration / "arkts/bindings.json").read_text())
    actual = {(row["caseId"], row["traceDigest"]) for row in bindings["cases"]}
    expected = {(row["caseId"], row["traceDigest"]) for row in contract["cases"]}
    if actual != expected:
        raise RuntimeError("ArkTS bindings do not match canonical case identities and digests")


def read_episode(binary: str, target: str, bundle: str, key: str) -> tuple[dict, str]:
    hdc(binary, target, "shell", "aa", "force-stop", bundle, check=False)
    hdc(binary, target, "shell", "hilog", "-r", check=False)
    start = hdc(binary, target, "shell", "aa", "start", "-a", "EntryAbility", "-b", bundle, "--ps", "caseKey", key, check=False)
    if start.returncode or "successfully" not in start.stdout:
        raise RuntimeEpisodeError((start.stdout + start.stderr).strip() or "ability start failed")
    deadline = time.monotonic() + 25
    raw_hilog = ""
    while time.monotonic() < deadline:
        logs = hdc(binary, target, "shell", "hilog", "-x", check=False)
        marker_lines = [line for line in logs.stdout.splitlines() if MARKER in line]
        raw_hilog = "\n".join(marker_lines)
        if raw_hilog:
            raw_hilog += "\n"
        if logs.stderr:
            raw_hilog += logs.stderr
        chunks: dict[int, str] = {}
        total = None
        for line in marker_lines:
            body = line.split(MARKER, 1)[1].strip()
            parts = body.split(":", 3)
            if len(parts) != 4 or parts[0] != key:
                continue
            index, count = int(parts[1]), int(parts[2])
            total = count
            chunks[index] = parts[3]
        if total is not None and len(chunks) == total:
            episode = json.loads(urllib.parse.unquote("".join(chunks[index] for index in range(total))))
            if episode.get("caseKey") == key:
                return episode, raw_hilog
        time.sleep(0.3)
    raise RuntimeEpisodeError(f"runtime episode timeout: {key}", raw_hilog)


def unavailable(case: dict, reason: str) -> dict:
    return {"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
            "status": "not_scored", "observed": {}, "invariantChecks": [],
            "runtimeBoundaryChecks": [], "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", default=os.environ.get("HDC_TARGET", DEFAULT_TARGET))
    parser.add_argument("--hdc", default=os.environ.get("HDC", DEFAULT_HDC))
    args = parser.parse_args()
    project = args.project.resolve()
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    rows, episodes = [], []
    bundle = bundle_name(project)
    haps = sorted((project / "entry/build").rglob("*.hap"))
    hap = haps[-1] if haps else None
    runtime = {"target": args.target, "apiLevel": None, "softwareVersion": "", "transport": "hdc EntryAbility/hilog"}
    installed = False
    lock_name = hashlib.sha256(args.target.encode()).hexdigest()[:16]
    with open(f"/tmp/ltb-arkts-device-{lock_name}", "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            validate_bindings(migration, contract)
            if hap is None:
                raise RuntimeError("calibration HAP missing")
            targets = subprocess.run([args.hdc, "list", "targets", "-v"], text=True, errors="replace",
                                     capture_output=True, check=True).stdout
            if args.target not in targets or "Connected" not in targets:
                raise RuntimeError(f"HDC target unavailable: {args.target}")
            api = int(hdc(args.hdc, args.target, "shell", "param", "get", "const.ohos.apiversion").stdout.strip())
            if api != 23:
                raise RuntimeError(f"expected API 23 device, found {api}")
            runtime["apiLevel"] = api
            runtime["softwareVersion"] = hdc(args.hdc, args.target, "shell", "param", "get", "const.product.software.version").stdout.strip()
            install = hdc(args.hdc, args.target, "install", "-r", str(hap), timeout=180, check=False)
            if install.returncode or "successfully" not in install.stdout:
                raise RuntimeError((install.stdout + install.stderr).strip() or "HAP install failed")
            installed = True
            for case in contract["cases"]:
                try:
                    episode, raw_hilog = read_episode(args.hdc, args.target, bundle, case["key"])
                    episodes.append({"caseId": case["caseId"], "episode": episode, "rawHilog": raw_hilog})
                    rows.append(score_case(case, episode))
                except Exception as exc:
                    episodes.append({"caseId": case["caseId"], "error": str(exc),
                                     "rawHilog": getattr(exc, "raw_hilog", "")})
                    rows.append(unavailable(case, str(exc)))
        except Exception as exc:
            rows = [unavailable(case, str(exc)) for case in contract["cases"]]
        finally:
            if installed:
                hdc(args.hdc, args.target, "shell", "aa", "force-stop", bundle, check=False)
                hdc(args.hdc, args.target, "uninstall", bundle, check=False)
    write_report(args.output.resolve(), contract["taskId"], "arkts", args.role, rows,
                 source_inventory(project / "entry/src/main", (".ets", ".json", ".json5")), runtime, episodes)
    return 0 if all(row["status"] != "not_scored" for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
