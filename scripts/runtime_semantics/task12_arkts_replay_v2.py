"""Task12 evaluator-only replay of the exact fresh-v2 baseline and model patch.

Frozen runners/helpers are read-only inputs. Derived entry bindings and the new
native UI/effect observer are separate, versioned evaluator artifacts.
"""

import argparse
import copy
from dataclasses import replace
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

sys.dont_write_bytecode = True

from . import task12_13_formal_core as core
from . import task12_13_runtime_support as support
from . import task12_arkts_strict_runtime as frozen
from . import task12_formal_agent as formal
from . import task12_live_entry_validation as entry
from .task14_15_formal_core import build_arkts_application
from scripts.run_runtime_transition_matrix import validate_report

FACTS = Path(__file__).with_name("Task12ReplayFacts.cjs")
RUNNER = Path(__file__).with_name("Task12ReplayDevice.cjs")
ROOT = core.ROOT
CONTRACT = ROOT / "benchmark_tasks/12_report_room/transitions.json"
CONTRACT_SHA = "365670eba603c9762842a836b3b5385c37f925abdf3e88cc1d3d355b3f64531e"


def require(value, reason):
    if not value:
        raise ValueError("Task12 evaluator-only replay: " + reason)


def checked(record):
    path = Path(record["path"])
    require(core.sha256(path) == record["sha256"] and path.stat().st_size == record["bytes"], "input artifact changed")
    return path


def extract_source(archive, target):
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            name = Path(member.name)
            require(not name.is_absolute() and ".." not in name.parts and (member.isdir() or member.isfile()),
                    "unsafe source archive member")
        source.extractall(target)


def git(source, *arguments):
    return subprocess.check_output(["git", "-C", str(source), "-c", "core.autocrlf=false", *arguments],
                                   text=True, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}).strip()


def reconstruct(budget, target, output):
    archive, patch = checked(budget["candidateBaseline"]), checked(budget["candidatePatch"])
    target.mkdir()
    extract_source(archive, target)
    git(target, "init", "-q")
    git(target, "add", "--all", "--force", ".")
    require(git(target, "write-tree") == budget["candidateBaseline"]["tree"], "frozen baseline Git tree differs")
    git(target, "apply", "--check", "--index", str(patch))
    git(target, "apply", "--index", str(patch))
    require(git(target, "write-tree") == budget["candidatePatch"]["tree"], "exact baseline+patch tree differs")
    inventory = core.source_inventory(target)
    git(target, "archive", "--format=tar.gz", "--output=" + str(output / "candidate.exact-source.tar.gz"),
        budget["candidatePatch"]["tree"])
    core.write(output / "reconstruction.json", {"baseline": budget["candidateBaseline"], "patch": budget["candidatePatch"],
        "candidateTree": budget["candidatePatch"]["tree"], "sourceInventory": inventory,
        "archive": core.file_record(output / "candidate.exact-source.tar.gz"), "newModelCall": False,
        "candidateModifiedByEvaluator": False, "exactFrozenTreeVerified": True})
    return inventory


def derive_common(*, target, **arguments):
    frozen._derived_runner(template=frozen.BASE_RUNNER, target=target, **arguments)
    source = target.read_text()
    source = "const replayFacts = require(" + repr(str(FACTS)) + ");\n" + source
    old = """      if (caseRequests.map(item => item.url).join('|') !==
        ('/_matrix/client/v3/joined_rooms|/_matrix/client/v3/rooms/!room%3Aexample.org/state' +
          (available ? '|/_matrix/client/versions' : '')) ||
        caseRequests.some(item => item.authorization !== 'Bearer runtime-token')) throw new Error('Unexpected Matrix common-start requests');"""
    require(source.count(old) == 1, "frozen common-start derivation shape changed")
    source = source.replace(old, "      replayFacts.prefixRequests(caseRequests, roomId);")
    old_entry = "const entry = requireOne(stable.nodes, 'report_room_entry');"
    require(source.count(old_entry) == 1, "frozen report entry binding shape changed")
    source = source.replace(old_entry, "const entry = replayFacts.one(stable.nodes, 'entry');")
    old_row = "      rows.push({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'fail', transitionExecuted: false,"
    require(source.count(old_row) == 1, "frozen absence boundary shape changed")
    source = source.replace(old_row, "      [details, stable, restored].forEach(sample => replayFacts.closedBase(sample.nodes));\n" + old_row)
    target.write_text(source)


