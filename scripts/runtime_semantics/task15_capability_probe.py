"""Authenticated unsupported-capability control on the candidate's original ArkUI page."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import argparse
import time
import shutil
from contextlib import ExitStack

import task14_15_formal_core as core
import task14_15_device_lease as lease

ROOT = core.ROOT
FIXTURES = Path(__file__).with_name("task15_capability")


def derive_builder(text, fixtures=FIXTURES):
    replacements = {
        "const root = path.resolve(__dirname, '../..');": "const root = " + json.dumps(str(ROOT)) + ";",
        "require('./arkts_native_smoke.cjs')": "require(" + json.dumps(str(ROOT / "scripts/runtime_semantics/arkts_native_smoke.cjs")) + ")",
        "require('./arkts_native_bundle.cjs')": "require(" + json.dumps(str(ROOT / "scripts/runtime_semantics/arkts_native_bundle.cjs")) + ")",
        "fixture === 'context_probe' ? ['DeviceContextProbe.test.ets']":
            "fixture === 'context_probe' ? ['Task15CapabilityProbe.test.ets', 'Task15CapabilityProbe.js', 'Task15CapabilityProbe.d.ts']",
        "const file = path.join(root, 'state_tests/runtime/arkts/native', name);":
            "const file = path.join(" + json.dumps(str(fixtures)) + ", name);",
        "'DeviceContextProbe.test'": "'Task15CapabilityProbe.test'",
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise RuntimeError("Task15 capability builder derivation changed: " + old[:60])
        text = text.replace(old, new)
    return text


def describe_entry(source, deadline):
    helper = ROOT / "state_tests/runtime/arkts/native/CandidateApiBindings.cjs"
    code = "const b=require(process.argv[1]);process.stdout.write(JSON.stringify(b.exportedClass(process.argv[2],'AccountDeactivationPresenter')));"
    process = subprocess.run(["/Applications/DevEco-Studio.app/Contents/tools/node/bin/node", "-e", code,
        str(helper), str(source)], capture_output=True, text=True, check=True,
        timeout=min(30, core.remaining_deadline(deadline, "capability source API binding")))
    api = json.loads(process.stdout)
    return {"entryId": "settings_deactivate_account" if {"refreshAvailability", "openForm"} <= set(api["methods"])
            else "deactivate_account_entry", "presenterSource": api["path"],
            "sourceSha256": core.sha256(source / api["path"]), "api": api}


def validate_observation(value, expected_entry_id="deactivate_account_entry"):
    if expected_entry_id not in {"deactivate_account_entry", "settings_deactivate_account"} or \
            value.get("entryQueryId", "deactivate_account_entry") != expected_entry_id:
        raise RuntimeError("Capability entry query is not source-bound")
    if value.get("status") not in {"pass", "fail"} or value.get("cleanup", {}).get("productionSessionRemoved") is not True:
        raise RuntimeError("Unsupported capability runtime did not establish and clean the given: " + str(value.get("error")))
    launches = value.get("startup", [])
    if len(launches) != 2:
        raise RuntimeError("Unsupported capability did not observe two original cold launches")
    for launch in launches:
        expected = {"bundleName": launch.get("bundleName"), "name": "EntryAbility", "moduleName": "entry"}
        if (not expected["bundleName"] or launch.get("monitorAdded") is not True or
                launch.get("monitorRemoved") is not True or launch.get("createdAbility") != expected or
                launch.get("foregroundAbility") != expected or not launch.get("observations") or
                launch["observations"][-1].get("identity") != expected):
            raise RuntimeError("Unsupported capability original AbilityMonitor/foreground evidence is incomplete")
    if launches[0].get("destroyedAbility") != launches[0]["createdAbility"]:
        raise RuntimeError("Original Ability destruction was not observed before the authenticated cold restart")
    points = {point["name"]: point["state"] for point in value["checkpoints"]}
    before = points["authenticated_unsupported_given"]
    samples = points["original_settings_after_capability_load"]["samples"]
    if (before.get("authMode") != "oidc" or before.get("phase") != "active" or
            before.get("userId") != "@unsupported:task15.test" or len(samples) != 5):
        raise RuntimeError("Unsupported capability given or isolated UI samples incomplete")
    for sample in samples:
        for name, control_id in (("session", "account_session_user"), ("signOut", "account_sign_out"),
                                 ("entry", expected_entry_id)):
            control = sample[name]
            query = control.get("query", {})
            if (query.get("transportCompleted") is not True or query.get("windowBundle") != launches[0]["bundleName"] or
                    query.get("id") != control_id or query.get("count") != (1 if control["present"] else 0)):
                raise RuntimeError("Capability missing-entry observation lacks a completed original-window query")
    calls = value.get("calls", [])
    if (len(calls) != 2 or calls[0] != {"method": "NativeAccountSessionStore.save/read", "production": True,
            "authMode": before["authMode"], "phase": before["phase"], "userId": before["userId"]} or
            calls[1] != {"method": "AccountClient.restore/canDeactivateAccount", "production": True,
            "restoredUserId": before["userId"], "capability": before.get("capability")}):
        raise RuntimeError("Authenticated capability production calls are missing or inconsistent")
    hidden = all(sample["session"].get("present") is True and sample["session"].get("visible") is True and
                 sample["session"].get("text") == before["userId"] and
                 sample["signOut"].get("present") is True and sample["signOut"].get("visible") is True and
                 sample["entry"].get("present") is False for sample in samples)
    passed = before.get("capability") is False and hidden
    if value.get("observed") != {"authenticatedUserId": before["userId"], "capability": before["capability"],
            "deactivateEntryVisible": not hidden, "originalPageRestored": True}:
        raise RuntimeError("Capability observations contradict the production given and actual UI")
    if value["status"] != ("pass" if passed else "fail"):
        raise RuntimeError("Capability verdict contradicts production readback")
    return passed


def compile_fixture(*, source: Path, output: Path, deadline: float, report: dict):
    core.require_build_space()
    original = ROOT / "scripts/runtime_semantics/arkts_native_device.cjs"
    snapshots = output / "fixture-snapshots"
    shutil.copytree(FIXTURES, snapshots)
    with tempfile.TemporaryDirectory(prefix="ltb-task15-capability-builder-") as raw:
        derived = Path(raw) / "builder.cjs"
        derived.write_text(derive_builder(original.read_text(), snapshots.resolve()))
        report["builder"] = {"originalSha256": core.sha256(original), "derivedSha256": core.sha256(derived)}
        command = ["/Applications/DevEco-Studio.app/Contents/tools/node/bin/node", str(derived),
                   "--source", str(source), "--task", "15_account_deactivation", "--fixture", "context_probe",
                   "--output-dir", str(output / "build")]
        report["commands"].append({"command": command})
        try:
            process = subprocess.run(command, capture_output=True, text=True, check=False,
                timeout=core.remaining_deadline(deadline, "Task15 capability fixture compilation"))
        except subprocess.TimeoutExpired as error:
            log = output / "build-command.log"
            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            log.write_text(decoded(error.stdout) + decoded(error.stderr))
            report["commands"][-1].update(timedOut=True,
                log={"path": str(log), "sha256": core.sha256(log), "bytes": log.stat().st_size})
            raise
        log = output / "build-command.log"
        log.write_text(process.stdout + process.stderr)
        report["commands"][-1].update(exitCode=process.returncode,
            log={"path": str(log), "sha256": core.sha256(log), "bytes": log.stat().st_size})
        build_path = output / "build/device-build-report.json"
        if build_path.exists():
            report["build"] = core.load(build_path)
        if process.returncode:
            raise RuntimeError("Task15 capability command failed: build-command")
    build = report["build"]
    if (build["runtimeCompile"]["passed"] is not True or build["productionUnchanged"] is not True or
            build["copiedProductionUnchanged"] is not True or build["temporaryProjectRemoved"] is not True):
        raise RuntimeError("Unsupported capability production build identity invalid")
    return build


def compile_only(*, source: Path, output: Path, deadline: float):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    started = time.monotonic()
    report = {"taskId": "15_account_deactivation", "source": str(source.resolve()),
              "candidateRootSha256": core.directory_digest(source), "commands": [],
              "scope": "same production app and capability ohosTest fixture packaging; no semantic scoring",
              "deviceLeaseAcquired": False, "nativeRuntimeExecuted": False,
              "timeoutSeconds": deadline - started, "status": "not_scored"}
    try:
        compile_fixture(source=source, output=output, deadline=deadline, report=report)
        report["status"] = "compiled_not_executed"
        return report
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["removedBinaries"] = core.remove_binary_artifacts(output)
        report["productionUnchanged"] = core.directory_digest(source) == report["candidateRootSha256"]
        report["elapsedSecondsOverall"] = time.monotonic() - started
        report["cleanup"] = {"binariesRetained": False,
            "temporaryProjectRemoved": report.get("build", {}).get("temporaryProjectRemoved")}
        core.write(output / "compile-fixture-report.json", report)


def evaluate(*, source: Path, output: Path, deadline: float, device_serial=None):
    core.require_build_space()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    report = {"source": str(source.resolve()), "candidateRootSha256": core.directory_digest(source),
              "taskId": "15_account_deactivation", "role": "agent", "commands": []}
    hdc = str(Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc")
    bundle = None
    owned = False

    def run(name, command, *, limit=None):
        process = subprocess.run(command, capture_output=True, text=True, check=False,
            timeout=min(limit or 3600, core.remaining_deadline(deadline, "Task15 capability " + name)))
        log = output / (name + ".log")
        log.write_text(process.stdout + process.stderr)
        report["commands"].append({"command": command, "exitCode": process.returncode,
            "log": {"path": str(log), "sha256": core.sha256(log), "bytes": log.stat().st_size}})
        if process.returncode:
            raise RuntimeError("Task15 capability command failed: " + name)
        return process.stdout + process.stderr

    with ExitStack() as stack:
        try:
            build = compile_fixture(source=source, output=output, deadline=deadline, report=report)
            report["entryBinding"] = describe_entry(source, deadline)
            scope = stack.enter_context(lease.task_scope("15_account_deactivation", deadline, device_serial))
            serial = scope["serial"]
            report["deviceLease"] = {**scope, "scope": "authenticated capability UI scenario after fixture compilation"}
            device = lambda name, args, **kwargs: run(name, [hdc, "-t", serial, *args], **kwargs)
            bundle = build["bundleName"]
            inventory = device("installed-before", ["shell", "bm", "dump", "-a"])
            if bundle in inventory:
                raise RuntimeError("Capability candidate is already installed")
            owned = True
            for index, hap in enumerate(build["haps"]):
                if core.sha256(Path(hap["path"])) != hap["sha256"]:
                    raise RuntimeError("Capability HAP changed")
                text = device("install-" + str(index), ["install", hap["path"]], limit=120)
                if "install bundle successfully" not in text:
                    raise RuntimeError("Capability HAP install rejected")
            device("force-stop", ["shell", "aa", "force-stop", bundle])
            device("wakeup", ["shell", "power-shell", "wakeup"])
            test = device("test", ["shell", "aa", "test", "-b", bundle, "-m", "entry_test",
                "-s", "unittest", "OpenHarmonyTestRunner", "-s", "task15EntryId", report["entryBinding"]["entryId"],
                "-s", "timeout", "120000", "-w", "150000"], limit=180)
            if "TestFinished-ResultCode: 0" not in test or "Failure: 0, Error: 0" not in test:
                raise RuntimeError("Capability Hypium transport incomplete")
            path = output / "observation.json"
            device("pull-result", ["file", "recv", "/data/app/el2/100/base/" + bundle +
                   "/cache/task15-capability-result.json", str(path)])
            value = core.load(path)
            if any(launch.get("bundleName") != bundle for launch in value.get("startup", [])):
                raise RuntimeError("Capability startup observed a different installed candidate")
            report["invariantPassed"] = validate_observation(value, report["entryBinding"]["entryId"])
            report["observation"] = {"path": str(path), "sha256": core.sha256(path), "bytes": path.stat().st_size}
            report["status"] = "pass" if report["invariantPassed"] else "fail"
            return report
        finally:
            try:
                if owned and bundle:
                    text = device("uninstall", ["uninstall", bundle], limit=120)
                    report["ownedAppUninstalled"] = "uninstall bundle successfully" in text
                    if not report["ownedAppUninstalled"]:
                        raise RuntimeError("Unsupported capability app cleanup was rejected")
            finally:
                report["removedBinaries"] = core.remove_binary_artifacts(output)
                report["productionUnchanged"] = core.directory_digest(source) == report["candidateRootSha256"]
                core.write(output / "report.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device-serial")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600:
        raise ValueError("Timeout must be 0 < timeout <= 3600")
    deadline = time.monotonic() + args.timeout
    if args.compile_only:
        print(json.dumps(compile_only(source=args.source, output=args.output, deadline=deadline)))
    else:
        print(json.dumps(evaluate(source=args.source, output=args.output, deadline=deadline,
                                  device_serial=args.device_serial)))
