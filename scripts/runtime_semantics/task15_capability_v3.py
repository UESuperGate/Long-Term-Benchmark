"""Versioned capability execution: unchanged real probe, reserved cleanup budget."""
from pathlib import Path
import subprocess
import time
from contextlib import ExitStack
from . import task14_15_formal_core as core
from . import task14_15_device_lease as lease
from .task15_capability_probe import compile_fixture, describe_entry, validate_observation


def evaluate(*, source: Path, output: Path, deadline: float, device_serial=None):
    work_deadline = deadline - 120
    core.remaining_deadline(work_deadline, 'capability scenario reserves cleanup in original budget')
    core.require_build_space()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    report = {"source": str(source.resolve()), "candidateRootSha256": core.directory_digest(source),
              "taskId": "15_account_deactivation", "role": "agent", "commands": []}
    report['runtimeImplementation'] = {'path': str(Path(__file__)), 'sha256': core.sha256(Path(__file__))}
    report['freshProtocol'] = 'task15.arkts.full-ten-case.v3'
    hdc = str(Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc")
    bundle = None
    owned = False

    def run(name, command, *, limit=None):
        process = subprocess.run(command, capture_output=True, text=True, check=False,
            timeout=min(limit or 3600, core.remaining_deadline(deadline if name == 'uninstall' else work_deadline,
                "Task15 capability " + name)))
        log = output / (name + ".log")
        log.write_text(process.stdout + process.stderr)
        report["commands"].append({"command": command, "exitCode": process.returncode,
            "log": {"path": str(log), "sha256": core.sha256(log), "bytes": log.stat().st_size}})
        if process.returncode:
            raise RuntimeError("Task15 capability command failed: " + name)
        return process.stdout + process.stderr

    with ExitStack() as stack:
        try:
            build = compile_fixture(source=source, output=output, deadline=work_deadline, report=report)
            report["entryBinding"] = describe_entry(source, work_deadline)
            scope = stack.enter_context(lease.task_scope("15_account_deactivation", work_deadline, device_serial))
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
