"""Projection-free Task12 native UI calibration, copy controls and exact replay.

Public review hook: validate_report_evidence(report, canonical_contract).
Legacy final-template reports cannot satisfy this gate by adding metadata.
"""

import argparse
import importlib
from dataclasses import replace
import json
from pathlib import Path
import re
import shutil
import tempfile
import time

from . import task12_13_formal_core as core
from . import task12_13_runtime_support as support
from . import task12_arkts_replay_v2 as replay
from scripts.run_runtime_transition_matrix import validate_report as public_validate

PROTOCOL = "task12.actual-ui-effects.v2"
HERE = Path(__file__).parent
FACTS = HERE / "Task12ActualUiFacts.cjs"
RUNNER = HERE / "Task12ActualUiDevice.cjs"
CONTRACT = replay.CONTRACT
require = replay.require
_derive = replay.derive_common


def derive_common(*, target, **kwargs):
    _derive(target=target, **kwargs)
    source = target.read_text()
    marker = "  const reportFile = path.join(output, 'arkts_12_report_room_base.device-entry.json');"
    require(source.count(marker) == 1, "current common report boundary changed")
    source = source.replace(marker,
        "  report.nativeProtocol = " + json.dumps(PROTOCOL) + ";\n" +
        "  report.provenance.actualUiFacts = " + json.dumps(core.file_record(FACTS)) + ";\n" + marker)
    target.write_text(source)


def configure():
    replay.FACTS = FACTS
    replay.RUNNER = RUNNER
    replay.derive_common = derive_common


def specification():
    return replace(replay.formal.SPEC, contract=CONTRACT, audited_contract=replay.formal.SPEC.contract,
        expected_contract_sha256=replay.CONTRACT_SHA, calibration_evidence={},
        calibrator_files={"arkts": (replay.frozen.BASE_RUNNER, FACTS, RUNNER, Path(__file__))})


def evaluate(*, task, platform, source, role, output, deadline, serial):
    configure()
    inventory = core.source_inventory(source)
    result = replay.evaluate(task=task, platform=platform, source=source, role=role, output=output,
                             deadline=deadline, serial=serial)
    require(core.source_inventory(source)["sha256"] == inventory["sha256"], "production changed during native run")
    inventory_path = output.with_suffix(".input.json")
    core.write(inventory_path, inventory)
    result["provenance"]["runtimeEvidence"]["sourceInventory"] = core.file_record(inventory_path)
    result["diagnostics"]["strictRuntime"]["nativeProtocol"] = PROTOCOL
    core.write(output, result)
    return result


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute():
        path = core.ROOT / path
    actual = core.file_record(path)
    require(all(actual[key] == record[key] for key in ("sha256", "bytes")), "current runtime artifact hash/size differs")
    return path.resolve()


def flatten(tree):
    nodes = [tree["attributes"]] if "attributes" in tree else []
    for child in tree.get("children", []):
        nodes.extend(flatten(child))
    return nodes


