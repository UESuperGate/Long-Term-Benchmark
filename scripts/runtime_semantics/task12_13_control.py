"""Run one source-parameterized runtime control, without a full app build."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import importlib
import math
from pathlib import Path
import time

from . import task12_13_formal_core as core
from . import task12_13_runtime_support as support
from scripts.run_runtime_transition_matrix import validate_report


def run(*, task: int, platform: str, source: Path, output: Path,
        timeout: float = 3600, role: str = "agent", device_serial: str = "127.0.0.1:5555",
        absolute_deadline: float | None = None):
    if task not in (12, 13) or platform not in {"android", "arkts"}:
        raise ValueError("Only Task12/13 Android/ArkTS controls are supported")
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("Control timeout must satisfy 0 < timeout <= 3600")
    started = time.monotonic()
    deadline = started + timeout
    if absolute_deadline is not None:
        if not math.isfinite(absolute_deadline) or absolute_deadline <= started:
            raise ValueError("Shared control deadline exhausted")
        deadline = min(deadline, absolute_deadline)
    module = importlib.import_module(f".task{task}_formal_agent", __package__)
    runtime = importlib.import_module(f".task{task}_{platform}_strict_runtime", __package__)
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.with_suffix(f".{platform}-evidence").exists():
        raise ValueError("Control output already exists")
    before = core.source_inventory(source)
    contract = core.load(module.SPEC.contract)
    assessment = {
        "schemaVersion": 1, "taskId": module.SPEC.task_id, "platform": platform,
        "role": role, "source": str(source), "sourceInventory": before,
        "timeoutSeconds": timeout, "deadlineMonotonic": deadline,
        "applicationCompile": "not_credited_by_runtime_only_control",
        "runtimeValid": False, "publicPassed": False,
        "counts": {"passed": 0, "failed": 0, "notScored": len(contract["cases"])},
        "command": ["python3", "-m", "scripts.runtime_semantics.task12_13_control",
                    "--task", str(task), "--platform", platform, "--source", str(source),
                    "--output", str(output), "--role", role, "--timeout", str(timeout),
                    "--device-serial", device_serial],
    }
    try:
        lock = support.android_full_build_lock(deadline) if platform == "android" else nullcontext()
        with lock:
            report = runtime.evaluate(task=module.SPEC, platform=platform, source=source,
                                      role=role, output=output, deadline=deadline,
                                      device_serial=device_serial)
        core.validate_runtime_report(report, spec=module.SPEC, platform=platform, role=role,
                                     source=source, inventory=before, contract=contract,
                                     lineage=core.calibrator_lineage(module.SPEC, platform))
        validate_report(report, contract)
        if core.source_inventory(source)["sha256"] != before["sha256"]:
            raise ValueError("Runtime control mutated its source")
        if time.monotonic() >= deadline:
            raise TimeoutError("Control exceeded its single monotonic deadline")
        assessment.update(runtimeValid=True, publicPassed=True, report=core.file_record(output),
                          counts={key: report["semantic"][key] for key in ("passed", "failed", "notScored")})
    except Exception as error:
        assessment.update(error=f"{type(error).__name__}: {error}",
                          classification="runtime_compile_adapter_transport_or_evidence")
    finally:
        cleanup = core.cleanup_artifacts(output.with_suffix(f".{platform}-evidence"), source)
        cleanup_path = output.with_suffix(".cleanup.json")
        core.write(cleanup_path, cleanup)
        assessment.update(cleanup=core.file_record(cleanup_path),
                          elapsedSeconds=time.monotonic() - started)
        if cleanup["binariesRetained"] or not cleanup["temporaryBuildRemoved"]:
            assessment.update(runtimeValid=False, publicPassed=False,
                              counts={"passed": 0, "failed": 0, "notScored": len(contract["cases"])},
                              error="Runtime control cleanup incomplete")
        core.write(output.with_suffix(".assessment.json"), assessment)
    return assessment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=int, choices=(12, 13), required=True)
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), default="agent")
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--device-serial", default="127.0.0.1:5555")
    result = run(**vars(parser.parse_args()))
    print({key: result[key] for key in ("runtimeValid", "publicPassed", "counts", "elapsedSeconds")})
    return 0 if result["runtimeValid"] and result["publicPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
