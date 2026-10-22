"""Independent current public and source-bound Task13 four-control revalidation."""

import argparse
import copy
from pathlib import Path

from . import task12_13_formal_core as core
from . import task13_formal_agent as formal
from . import task13_arkts_common_entry_audit as entry
from scripts.run_runtime_transition_matrix import validate_report


def require(value, message):
    if not value:
        raise ValueError("Task13 independent control proof: " + message)


def verify_cleanup(path, haps):
    cleanup = core.load(path)
    require(cleanup.get("performed") is True and cleanup.get("binaryHashesRecordedBeforeRemoval") is True and
            cleanup.get("binariesRetained") is False and cleanup.get("temporaryBuildRemoved") is True,
            "binary cleanup incomplete")
    records = {item["path"]: item for item in cleanup.get("binaryHashes", [])}
    for hap in haps:
        require(all(records.get(hap["path"], {}).get(key) == hap[key] for key in ("bytes", "sha256")) and
                not Path(hap["path"]).exists(), "compiled HAP does not match hash-before-delete receipt")
    return core.file_record(path)


def verified_formal_path(root):
    original_path = root / "formal.json"
    original = core.load(original_path)
    anchors = {}
    for role in ("base", "final"):
        path = root / "formal.strict-evidence" / role / "runtime.json"
        report = core.load(path)
        anchors[role] = {**core.file_record(path), "counts": {
            key: report["semantic"][key] for key in ("passed", "failed", "notScored")}}
    if original["diagnostics"]["calibrationAnchors"] == anchors:
        return original_path
    revision = core.load(root / "formal-anchor-revision.json")
    require(entry.checked_record(revision["originalReport"]) == original_path and
            revision["newRuntimeExecuted"] is False and revision["currentDynamicAnchors"] == anchors,
            "obsolete anchor metadata requires an explicit source-bound revision")
    revised_path = entry.checked_record(revision["reviewedReport"])
    require(revised_path == root / "formal.reviewed.json", "reviewed formal report path differs")
    expected = copy.deepcopy(original)
    expected["diagnostics"]["calibrationAnchors"] = anchors
    expected["diagnostics"]["anchorMetadataRevision"] = {
        "scope": "metadata_only_no_new_runtime", "originalReport": core.file_record(original_path)}
    require(core.load(revised_path) == expected, "anchor revision changed runtime/semantic/compile evidence")
    return revised_path