def validate_report_evidence(report, contract, *, deadline=None):
    """Only current actual-native protocol; no old-result metadata upgrades."""
    configure()
    require(report.get("taskId") == contract.get("taskId") == "12_report_room" and
            report.get("platform") == "arkts" and core.sha256(CONTRACT) == replay.CONTRACT_SHA and
            core.load(CONTRACT) == contract, "task/platform/canonical contract differs")
    require(report.get("diagnostics", {}).get("strictRuntime", {}).get("nativeProtocol") == PROTOCOL,
            "legacy projection report is withdrawn, not repairable by metadata aliases")
    evidence = report["provenance"]["runtimeEvidence"]
    inventory_path = checked(evidence["sourceInventory"])
    inventory = core.load(inventory_path)
    raw_path, shim_path = checked(evidence["raw"]), checked(evidence["build"])
    require(raw_path.is_relative_to(core.ROOT / "experiment_results"), "raw runtime outside audit root")
    raw, shim = core.load(raw_path), core.load(shim_path)
    require(raw.get("nativeProtocol") == PROTOCOL, "raw native execution is not the replacement protocol")
    application_path = checked(shim["applicationBuild"])
    application = core.load(application_path)
    require(application["source"] == shim["source"] == inventory["source"] == report["provenance"]["candidateSource"] and
            application.get("passed") is True and all(application.get(key) is True for key in
            ("productionUnchanged", "copiedProductionUnchanged", "temporaryProjectRemoved")),
            "actual original-production compile/source binding missing")
    indexed = {item["path"]: item for item in inventory["files"]}
    require(application.get("sources") and all(indexed.get(item["path"]) == item for item in application["sources"]),
            "compiled production does not match the supplied source inventory")
    checked(application["log"])
    cleanup_path = evidence.get("currentCleanup")
    require(cleanup_path is not None, "current hash-before-delete receipt missing")
    cleanup = core.load(checked(cleanup_path))
    hap = application["hap"]
    require(cleanup.get("performed") is True and cleanup.get("binaryHashesRecordedBeforeRemoval") is True and
            cleanup.get("binariesRetained") is False and cleanup.get("temporaryBuildRemoved") is True and
            not Path(hap["path"]).exists() and Path(hap["path"]).is_relative_to(application_path.parent) and
            any(all(item.get(key) == hap[key] for key in ("path", "sha256", "bytes"))
                for item in cleanup.get("binaryHashes", [])), "actual current HAP cleanup receipt differs")
    require(all(raw["compile"]["hap"][key] == hap[key] for key in ("sha256", "bytes")),
            "actual executed HAP differs from source-specific compiled binary")
    commands = raw["diagnostics"]["commands"]
    for command in commands:
        checked(command["log"])
        require(command["exitCode"] in (0, 255), "actual native transport command failed")
    require(sum(command["args"][:2] == ["install", "-r"] for command in commands) == 10 and
            sum(command["args"][:3] == ["shell", "aa", "start"] for command in commands) == 10 and
            raw["diagnostics"]["cleanup"]["ownedAppUninstalled"] is True,
            "ten independent actual installs/ability starts or cleanup missing")
    is_entry = all(row.get("entryFailureEvidence") for row in report["semantic"]["cases"])
    recomputed = None
    if is_entry:
        require(checked(raw["provenance"]["actualUiFacts"]) == FACTS and
                raw["provenance"]["actualUiFacts"]["sha256"] == core.sha256(FACTS),
                "replacement complete-entry UI guard was not used")
        used = set()
        for row in report["semantic"]["cases"]:
            replay.entry.validate_entry_failure(row, report, used, contract=contract)
        script = """const fs=require('node:fs'),crypto=require('node:crypto');const F=require(process.argv[1]);
const raw=JSON.parse(fs.readFileSync(process.argv[2]));const root=process.argv[3];let samples=0;
const flat=n=>[...(n.attributes?[n.attributes]:[]),...(n.children||[]).flatMap(flat)];
for(const row of raw.semantic.cases)for(const point of row.checkpoints){
 if(point.name==='positive_leave_control')continue;
 const record=point.layout;const file=require('node:path').resolve(root,record.path);const bytes=fs.readFileSync(file);
 if(bytes.length!==record.bytes||crypto.createHash('sha256').update(bytes).digest('hex')!==record.sha256)throw Error('Native layout changed');
 F.closedBase(flat(JSON.parse(bytes)));samples++;}
process.stdout.write(JSON.stringify({validated:true,completeNativeClosureSamples:samples}));
"""
        log = raw_path.parent / "independent-current-entry-closure.log"
        support.run(["node", "-e", script, str(FACTS), str(raw_path), str(core.ROOT)],
            deadline=deadline or time.monotonic() + 120, phase="Current native entry UI closure recomputation", log=log)
        recomputed = core.load(log)
    else:
        require(checked(raw["provenance"]["facts"]) == FACTS and checked(raw["provenance"]["runner"]) == RUNNER,
                "legacy final-template producer cannot satisfy current native evidence")
        config = core.load(checked(raw["provenance"]["config"]))
        require(config["source"] == inventory["source"] and config["hap"] == hap["path"] and
                isinstance(raw.get("nativeNonce"), str) and re.fullmatch(r"[0-9a-f]{32}", raw["nativeNonce"]),
                "current native process/config/source binding differs")
        require(report["semantic"]["cases"] == raw["semantic"]["cases"], "runtime cases were rewritten after actual execution")
        for row in raw["semantic"]["cases"]:
            for point in row["checkpoints"]:
                nodes = flatten(core.load(checked(point["layout"])))
                roots = [node for node in nodes if node.get("type") == "root"]
                require(len(roots) == 1 and roots[0].get("bundleName") == config["bundle"] and
                        roots[0].get("pagePath") == "pages/Index" and roots[0].get("focused") == "true",
                        "actual native checkpoint not in original focused window")
                if point["name"] == "common_start":
                    require(any(node.get("id") == "room_details_id" and node.get("text") == "!room:example.org" and
                            node.get("visible") == "true" for node in nodes), "actual common room identity missing")
        log = raw_path.parent / "independent-current-recomputation.log"
        recomputed = replay.verify_native(raw_path, CONTRACT, bundle=config["bundle"],
            deadline=deadline or time.monotonic() + 120, log=log)
    core.validate_runtime_report(report, spec=specification(), platform="arkts", role=report["role"],
        source=Path(inventory["source"]), inventory=inventory, contract=contract,
        lineage=core.calibrator_lineage(specification(), "arkts"))
    return {"validated": True, "nativeProtocol": PROTOCOL, "currentRunOnly": True,
            "raw": core.file_record(raw_path), "application": core.file_record(application_path),
            "cleanup": cleanup_path, "nativeRecomputation": recomputed,
            "counts": {key: report["semantic"][key] for key in ("passed", "failed", "notScored")}}


