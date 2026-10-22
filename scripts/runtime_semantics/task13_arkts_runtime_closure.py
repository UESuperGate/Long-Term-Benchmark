"""Fresh Task13 ArkTS dynamic triple and random base-copy control in one budget."""

import argparse
import math
from pathlib import Path
import shutil
import tempfile
import time

from . import task12_13_formal_core as core
from . import task13_formal_agent as formal
from . import task13_arkts_strict_runtime as runtime
from scripts.run_runtime_transition_matrix import validate_report


def copy_input(source, prefix):
    destination = Path(tempfile.mkdtemp(prefix=prefix))
    inventory = core.source_inventory(source)
    for item in inventory["files"]:
        target = destination / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item["path"], target)
    if core.source_inventory(destination)["sha256"] != inventory["sha256"]:
        raise ValueError("Independent Task13 source copy differs")
    return destination


def public_proof(path, contract):
    proof = {"report": core.file_record(path), "directCall":
             "run_runtime_transition_matrix.validate_report(report, canonical_contract)", "passed": False}
    try:
        validate_report(core.load(path), contract)
        proof["passed"] = True
    except Exception as error:
        proof["error"] = f"{type(error).__name__}: {error}"
    return proof


def run(*, base_source, final_source, output, timeout=3600.0, device_serial="127.0.0.1:5555"):
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("Task13 closure timeout must satisfy 0 < timeout <= 3600")
    started = time.monotonic()
    deadline = started + timeout
    output = output.resolve()
    if output.exists():
        raise ValueError("Refusing existing closure evidence")
    output.mkdir(parents=True)
    protocol_path = output / "protocol.json"
    protocol = {"taskId": formal.SPEC.task_id, "platform": "arkts", "readyCandidate": False,
                "singleDeadlineMonotonic": deadline, "timeoutSeconds": timeout,
                "runtimeEvidenceReused": False, "applicationBuildReused": False}
    core.write(protocol_path, protocol)
    sources = {}
    try:
        for role, source in (("base", base_source), ("final", final_source)):
            sources[role] = copy_input(source, "ltb-t13-input-")
        sources["agent"] = copy_input(sources["final"], "ltb-t13-input-")
        sources["negative"] = copy_input(sources["base"], "ltb-t13-input-")
        protocol["sourceInventories"] = {key: core.source_inventory(path) for key, path in sources.items()}
        contract = core.load(formal.SPEC.contract)
        protocol["canonicalContract"] = core.file_record(formal.SPEC.contract)
        protocol["calibratorLineage"] = core.calibrator_lineage(formal.SPEC, "arkts")
        core.write(protocol_path, protocol)
        result_path = output / "formal.json"
        result = formal.score(platform="arkts", source=sources["agent"], base_source=sources["base"],
                              final_source=sources["final"], output=result_path,
                              timeout=deadline - time.monotonic(), device_serial=device_serial,
                              validate_public=False)
        protocol["calibrationPassed"] = result["calibration"].get("passed") is True
        protocol["candidateCounts"] = {key: result["semantic"][key] for key in ("passed", "failed", "notScored")}
        paths = [output / "formal.strict-evidence" / role / "runtime.json" for role in ("base", "final", "agent")]
        if protocol["calibrationPassed"] and protocol["candidateCounts"] == {"passed": 10, "failed": 0, "notScored": 0}:
            negative_path = output / "random-base-agent.json"
            try:
                negative = runtime.evaluate(task=formal.SPEC, platform="arkts", source=sources["negative"],
                                            role="agent", output=negative_path, deadline=deadline,
                                            device_serial=device_serial)
                core.validate_runtime_report(negative, spec=formal.SPEC, platform="arkts", role="agent",
                    source=sources["negative"], inventory=protocol["sourceInventories"]["negative"],
                    contract=contract, lineage=core.calibrator_lineage(formal.SPEC, "arkts"))
                protocol["negativeCounts"] = {key: negative["semantic"][key] for key in ("passed", "failed", "notScored")}
                paths.append(negative_path)
            finally:
                cleanup = core.cleanup_artifacts(negative_path.with_suffix(".arkts-evidence"), sources["negative"])
                core.write(output / "negative-cleanup.json", cleanup)
                protocol["negativeCleanup"] = core.file_record(output / "negative-cleanup.json")
        # Never patch the public registry locally to make a new entry policy pass.
        proofs = [public_proof(path, contract) for path in [*paths, result_path] if path.exists()]
        protocol["publicProofs"] = proofs
        protocol["readyCandidate"] = (protocol["calibrationPassed"] and len(proofs) == 5 and
            all(proof["passed"] for proof in proofs) and
            protocol.get("negativeCounts") == {"passed": 0, "failed": 10, "notScored": 0} and
            time.monotonic() < deadline)
        if not protocol["readyCandidate"]:
            result["publication"].update(eligible=False, reason="Four source-bound controls and direct current public validation must all complete")
            core.write(result_path, result)
            proofs[-1]["report"] = core.file_record(result_path)
        protocol["formalReport"] = core.file_record(result_path)
    except Exception as error:
        protocol["error"] = f"{type(error).__name__}: {error}"
    finally:
        cleanups = []
        for key, source in sources.items():
            records = [core.file_record(path) for path in sorted(source.rglob("*")) if path.is_file()]
            cleanups.append({"role": key, "source": str(source), "files": records,
                             "fileCount": len(records), "bytes": sum(item["bytes"] for item in records)})
            shutil.rmtree(source)
        core.write(output / "source-cleanup.json", {"allOwnedWorkflowsFinished": True, "removed": cleanups})
        protocol["sourceCleanup"] = core.file_record(output / "source-cleanup.json")
        protocol["elapsedSeconds"] = time.monotonic() - started
        if protocol["elapsedSeconds"] >= timeout:
            protocol["readyCandidate"] = False
        core.write(protocol_path, protocol)
    print({key: protocol.get(key) for key in ("readyCandidate", "candidateCounts", "negativeCounts", "error", "elapsedSeconds")}, flush=True)
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-source", "final-source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--device-serial", default="127.0.0.1:5555")
    return 0 if run(**vars(parser.parse_args()))["readyCandidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
