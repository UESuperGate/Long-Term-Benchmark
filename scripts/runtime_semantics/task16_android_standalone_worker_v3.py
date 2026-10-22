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
FIXTURE = ROOT / "state_tests/runtime/android/16_identity_reset/page_owner_sdk_v3"
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


def owned_popen(original, launches, output, deadline, *args, **kwargs):
    remaining(deadline)
    if kwargs.get("start_new_session") or kwargs.get("process_group") is not None or kwargs.get("preexec_fn") is not None or kwargs.get("shell"):
        raise ValueError("Descendant session/group/shell escape rejected before Popen")
    command = args[0] if args else kwargs.get("args")
    if not isinstance(command, (list, tuple)):
        raise ValueError("Descendant command must be explicit argv")
    process = original(*args, **kwargs)
    pgid = os.getpgid(process.pid)
    launches.append({"pid": process.pid, "pgid": pgid, "command": list(map(str, command)),
                     "workerPid": os.getpid(), "workerPgid": os.getpgrp(),
                     "startedAtEpochMs": int(time.time() * 1000)})
    supervisor.atomic(output, launches)
    if pgid != os.getpgrp():
        raise ValueError("Actual launched descendant escaped the owned group; retain evidence")
    return process


def retain_classes(classes, output, scope, deadline):
    remaining(deadline)
    classes = Path(classes).resolve()
    rows = [record(path) for path in sorted(classes.rglob("*.class"))]
    if not rows:
        return {"scope": scope, "classRoot": str(classes), "classFiles": [], "archive": None}
    if scope == "binary_free_predeclared":
        return {"scope": scope, "classRoot": str(classes), "classFiles": rows, "archive": None,
                "mainClassBytesReverified": False}
    if scope != "retained_tiny_classes" or sum(row["bytes"] for row in rows) > 32 * 1024 ** 2:
        raise ValueError("Class retention scope/32MiB limit exceeded; never silently change proof tier")
    with tarfile.open(output, "w:gz") as stream:
        for row in rows:
            remaining(deadline)
            path = Path(row["path"])
            if path.is_symlink():
                raise ValueError("Generated class symlink unsupported")
            data = path.read_bytes()
            if inputs.digest(data) != row["sha256"]:
                raise ValueError("Class bytes changed before archive")
            entry = tarfile.TarInfo(path.relative_to(classes).as_posix())
            entry.size = len(data)
            stream.addfile(entry, io.BytesIO(data))
    return {"scope": scope, "classRoot": str(classes), "classFiles": rows,
            "archive": record(output), "retention": "KEEP until main bytewise review and explicit cleanup authorization"}