def verify_native(raw_path, contract_path, *, bundle, deadline, log):
    script = """const fs=require('node:fs'),crypto=require('node:crypto');
const F=require(process.argv[1]);
const read=p=>JSON.parse(fs.readFileSync(p));
const load=record=>{const bytes=fs.readFileSync(record.path);
 if(bytes.length!==record.bytes||crypto.createHash('sha256').update(bytes).digest('hex')!==record.sha256)throw Error('Native layout hash differs');
 return JSON.parse(bytes);};
process.stdout.write(JSON.stringify(F.verifyNative(read(process.argv[2]),read(process.argv[3]),load,process.argv[4])));
"""
    support.run(["node", "-e", script, str(FACTS), str(raw_path), str(contract_path), bundle],
                deadline=deadline, phase="Independent original native UI/effect recomputation", log=log)
    return core.load(log)


def evaluate(*, task, platform, source, role, output, deadline, serial):
    require(platform == "arkts" and core.sha256(CONTRACT) == CONTRACT_SHA, "task/platform/canonical contract differs")
    source, output = source.resolve(), output.resolve()
    evidence = output.with_suffix(".arkts-evidence")
    evidence.mkdir(parents=True, exist_ok=False)
    require(shutil.disk_usage(ROOT).free >= 8 * 1024**3, "storage protection: less than 8 GiB free")
    build_dir = evidence / "application-build"
    build = build_arkts_application(source=source, output=build_dir, deadline=deadline, label="task12-replay")
    require(build.get("passed") is True and all(build.get(key) is True for key in
        ("productionUnchanged", "copiedProductionUnchanged", "temporaryProjectRemoved")), "runtime production HAP compile/source binding failed")
    build_path = build_dir / "application-build.json"
    hap = Path(build["hap"]["path"])
    shim_path = evidence / "device-build-report.json"
    core.write(shim_path, {"status": "built_not_executed", "source": str(source), "role": role,
        "productionUnchanged": True, "sourceUnchanged": True, "copiedProductionUnchanged": True,
        "temporaryProjectRemoved": True, "hap": build["hap"], "applicationBuild": core.file_record(build_path)})
    common_runner = evidence / "common-entry.generated.cjs"
    derive_common(target=common_runner, bundle=frozen._bundle_name(source), hap=hap, build_report=shim_path,
                  contract=CONTRACT, serial=serial, port=18741)
    common_dir, common_log = evidence / "common-entry", evidence / "common-entry.log"
    contract = core.load(CONTRACT)
    with support.arkts_device_lock(serial=serial, deadline=deadline):
        support.wait_hdc_connected(serial=serial, deadline=deadline, log=evidence / "hdc-readiness.log")
        support.run(["node", str(common_runner), "--output", str(common_dir)], deadline=deadline,
                    phase="Task12 replay actual common production UI", log=common_log)
        common_path = common_dir / "arkts_12_report_room_base.device-entry.json"
        discovery = core.load(common_path)
        cases = discovery["semantic"]["cases"]
        missing = len(cases) == 10 and all(row["status"] == "fail" and row.get("entryFailureEvidence", {}).get("reportEntryCount") == 0 for row in cases)
        available = len(cases) == 10 and all(row.get("discovery", {}).get("entryAvailable") is True for row in cases)
        require(missing != available, "actual common-entry discovery incomplete/ambiguous")
        if missing:
            verification = entry.arkts.verify(common_path)
            verification["rawReport"] = core.file_record(common_path)
            verified_path = evidence / "independent-device-entry-verification.json"
            core.write(verified_path, verification)
            rows = entry.entry_rows(contract, discovery, common_path, "arkts", device_verification=core.file_record(verified_path))
            raw_path = common_path
            log = common_log
        else:
            config_path = evidence / "native-config.json"
            native_dir = evidence / "native-execution"
            core.write(config_path, {"source": str(source), "bundle": frozen._bundle_name(source),
                "hap": str(hap), "buildReport": str(build_path), "contract": str(CONTRACT),
                "hdc": str(frozen.HDC), "serial": serial, "port": 18742, "output": str(native_dir),
                "remainingSeconds": deadline - time.monotonic()})
            log = evidence / "native-command.log"
            support.run(["node", str(RUNNER), str(config_path)], deadline=deadline,
                        phase="Task12 replay original production native transitions", log=log)
            raw_path = native_dir / "runtime.native.json"
            raw = core.load(raw_path)
            require(raw["source"] == str(source) and raw["diagnostics"]["cleanup"]["ownedAppUninstalled"] is True,
                    "native production binding/cleanup missing")
            rows = raw["semantic"]["cases"]
            if not any(row["status"] == "not_scored" for row in rows):
                verification = verify_native(raw_path, CONTRACT, bundle=frozen._bundle_name(source), deadline=deadline,
                                             log=evidence / "independent-native-verification.log")
                core.write(evidence / "independent-native-verification.json", verification)
    return support.strict_report(task=task, platform=platform, source=source, role=role, rows=rows,
        runtime_compile={"passed": True, "status": "passed", "scope": "production HAP and source-bound native UI runtime"},
        lineage=core.calibrator_lineage(task, "arkts"), runtime_kind="openharmony api23 device uitest original production",
        transport="transport_completed", evidence={"build": core.file_record(shim_path), "raw": core.file_record(raw_path),
            "commonEntry": core.file_record(common_path), "runner": core.file_record(RUNNER), "facts": core.file_record(FACTS),
            "derivedCommonRunner": core.file_record(common_runner), "log": core.file_record(log)}, output=output)


