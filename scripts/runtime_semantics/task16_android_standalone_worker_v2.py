"""Staged worker API; no launcher and no work on import.

A reviewed supervisor must supply a NEW coordinated root and ONE overall child
budget after resource release. This module does not grant that release or start
a fresh3600 timer. Its own Android locks must NOT also be held by its caller.
All returned rows remain diagnostic/unscored until a full independent verifier
and admission policy are reviewed. Offline tests are not runtime receipts.
"""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

from . import task16_android_standalone_inputs_v2 as inputs
from . import tasks16_17_native_controller_v3 as supervisor

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "state_tests/runtime/android/16_identity_reset/page_owner_sdk_v2"
LOCKS = [Path("/tmp/long-term-benchmark-android-full-build.lock"), ROOT / "state_tests/runtime/android/.build.lock"]


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": inputs.digest(data)}


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("Shared overall child deadline exhausted; no per-stage reset")
    return value


def request_budget(request):
    start, end = request["startedAtEpochMs"], request["deadlineEpochMs"]
    if type(start) not in (int, float) or type(end) not in (int, float) or start > time.time() * 1000 + 1000:
        raise ValueError("Invalid actual overall start/deadline")
    if not 0 < end - start <= 3600000:
        raise ValueError("New coordinated overall budget must be <=3600s")
    if request.get("originalRepairBudgetReused") is not False:
        raise ValueError("Old repair budget cannot be reused/reset")
    # This statement records coordination, NOT human authorization or readiness.
    if request.get("resourceSchedule") != "new_root_after_coordinator_release":
        raise ValueError("Explicit coordinator resource release/root required")
    deadline = supervisor.timer.child_local_deadline(request["childBudget"])
    deadline = min(deadline, time.monotonic() + end / 1000 - time.time())
    remaining(deadline)
    return deadline


@contextlib.contextmanager
def android_locks(deadline):
    handles = []
    try:
        for path in LOCKS:
            handle = path.open("a")
            handles.append(handle)
            while True:
                remaining(deadline)
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(min(0.1, remaining(deadline)))
        yield
    finally:
        # Closing only this worker's FDs cannot release someone else's lock.
        for handle in reversed(handles):
            handle.close()


def require_floor(root):
    if shutil.disk_usage(root).free < 8 * 1024 ** 3:
        raise OSError("8GiB floor: no build or dependency preparation started")


