"""Reuse only audited Task12 production application compilation for exact source copies."""

from pathlib import Path

try:
    from . import task12_13_formal_core as core
except ImportError:
    import task12_13_formal_core as core


def verify_record(record):
    path = Path(record["path"])
    if not path.is_absolute():
        path = core.ROOT / path
    actual = core.file_record(path)
    if any(actual[key] != record[key] for key in ("bytes", "sha256")):
        raise ValueError("Task12 application compile audit artifact changed")
    return path


def bind_source_copy(*, source, prior_report, platform, output):
    prior = core.load(prior_report)
    if prior.get("taskId") != "12_report_room" or prior.get("platform") != platform:
        raise ValueError("Task12 application evidence identity differs")
    inventory = core.source_inventory(source)
    phases = prior["diagnostics"]["phases"]
    role = "agent" if platform == "android" else "final"
    phase = next(item for item in phases if item["role"] == role)
    if phase["sourceInventorySha256"] != inventory["sha256"]:
        raise ValueError("Task12 source copy differs from compiled source inventory")
    evidence = []
    if platform == "android":
        compilation = prior["compile"]
        if (compilation.get("passed") is not True or compilation.get("exitCode") != 0 or
                compilation.get("scope") != "standalone_candidate_application_build" or
                compilation.get("source") != phase["source"]):
            raise ValueError("Task12 standalone Android app compile not established")
        for item in (compilation["log"], compilation["repositoryConfiguration"]):
            evidence.append(core.file_record(verify_record(item)))
        artifacts = compilation["artifacts"]
        cleanup = next(item for item in prior["diagnostics"]["cleanup"] if item["role"] == "application_compile")
    elif platform == "arkts":
        runtime_path = prior_report.resolve().with_suffix(".strict-evidence") / "final/runtime.json"
        runtime = core.load(runtime_path)
        if runtime["provenance"]["sourceInventorySha256"] != inventory["sha256"]:
            raise ValueError("Task12 plain HAP source inventory differs")
        shim_path = verify_record(runtime["provenance"]["runtimeEvidence"]["build"])
        shim = core.load(shim_path)
        build_path = verify_record(shim["applicationBuild"])
        compilation = core.load(build_path)
        if (compilation.get("passed") is not True or compilation.get("exitCode") != 0 or
                compilation.get("productionUnchanged") is not True or
                compilation.get("copiedProductionUnchanged") is not True or
                compilation.get("source") != phase["source"] or
                "assembleHap" not in compilation.get("command", []) or
                any("ohosTest" in part for part in compilation["command"])):
            raise ValueError("Task12 unchanged standalone production HAP compile not established")
        evidence += [core.file_record(runtime_path), core.file_record(shim_path), core.file_record(build_path),
                     core.file_record(verify_record(compilation["log"]))]
        artifacts = [compilation["hap"]]
        cleanup = core.load(runtime_path.parent / "cleanup.json")
    else:
        raise ValueError("Task12 application evidence platform unsupported")
    hashes = {(item["sha256"], item["bytes"]) for item in cleanup["binaryHashes"]}
    if not artifacts or any((item["sha256"], item["bytes"]) not in hashes for item in artifacts):
        raise ValueError("Task12 compiled binary hashes missing from cleanup manifest")
    receipt = {
        "taskId": "12_report_room", "platform": platform, "scope": "application_compile_only",
        "runtimeEvidenceReused": False, "source": str(source.resolve()),
        "sourceInventorySha256": inventory["sha256"], "sourceFileCount": inventory["fileCount"],
        "compiledSource": phase["source"], "priorReport": core.file_record(prior_report),
        "compileAuditArtifacts": evidence, "compiledBinaryHashes": artifacts,
        "binding": "full source inventory equality; directory materialization differs",
    }
    core.write(output, receipt)
    return receipt


def reuse_compiler(receipt_path):
    receipt = core.load(receipt_path)

    def compile_application(*, platform, source, output, deadline, command):
        if (receipt.get("taskId") != "12_report_room" or receipt.get("platform") != platform or
                receipt.get("scope") != "application_compile_only" or
                receipt.get("runtimeEvidenceReused") is not False):
            raise ValueError("Task12 compile receipt identity differs")
        if core.source_inventory(source)["sha256"] != receipt["sourceInventorySha256"]:
            raise ValueError("Task12 compile receipt source inventory differs")
        for record in [receipt["priorReport"], *receipt["compileAuditArtifacts"]]:
            verify_record(record)
        return {"passed": True, "status": "passed", "scope": "standalone_candidate_application_build",
                "source": str(source.resolve()), "reused": True, "runtimeEvidenceReused": False,
                "command": command or "audited unchanged standalone application compile",
                "evidence": core.file_record(receipt_path)}

    return compile_application