def protected_records(run_root):
    files = [path for path in run_root.rglob("*") if path.is_file()]
    for pattern in ("task12*.py", "task12*.cjs", "Task12*.cjs", "verify_task12*.py"):
        files.extend(path for path in Path(__file__).parent.glob(pattern)
                     if path not in {Path(__file__), FACTS, RUNNER})
    files.extend(ROOT / "scripts" / name for name in ("run_task_runtime_tests.py", "run_runtime_transition_matrix.py"))
    freeze = ROOT / "experiment_results/runtime_transition_20261020/formal_task12_13_runtime_20261020/task13-entry-policy-v2-review/source-snapshot-manifest.json"
    files.extend(Path(item["path"]) for item in core.load(freeze)["files"])
    return [core.file_record(path) for path in sorted(set(files))]


def replay(*, run_root, output, serial):
    started = time.monotonic()
    deadline = started + 3600
    run_root, output = run_root.resolve(), output.resolve()
    require(not output.exists(), "refusing existing replay evidence")
    output.mkdir(parents=True)
    protected = protected_records(run_root)
    core.write(output / "protected-inputs.json", protected)
    original = output / "original"
    original.mkdir()
    old_name = "arkts_12_report_room_agent"
    shutil.copytree(run_root / "reports" / (old_name + ".strict-evidence"), original / "strict-evidence")
    for name in (old_name + ".json", "arkts_12_report_room_execution-budget.json", "arkts_12_report_room_isolation-audit.json"):
        shutil.copy2(run_root / "reports" / name, original / name)
    budget = core.load(run_root / "reports/arkts_12_report_room_execution-budget.json")
    old_report = core.load(run_root / "reports" / (old_name + ".json"))
    require(budget["isolationAudit"]["complete"] is True and not budget["isolationViolations"] and
            old_report["compile"]["passed"] is True and budget["codeGenerated"] is True,
            "original generation/compile/isolation evidence is not available")
    completion = {"newModelCall": False, "readyCandidate": False, "deadlineMonotonic": deadline,
                  "timeoutSeconds": 3600, "timingScope": "evaluator-only reconstruction/calibration/replay/cleanup; original model duration unchanged"}
    temporary = Path(tempfile.mkdtemp(prefix="ltb-task12-exact-replay-"))
    try:
        sources = {"agent": temporary / "candidate"}
        inventory = reconstruct(budget, sources["agent"], output)
        original_build = core.load(original / "strict-evidence/agent/runtime.arkts-evidence/application-build/application-build.json")
        indexed = {item["path"]: item for item in inventory["files"]}
        require(all(indexed.get(item["path"]) == item for item in original_build["sources"]),
                "reconstructed production differs from original actually compiled candidate")
        for role, relative in (("base", "12_report_room_base_25_04_3_rebuilt"),
                               ("final", "final_dev_nodes/12_report_room_final_25_05_4")):
            src = ROOT / relative
            previous = core.load(original / "strict-evidence" / role / "runtime.json")
            require(core.source_inventory(src)["sha256"] == previous["provenance"]["sourceInventorySha256"],
                    "immutable calibration source differs from original fresh-v2 input")
            sources[role] = temporary / role
            shutil.copytree(src, sources[role], ignore=shutil.ignore_patterns(".git", "build", ".hvigor", ".gradle", "node_modules", "oh_modules"))
        core.write(output / "source-inventories.json", {role: core.source_inventory(source) for role, source in sources.items()})
        task = replace(formal.SPEC, contract=CONTRACT, audited_contract=formal.SPEC.contract,
                       expected_contract_sha256=CONTRACT_SHA)
        result = core.score(spec=task, platform="arkts", source=sources["agent"], base_source=sources["base"],
            final_source=sources["final"], output=output / "agent.replay.json", compile_passed=True,
            compile_command=old_report["compile"]["command"], timeout=deadline - time.monotonic(),
            evaluator=lambda **kwargs: evaluate(**kwargs, serial=serial))
        result["compile"] = copy.deepcopy(old_report["compile"])
        result["codeGeneration"] = copy.deepcopy(old_report["codeGeneration"])
        result["semanticReplay"] = {"newModelCall": False, "originalReport": core.file_record(run_root / "reports" / (old_name + ".json")),
            "reconstruction": core.file_record(output / "reconstruction.json"), "originalTimingReplaced": False}
        core.write(output / "agent.replay.json", result)
        proofs = []
        for role in ("base", "final", "agent"):
            path = output / "agent.replay.strict-evidence" / role / "runtime.json"
            if path.exists():
                proof = {"role": role, "report": core.file_record(path), "publicPassed": False}
                try:
                    validate_report(core.load(path), core.load(CONTRACT))
                    proof["publicPassed"] = True
                except Exception as error:
                    proof["error"] = str(error)
                proofs.append(proof)
        try:
            validate_report(result, core.load(CONTRACT))
            completion["formalPublicPassed"] = True
        except Exception as error:
            completion["formalPublicPassed"] = False
            completion["formalPublicError"] = str(error)
        completion.update(calibration=result["calibration"], semantic={key: result["semantic"][key]for key in ("passed", "failed", "notScored")}, publicProofs=proofs)
        completion["semanticCoverageComplete"] = result["semantic"]["notScored"] == 0
        completion["readyCandidate"] = (completion["semanticCoverageComplete"] and result["calibration"].get("passed") is True and
            completion["formalPublicPassed"] and len(proofs) == 3 and all(proof["publicPassed"] for proof in proofs))
    except Exception as error:
        completion["error"] = f"{type(error).__name__}: {error}"
    finally:
        cleanup = core.cleanup_artifacts(output)
        core.write(output / "binary-cleanup.json", cleanup)
        files = [core.file_record(path) for path in sorted(temporary.rglob("*")) if path.is_file()]
        core.write(output / "source-cleanup.json", {"allOwnedWorkflowFinished": True, "files": files,
            "fileCount": len(files), "bytes": sum(item["bytes"] for item in files), "source": str(temporary)})
        shutil.rmtree(temporary)
        completion["elapsedSeconds"] = time.monotonic() - started
        completion["protectedOriginalsUnchanged"] = all(core.file_record(Path(item["path"])) == item for item in protected)
        completion["temporarySourcesRemoved"] = not temporary.exists()
        completion["retainedNativeEvidence"] = [core.file_record(path) for path in sorted(output.rglob("*"))
            if path.is_file() and path.suffix in {".json", ".log", ".cjs"}]
        completion["readyCandidate"] = completion["readyCandidate"] and completion["protectedOriginalsUnchanged"] and completion["elapsedSeconds"] < 3600
        core.write(output / "completion.json", completion)
    print({key: completion.get(key) for key in ("readyCandidate", "semantic", "error", "elapsedSeconds")}, flush=True)
    return completion


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", default="127.0.0.1:5555")
    raise SystemExit(0 if replay(**vars(parser.parse_args()))["readyCandidate"] else 2)