def validate_entry_failure(row, report, used_observation_ids, *, contract):
    require(row.get('entryFailureEvidence', {}).get('policyId') == 'arkts.task12.actual-ui-disabled-action.v2',
            'unknown disabled-action entry policy')
    from .task12_arkts_runtime_admission import validate_report_evidence as admit
    admit(report, contract)
    raw_record = report['provenance']['runtimeEvidence']['raw']
    raw = core.load(checked(raw_record))
    selected = [item for item in raw['semantic']['cases'] if item['caseId'] == row['caseId']]
    require(len(selected) == 1 and selected[0] == row, 'disabled-action row differs from actual native runtime')
    identity = (raw_record['sha256'], row['caseRunId'])
    require(identity not in used_observation_ids, 'disabled-action native session reused')
    used_observation_ids.add(identity)


def run(*, run_root, output, prior_repair, serial):
    configure()
    started = time.monotonic()
    # Conservative shared repair-episode deadline; never grant another 3600s.
    epoch_deadline = int(prior_repair.stat().st_birthtime) + 3598
    remaining = min(3600.0, epoch_deadline - time.time())
    require(remaining > 0, "shared repair-episode deadline exhausted")
    deadline = started + remaining
    output = output.resolve()
    require(not output.exists(), "refusing existing actual-ui protocol evidence")
    output.mkdir(parents=True)
    budget = core.load(run_root / "reports/arkts_12_report_room_execution-budget.json")
    original_report = run_root / "reports/arkts_12_report_room_agent.json"
    old = core.load(original_report)
    routers = {str(core.ROOT / 'scripts/run_task_runtime_tests.py'), str(core.ROOT / 'scripts/run_runtime_transition_matrix.py')}
    all_protected = replay.protected_records(run_root)
    protected = [record for record in all_protected if record['path'] not in routers]
    protected.extend(core.file_record(path) for path in (FACTS, RUNNER, Path(__file__)))
    core.write(output / "protected-inputs.json", protected)
    protocol = {"nativeProtocol": PROTOCOL, "readyCandidate": False, "newModelCall": False,
        "singleDeadlineMonotonic": deadline, "sharedEpisodeDeadlineEpoch": epoch_deadline,
        "remainingBudgetAtStart": remaining, "priorRepair": str(prior_repair), "originalGenerationDurationUnchanged": True,
        "controlsAreNotModelResults": True, "reports": [],
        "protectionScope": "Original model inputs/artifacts and frozen helpers; parent-owned routers may be integrated concurrently",
        "parentOwnedRoutersBefore": [record for record in all_protected if record['path'] in routers]}
    core.write(output / "protocol.json", protocol)
    temporary = Path(tempfile.mkdtemp(prefix="ltb-task12-actual-ui-inputs-"))
    sources = {}
    try:
        require(old["compile"]["passed"] is True and budget["isolationAudit"]["complete"] is True and
                not budget["isolationViolations"], "original model compile/recursive isolation proof unavailable")
        sources["model"] = temporary / "candidate"
        replay.reconstruct(budget, sources["model"], output)
        for label, relative in (("base", "12_report_room_base_25_04_3_rebuilt"),
                                ("final", "final_dev_nodes/12_report_room_final_25_05_4")):
            source = core.ROOT / relative
            original = core.load(run_root / "reports/arkts_12_report_room_agent.strict-evidence" / label / "runtime.json")
            require(core.source_inventory(source)["sha256"] == original["provenance"]["sourceInventorySha256"],
                    "immutable calibration source differs from frozen run")
            sources[label] = Path(tempfile.mkdtemp(prefix="control-", dir=temporary))
            shutil.copytree(source, sources[label], dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", "build", ".gradle", ".hvigor", "oh_modules", "node_modules"))
        for label, original in (("negative", "base"), ("positive", "final")):
            sources[label] = Path(tempfile.mkdtemp(prefix="control-", dir=temporary))
            shutil.copytree(sources[original], sources[label], dirs_exist_ok=True)
        inventories = {label: core.source_inventory(source) for label, source in sources.items()}
        core.write(output / "source-inventories.json", inventories)
        task, contract = specification(), core.load(CONTRACT)
        for label in ("base", "final", "negative", "positive", "model"):
            role = label if label in {"base", "final"} else "agent"
            path = output / label / "runtime.json"
            try:
                result = evaluate(task=task, platform="arkts", source=sources[label], role=role,
                    output=path, deadline=deadline, serial=serial)
            finally:
                cleanup_path = path.parent / "cleanup.json"
                core.write(cleanup_path, core.cleanup_artifacts(path.parent))
            result["provenance"]["runtimeEvidence"]["currentCleanup"] = core.file_record(cleanup_path)
            core.write(path, result)
            proof = validate_report_evidence(result, contract, deadline=deadline)
            core.write(path.parent / "independent-proof.json", proof)
            actual = proof["counts"]
            expected = {"passed": 0, "failed": 10, "notScored": 0} if label in {"base", "negative"} else {"passed": 10, "failed": 0, "notScored": 0}
            if label != "model":
                require(actual == expected, "actual replacement calibration/copy control differs: " + label)
            protocol["reports"].append({"label": label, "role": role, "runtime": core.file_record(path),
                "proof": core.file_record(path.parent / "independent-proof.json"), "counts": actual, "publicPassed": False})
            core.write(output / "protocol.json", protocol)
            print({"label": label, "counts": actual, "independentValidated": True, "publicPendingAdmission": True}, flush=True)
        bundle = {"nativeProtocol": PROTOCOL, "contract": core.file_record(CONTRACT),
            "sourceParameterizedControls": {}, "episodeDeadlineEpoch": epoch_deadline,
            "producerHashes": [core.file_record(path) for path in (FACTS, RUNNER, Path(__file__))]}
        for item in protocol["reports"]:
            path = Path(item["runtime"]["path"])
            report = core.load(path)
            evidence = report["provenance"]["runtimeEvidence"]
            bundle["sourceParameterizedControls"][item["label"]] = {"reportPath": str(path),
                "raw": evidence["raw"], "sourceInventory": evidence["sourceInventory"],
                "build": evidence["build"], "currentCleanup": evidence["currentCleanup"]}
        bundle_path = output / "admission-bundle.json"
        core.write(bundle_path, bundle)
        from scripts import run_runtime_transition_matrix as matrix
        importlib.reload(matrix)
        for item in protocol["reports"]:
            path = Path(item["runtime"]["path"])
            report = core.load(path)
            report["provenance"]["runtimeEvidence"]["admissionBundle"] = core.file_record(bundle_path)
            core.write(path, report)
            item["runtime"] = core.file_record(path)
        for item in protocol["reports"]:
            matrix.validate_report(core.load(Path(item["runtime"]["path"])), contract)
            item["publicPassed"] = True
        core.write(output / "protocol.json", protocol)
        model = core.load(output / "model/runtime.json")
        model["compile"] = old["compile"]
        model["codeGeneration"] = old["codeGeneration"]
        model["calibration"] = {"passed": True, "base": protocol["reports"][0]["counts"], "final": protocol["reports"][1]["counts"]}
        model["semanticReplay"] = {"originalReport": core.file_record(original_report), "newModelCall": False,
            "reconstruction": core.file_record(output / "reconstruction.json"), "originalTimingReplaced": False}
        model["publication"] = {"eligible": True, "scope": "evaluator-only replay; not a new model run"}
        public_validate(model, contract)
        validate_report_evidence(model, contract, deadline=deadline)
        core.write(output / "agent.replay.json", model)
        protocol["formalReport"] = core.file_record(output / "agent.replay.json")
        protocol["readyCandidate"] = True
    except Exception as error:
        protocol["error"] = f"{type(error).__name__}: {error}"
    finally:
        files = [core.file_record(path) for path in sorted(temporary.rglob("*")) if path.is_file()]
        core.write(output / "source-cleanup.json", {"allOwnedWorkflowFinished": True, "source": str(temporary),
            "files": files, "fileCount": len(files), "bytes": sum(item["bytes"] for item in files)})
        shutil.rmtree(temporary)
        protocol["sourceCleanup"] = core.file_record(output / "source-cleanup.json")
        protocol["protectedOriginalsUnchanged"] = all(core.file_record(Path(item["path"])) == item for item in protected)
        protocol["parentOwnedRoutersAfter"] = [core.file_record(Path(path)) for path in sorted(routers)]
        protocol["elapsedSeconds"] = time.monotonic() - started
        protocol["readyCandidate"] = protocol["readyCandidate"] and protocol["protectedOriginalsUnchanged"] and time.monotonic() < deadline
        core.write(output / "protocol.json", protocol)
    print({key: protocol.get(key) for key in ("readyCandidate", "error", "elapsedSeconds")}, flush=True)
    return protocol


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-repair", type=Path, required=True)
    parser.add_argument("--serial", default="127.0.0.1:5555")
    raise SystemExit(0 if run(**vars(parser.parse_args()))["readyCandidate"] else 2)
