#!/usr/bin/env python3
"""Run the Task17 owner-bound ArkTS base/final/agent device matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"
BUILD = ROOT / "scripts/runtime_semantics/task17_arkts_owner_build.cjs"
EXECUTE = ROOT / "scripts/runtime_semantics/arkts_device_execute.cjs"
SOURCES = {
    "base": ROOT / "17_pinned_messages_base_0_5_1",
    "final": ROOT / "final_dev_nodes/17_pinned_messages_final_0_5_3",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"Task17 role budget exhausted during {phase}")
    return value


def run(command: list[str], log: Path, deadline: float) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as stream:
        completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=remaining(deadline, command[1]), check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit {completed.returncode}: {' '.join(command)}")


def source_inventory(source: Path) -> list[dict]:
    rows = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or any(part in {".git", ".hvigor", "build", "oh_modules", "node_modules"}
                                     for part in path.relative_to(source).parts):
            continue
        rows.append({"path": str(path.relative_to(source)), "bytes": path.stat().st_size,
                     "sha256": sha256(path)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-source", type=Path, required=True)
    parser.add_argument("--serial", default="127.0.0.1:5555")
    parser.add_argument("--role", action="append", choices=("base", "final", "agent"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing existing output: {output}")
    output.mkdir(parents=True)
    roles = args.role or ["base", "final", "agent"]
    sources = {**SOURCES, "agent": args.agent_source.resolve()}
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cases = contract["cases"]
    started = time.monotonic()
    matrix = {
        "schemaVersion": 1,
        "taskId": "17_pinned_messages",
        "runtime": "openharmony_api23_device_uitest_candidate_page_owner_matrix_room_port",
        "contract": record(CONTRACT),
        "evaluator": {"build": record(BUILD), "execute": record(EXECUTE)},
        "roleBudgetSeconds": 3600,
        "serial": args.serial,
        "roles": {},
        "rows": [],
        "complete": False,
    }
    write(output / "matrix.partial.json", matrix)
    for role in roles:
        role_started = time.monotonic()
        deadline = role_started + 3600
        source = sources[role]
        role_rows = []
        for spec in cases:
            case_id = spec["caseId"]
            case_root = output / role / case_id
            build_root = case_root / "build"
            execution_root = case_root / "execution"
            run(["node", str(BUILD), "--source", str(source), "--role", role,
                 "--case", case_id, "--output-dir", str(build_root)],
                case_root / "build.log", deadline)
            build_report = build_root / "device-build-report.json"
            build = json.loads(build_report.read_text(encoding="utf-8"))
            if (build.get("compile", {}).get("passed") is not True or
                    build.get("runtimeCompile", {}).get("passed") is not True or
                    build.get("productionUnchanged") is not True):
                raise RuntimeError(f"Incomplete owner-bound build provenance: {role}/{case_id}")
            run(["node", str(EXECUTE), str(build_report), args.serial, str(execution_root)],
                case_root / "execute.log", deadline)
            execution_report = execution_root / "device-execution.json"
            execution = json.loads(execution_report.read_text(encoding="utf-8"))
            matching = [row for row in execution.get("rows", [])
                        if row.get("caseId") == case_id and row.get("traceDigest") == spec["traceDigest"]]
            if (execution.get("status") != "transport_completed" or
                    execution.get("transportCompleted") is not True or
                    execution.get("candidateAbsentBeforeInstall") is not True or
                    execution.get("cleanup", {}).get("ownedAppUninstalled") is not True or
                    len(matching) != 1 or matching[0].get("status") not in {"pass", "fail"}):
                raise RuntimeError(f"Incomplete owner-bound execution: {role}/{case_id}")
            row = {"role": role, "caseId": case_id, "traceDigest": spec["traceDigest"],
                   "status": matching[0]["status"], "compile": True, "runtimeCompile": True,
                   "build": record(build_report), "execution": record(execution_report),
                   "nativeResult": record(execution_root / "native-result.json")}
            role_rows.append(row)
            matrix["rows"].append(row)
            write(output / "matrix.partial.json", matrix)
        counts = {name: sum(row["status"] == name for row in role_rows) for name in ("pass", "fail")}
        expected = None if role == "agent" else ({"pass": 0, "fail": 9} if role == "base" else
                                                  {"pass": 9, "fail": 0})
        matrix["roles"][role] = {
            "source": str(source.resolve()),
            "sourceInventory": source_inventory(source),
            "applicationCompile": "passed",
            "semantic": counts,
            "expected": expected,
            "polarityValid": expected is None or counts == expected,
            "durationSeconds": round(time.monotonic() - role_started, 3),
        }
        write(output / f"{role}.json", {"schemaVersion": 1, "taskId": matrix["taskId"],
              "role": role, "runtime": matrix["runtime"], "contract": matrix["contract"],
              **matrix["roles"][role], "cases": role_rows})
        write(output / "matrix.partial.json", matrix)
    matrix["durationSeconds"] = round(time.monotonic() - started, 3)
    matrix["complete"] = True
    matrix["calibrationValid"] = all(value["polarityValid"] for role, value in matrix["roles"].items()
                                     if role in {"base", "final"})
    write(output / "matrix.json", matrix)
    (output / "matrix.partial.json").unlink()
    print(json.dumps({"matrix": str((output / 'matrix.json').resolve()),
                      "roles": {role: value["semantic"] for role, value in matrix["roles"].items()},
                      "durationSeconds": matrix["durationSeconds"],
                      "calibrationValid": matrix["calibrationValid"]}, indent=2))
    return 0 if matrix["calibrationValid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