def verify(*, protocol_directory, output):
    root = protocol_directory.resolve()
    protocol_path = root / "protocol.json"
    protocol = core.load(protocol_path)
    contract = core.load(formal.SPEC.contract)
    require(core.sha256(formal.SPEC.contract) == formal.REVISION5_SHA256 == core.sha256(formal.SPEC.audited_contract),
            "canonical contract differs from reviewed revision5")
    require(protocol["canonicalContract"] == core.file_record(formal.SPEC.contract), "runtime contract hash differs")
    require(0 < protocol["timeoutSeconds"] <= 3600 and protocol["elapsedSeconds"] < protocol["timeoutSeconds"],
            "single overall runtime budget exceeded")
    inventories = protocol["sourceInventories"]
    require(len({item["source"] for item in inventories.values()}) == 4 and
            inventories["base"]["sha256"] == inventories["negative"]["sha256"] and
            inventories["final"]["sha256"] == inventories["agent"]["sha256"], "independent controls/source copies differ")
    require(inventories["base"]["sha256"] == core.source_inventory(core.ROOT / "13_user_verification_base_25_03_1")["sha256"] and
            inventories["final"]["sha256"] == core.source_inventory(core.ROOT / "final_dev_nodes/13_user_verification_final_25_03_2")["sha256"],
            "protocol does not use current migrated base/final source")
    result = {"taskId": formal.SPEC.task_id, "platform": "arkts", "readyCandidate": False,
              "scope": "Independent retained fresh-runtime revalidation, not a new runtime execution",
              "protocol": core.file_record(protocol_path), "contract": core.file_record(formal.SPEC.contract),
              "reports": []}
    for name, counts in (("base", (0, 10, 0)), ("final", (10, 0, 0)),
                         ("agent", (10, 0, 0)), ("negative", (0, 10, 0))):
        path = root / "formal.strict-evidence" / name / "runtime.json" if name != "negative" else root / "random-base-agent.json"
        report = core.load(path)
        role = "agent" if name == "negative" else name
        inventory = inventories[name]
        core.validate_runtime_report(report, spec=formal.SPEC, platform="arkts", role=role,
            source=Path(inventory["source"]), inventory=inventory, contract=contract,
            lineage=core.calibrator_lineage(formal.SPEC, "arkts"))
        evidence = report["provenance"]["runtimeEvidence"]
        raw_path, build_path = [entry.checked_record(evidence[key]) for key in ("execution", "build")]
        has_entries = any(row.get("entryFailureEvidence") for row in report["semantic"]["cases"])
        native_proof = entry.inspect_report(raw_path, build_path, inventory=inventory, contract=contract,
                                             include_entry_cases=has_entries)
        used = set()
        for row in report["semantic"]["cases"]:
            if row.get("entryFailureEvidence"):
                entry.validate_entry_failure(row, report, used, contract=contract)
        actual = tuple(report["semantic"][key] for key in ("passed", "failed", "notScored"))
        require(actual == counts, "actual control polarity differs: " + name)
        cleanup_path = path.parent / "cleanup.json" if name != "negative" else root / "negative-cleanup.json"
        proof = {"role": name, "report": core.file_record(path), "counts": list(actual),
                 "independentValidated": True, "entryCases": len(used),
                 "freshNativeProcess": core.load(raw_path)["pid"], "nativeProof": native_proof,
                 "cleanup": verify_cleanup(cleanup_path, core.load(build_path)["haps"]), "publicPassed": False}
        try:
            validate_report(report, contract)
            proof["publicPassed"] = True
        except Exception as error:
            proof["publicError"] = f"{type(error).__name__}: {error}"
        result["reports"].append(proof)
    formal_path = verified_formal_path(root)
    formal_report = core.load(formal_path)
    require(formal_report["compile"].get("passed") is True and
            formal_report["compile"].get("status") == "passed", "candidate standalone compile did not pass")
    application_path = entry.checked_record(formal_report["compile"]["evidence"])
    application = core.load(application_path)
    require(application.get("source") == inventories["agent"]["source"] and
            all(application.get(key) is True for key in ("passed", "productionUnchanged", "copiedProductionUnchanged", "temporaryProjectRemoved")),
            "candidate application compile source binding differs")
    entry.checked_record(application["log"])
    result["applicationCleanup"] = verify_cleanup(root / "formal.strict-evidence/application-compile/cleanup.json",
                                                    [application["hap"]])
    final_proof = {"role": "formal", "report": core.file_record(formal_path), "publicPassed": False}
    try:
        validate_report(formal_report, contract)
        final_proof["publicPassed"] = True
    except Exception as error:
        final_proof["publicError"] = f"{type(error).__name__}: {error}"
    result["reports"].append(final_proof)
    cleanup_path = entry.checked_record(protocol["sourceCleanup"])
    source_cleanup = core.load(cleanup_path)
    require(source_cleanup.get("allOwnedWorkflowsFinished") is True and len(source_cleanup["removed"]) == 4 and
            all(not Path(item["source"]).exists() for item in source_cleanup["removed"]), "temporary inputs were not cleaned")
    result["sourceCleanup"] = core.file_record(cleanup_path)
    result["readyCandidate"] = all(item["publicPassed"] for item in result["reports"])
    core.write(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = verify(**vars(parser.parse_args()))
    print({"readyCandidate": result["readyCandidate"], "publicPassed":
           sum(proof["publicPassed"] for proof in result["reports"]), "reports": len(result["reports"])})
    return 0 if result["readyCandidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