def load_plan():
    spec = importlib.util.spec_from_file_location("task16_standalone_plan_v2", FIXTURE / "plan.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)
    return plan


def ensure_owned_worker(root, request, request_path, deadline):
    # Parent records the actual Popen immediately after spawn. Wait for that
    # atomic marker before locks/build; do not manufacture it in the child.
    marker = root / "worker-launch.json"
    while not marker.exists():
        time.sleep(min(0.01, remaining(deadline)))
    launch = json.loads(marker.read_text())
    if launch.get("pid") != os.getpid() or launch.get("pgid") != os.getpgrp() or os.getpid() != os.getpgrp():
        raise ValueError("Worker is not the actual supervisor-owned session leader")
    if request.get("supervisorPid") != os.getppid() or launch.get("request") != record(request_path):
        raise ValueError("Actual supervisor/request ownership differs")
    command = launch.get("command", [])
    if "--worker" not in command or str(request_path) not in command or "--expected-request-sha256" not in command or record(request_path)["sha256"] not in command:
        raise ValueError("Actual owned worker launch is not source/request-bound")


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
    if not request.get("implementation") or any(record(item["path"]) != item for item in request["implementation"]):
        raise ValueError("Reviewed implementation bytes changed before lock/build")
    scope = request.get("binaryProofScope")
    if scope not in {"retained_tiny_classes", "binary_free_predeclared"}:
        raise ValueError("Binary proof scope must be declared BEFORE runtime")
    source = Path(request["source"]).resolve(strict=True)
    if source == root or source in root.parents or root in source.parents:
        raise ValueError("Candidate and retained audit root must be disjoint")
    ensure_owned_worker(root, request, request_path, deadline)
    result = {"formalStatus": "not_scored", "standaloneApplicationCompile": "not_run", "stage": "lock_wait"}
    supervisor.atomic(root / "android-worker-started.json", {"pid": os.getpid(), "pgid": os.getpgrp(),
        "request": record(request_path), "binaryProofScope": scope,
        "deadlineEpochMs": request["deadlineEpochMs"], "startedBeforeLockWait": True})
    # Cover preparation too: plan.catalog on Python3.9 uses check_output/run.
    # The inner compiler recorder delegates to these SAME bounded functions.
    unobserved_run, unobserved_popen = subprocess.run, subprocess.Popen
    launches = []
    def preparation_popen(*args, **kwargs):
        if request["supervisorPid"] != os.getppid():
            raise ValueError("Owned supervisor disappeared: no further process launched")
        return owned_popen(unobserved_popen, launches, root / "actual-process-launches.json", deadline, *args, **kwargs)
    def bounded_run(*args, **kwargs):
        kwargs["timeout"] = min(kwargs.get("timeout") or 3600, remaining(deadline))
        return unobserved_run(*args, **kwargs)
    subprocess.run, subprocess.Popen = bounded_run, preparation_popen
    try:
        with android_locks(deadline):
            supervisor.atomic(root / "android-locks-acquired.json", {"pid": os.getpid(), "paths": list(map(str, LOCKS)),
                "acquiredAtEpochMs": int(time.time() * 1000), "deadlineEpochMs": request["deadlineEpochMs"], "lockOwner": "child_only"})
            require_floor(root)
            remaining(deadline)
            result["stage"] = "capture_complete_standalone"
            plan = load_plan().generate(source, root / "input-plan")
            captured = plan["standaloneInput"]
            result["inputPlan"] = record(root / "input-plan/plan.json")
            result["beforeRuntimeTreeSha256"] = inputs.assert_unchanged(source, captured)
            with tempfile.TemporaryDirectory(prefix="ltb16-standalone-owned-", dir=root / "owned-work") as temporary:
                retained_source = inputs.materialize(captured, Path(temporary) / "candidate")
                result["stage"] = "runtime_slice"
                configuration = root / "input-plan/configuration.json"
                for name in ("IdentityPageOwnerTest.kt", "MainThreadClockDispatcher.kt"):
                    shutil.copyfile(FIXTURE / name, configuration.parent / name)
                require_floor(root)
                from . import android_robolectric as robo
                from .android_robolectric_ui_resources import compile_resources
                original_run, original_popen, original_resources = subprocess.run, subprocess.Popen, robo.compile_resources
                compilations, java_compilations = [], []

                def popen(*args, **kwargs):
                    # Already guarded/recorded by preparation_popen: do not
                    # double-record one actual launch or fork a new deadline.
                    return original_popen(*args, **kwargs)

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
                                                  "binaryLedgerBeforeCleanup": inputs.binary_ledger(payloads) if payloads else None,
                                                  "classRetention": retain_classes(classes, root / ("javac-classes-%02d.tar.gz" % len(java_compilations)), scope, deadline)})
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
                                             "binaryLedgerBeforeCleanup": inputs.binary_ledger(binaries) if binaries else None,
                                             "classRetention": retain_classes(classes, root / "kotlin-classes.tar.gz", scope, deadline)})
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
        subprocess.run, subprocess.Popen = unobserved_run, unobserved_popen
        result["deadlineEpochMs"] = request["deadlineEpochMs"]
        result["endedAtEpochMs"] = int(time.time() * 1000)
        result["worker"] = record(__file__)
        result["binaryProofScope"] = scope
        result["androidLocksClosedByWorker"] = True
        supervisor.atomic(root / "standalone-diagnostic.json", result)
    return result