def load_plan():
    spec = importlib.util.spec_from_file_location("task16_standalone_plan_v2", FIXTURE / "plan.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)
    return plan


def execute_prepared(request_path, *, expected_request_sha256):
    """Only a reviewed owned supervisor may call this after a new slot release."""
    request_path = Path(request_path).resolve(strict=True)
    if record(request_path)["sha256"] != expected_request_sha256:
        raise ValueError("Caller-pinned request hash mismatch")
    request = json.loads(request_path.read_text())
    root = request_path.parent
    deadline = request_budget(request)
    if request["worker"] != record(__file__):
        raise ValueError("Reviewed worker bytes changed")
    if request["fixtureSources"] != [record(path) for path in sorted(FIXTURE.iterdir()) if path.is_file()]:
        raise ValueError("Reviewed fixture bytes changed")
    source = Path(request["source"]).resolve(strict=True)
    if source == root or source in root.parents or root in source.parents:
        raise ValueError("Candidate and retained audit root must be disjoint")
    result = {"formalStatus": "not_scored", "standaloneApplicationCompile": "not_run", "stage": "lock_wait"}
    try:
        with android_locks(deadline):
            require_floor(root)
            remaining(deadline)
            result["stage"] = "capture_complete_standalone"
            plan = load_plan().generate(source, root / "input-plan")
            captured = plan["standaloneInput"]
            result["inputPlan"] = record(root / "input-plan/plan.json")
            result["beforeRuntimeTreeSha256"] = inputs.assert_unchanged(source, captured)
            with tempfile.TemporaryDirectory(prefix="ltb16-standalone-owned-", dir=root) as temporary:
                retained_source = inputs.materialize(captured, Path(temporary) / "candidate")
                result["stage"] = "runtime_slice"
                configuration = root / "input-plan/configuration.json"
                for name in ("IdentityPageOwnerTest.kt", "MainThreadClockDispatcher.kt"):
                    shutil.copyfile(FIXTURE / name, configuration.parent / name)
                require_floor(root)
                from . import android_robolectric as robo
                from .android_robolectric_ui_resources import compile_resources
                original_run, original_popen, original_resources = subprocess.run, subprocess.Popen, robo.compile_resources
                launches, compilations, java_compilations = [], [], []

                def popen(*args, **kwargs):
                    if kwargs.get("start_new_session") or kwargs.get("process_group") is not None:
                        raise ValueError("Build descendants must stay in supervisor-owned process group")
                    process = original_popen(*args, **kwargs)
                    launches.append({"pid": process.pid, "pgid": os.getpgid(process.pid),
                                     "command": args[0] if args else kwargs.get("args")})
                    supervisor.atomic(root / "actual-process-launches.json", launches)
                    return process

                def run(*args, **kwargs):
                    raw_argv = args[0] if args else kwargs["args"]
                    if not isinstance(raw_argv, (list, tuple)) or kwargs.get("shell"):
                        raise ValueError("Only fixed argv commands are supported by the staged worker")
                    argv = list(map(str, raw_argv))
                    kwargs["timeout"] = min(kwargs.get("timeout") or 3600, remaining(deadline))
                    process = original_run(*args, **kwargs)
                    if Path(argv[0]).name == "javac":
                        generated = [Path(value) for value in argv if value.endswith(".java")]
                        archive = root / ("actual-java-inputs-%02d.tar.gz" % len(java_compilations))
                        with tarfile.open(archive, "w:gz") as stream:
                            for index, path in enumerate(generated):
                                data = path.read_bytes()
                                entry = tarfile.TarInfo(str(index) + "_" + path.name)
                                entry.size = len(data)
                                stream.addfile(entry, io.BytesIO(data))
                        classes = Path(argv[argv.index("-d") + 1])
                        payloads = sorted(classes.rglob("*.class"))
                        java_compilations.append({"command": argv, "exitCode": process.returncode,
                                                  "actualJavaInputs": [record(path) for path in generated],
                                                  "inputArchive": record(archive), "compiler": record(argv[0]),
                                                  "binaryLedgerBeforeCleanup": inputs.binary_ledger(payloads) if payloads else None})
                        supervisor.atomic(root / "actual-java-compilation.json", java_compilations)
                    if "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler" in argv:
                        classes = Path(argv[argv.index("-d") + 1])
                        kotlin = [record(value) for value in argv if str(value).endswith(".kt")]
                        jars = set()
                        for flag in ("-cp", "-classpath"):
                            for index, value in enumerate(argv[:-1]):
                                if value == flag:
                                    jars.update(Path(path) for path in str(argv[index + 1]).split(os.pathsep)
                                                if Path(path).is_file())
                        for value in argv:
                            if str(value).startswith("-Xplugin="):
                                jars.add(Path(str(value).split("=", 1)[1]))
                        resources = [path.parent / "resources.apk" for path in jars if path.name == "resources.jar"]
                        binaries = list(classes.rglob("*.class")) + sorted(jars) + [path for path in resources if path.is_file()]
                        compilations.append({"command": argv, "exitCode": process.returncode,
                                             "jvmExecutable": record(argv[0]),
                                             "actualKotlinInputs": kotlin,
                                             "binaryLedgerBeforeCleanup": inputs.binary_ledger(binaries) if binaries else None})
                        supervisor.atomic(root / "actual-kotlin-compilation.json", compilations)
                    return process

                subprocess.run, subprocess.Popen, robo.compile_resources = run, popen, compile_resources
                try:
                    # Constant loader label for EVERY candidate; actual standalone
                    # files select behavior. No role/ref/path polarity inference.
                    raw = robo.run_slice("16_identity_reset", "agent", retained_source, FIXTURE.parent,
                                         configuration, root / "slice.json", remaining(deadline))
                    result["diagnosticSliceStatus"] = raw["status"]
                finally:
                    subprocess.run, subprocess.Popen, robo.compile_resources = original_run, original_popen, original_resources
                    result["afterRuntimeTreeSha256"] = inputs.assert_unchanged(source, captured)
                    result["retainedRuntimeInputTreeSha256"] = inputs.assert_unchanged(retained_source, dict(captured, excluded=[]))
                    remaining(deadline)
            result["temporaryMaterializationRemoved"] = not Path(temporary).exists()
            result["stage"] = "diagnostic_complete_no_formal_admission"
    except Exception as failure:
        result.update(stage="unavailable", error=type(failure).__name__ + ": " + str(failure))
        raise
    finally:
        result["deadlineEpochMs"] = request["deadlineEpochMs"]
        result["endedAtEpochMs"] = int(time.time() * 1000)
        result["worker"] = record(__file__)
        supervisor.atomic(root / "standalone-diagnostic.json", result)
    return result
