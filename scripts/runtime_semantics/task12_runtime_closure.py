"""Fresh Task12 dynamic calibration and base-copy control; app compile is receipt-only."""

import argparse
from contextlib import nullcontext
import math
from pathlib import Path
import time

from . import task12_formal_agent as formal
from . import task12_13_control as control
from . import task12_13_formal_core as core
from . import task12_13_runtime_support as support


def run(*, platform, source, base_source, final_source, negative_source,
        application_compile_evidence, output, negative_output, protocol_output,
        timeout=3600.0, device_serial="127.0.0.1:5555"):
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("Closure timeout must satisfy 0 < timeout <= 3600")
    started = time.monotonic()
    deadline = started + timeout
    candidate = core.source_inventory(source)
    positive = core.source_inventory(final_source)
    negative = core.source_inventory(negative_source)
    baseline = core.source_inventory(base_source)
    if candidate["sha256"] != positive["sha256"] or negative["sha256"] != baseline["sha256"]:
        raise ValueError("Control copies differ from their immutable calibration inputs")
    if len({p.resolve() for p in (source, base_source, final_source, negative_source)}) != 4:
        raise ValueError("All calibration and control source paths must be independent")
    audit = {"schemaVersion": 1, "platform": platform, "deadlineSeconds": timeout,
             "singleDeadlineMonotonic": deadline, "readyCandidate": False,
             "freshRuntimeExecuted": True, "applicationEvidenceReusedOnly": True,
             "sourceInventories": {"base": baseline, "final": positive,
                                   "candidate": candidate, "negative": negative}}
    core.write(protocol_output, audit)
    try:
        lock = support.android_full_build_lock(deadline) if platform == "android" else nullcontext()
        with lock:
            result = formal.score(
                platform=platform, source=source, base_source=base_source, final_source=final_source,
                output=output, application_compile_evidence=application_compile_evidence,
                timeout=deadline - time.monotonic(), device_serial=device_serial,
            )
        audit["formalReport"] = core.file_record(output)
        audit["candidateCounts"] = {key: result["semantic"][key] for key in ("passed", "failed", "notScored")}
        core.write(protocol_output, audit)
        if (result["calibration"].get("passed") and result["publication"]["eligible"] and
                audit["candidateCounts"] == {"passed": 10, "failed": 0, "notScored": 0}):
            negative_result = control.run(
                task=12, platform=platform, source=negative_source, output=negative_output,
                timeout=deadline - time.monotonic(), absolute_deadline=deadline,
                device_serial=device_serial,
            )
            audit["negativeControl"] = core.file_record(negative_output.with_suffix(".assessment.json"))
            audit["negativeCounts"] = negative_result["counts"]
            audit["readyCandidate"] = (negative_result["runtimeValid"] and negative_result["publicPassed"] and
                negative_result["counts"] == {"passed": 0, "failed": 10, "notScored": 0} and
                time.monotonic() < deadline)
    except Exception as error:
        audit["error"] = f"{type(error).__name__}: {error}"
    finally:
        audit["elapsedSeconds"] = time.monotonic() - started
        core.write(protocol_output, audit)
    print({key: audit.get(key) for key in ("readyCandidate", "candidateCounts", "negativeCounts", "error", "elapsedSeconds")}, flush=True)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("android", "arkts"))
    for flag in ("source", "base-source", "final-source", "negative-source", "application-compile-evidence",
                 "output", "negative-output", "protocol-output"):
        parser.add_argument("--" + flag, required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--device-serial", default="127.0.0.1:5555")
    return 0 if run(**vars(parser.parse_args()))["readyCandidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
