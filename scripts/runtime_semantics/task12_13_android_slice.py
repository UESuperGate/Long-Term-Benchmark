"""Run the unchanged exact Android slice with one deadline and hash-only cleanup."""

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
try:
    from . import android_robolectric as exact
    from . import android_robolectric_dependencies as dependencies
    from . import android_robolectric_ui_resources as resources
    from . import task12_13_formal_core as core
    from . import task12_13_runtime_support as support
except ImportError:
    import android_robolectric as exact
    import android_robolectric_dependencies as dependencies
    import android_robolectric_ui_resources as resources
    import task12_13_formal_core as core
    import task12_13_runtime_support as support


class Proxy:
    def __init__(self, original, **overrides):
        self.original = original
        self.overrides = overrides

    def __getattr__(self, name):
        return self.overrides.get(name, getattr(self.original, name))


@contextmanager
def replace_attribute(module, name, value):
    original = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, original)


def run_slice(task_id, role, source, adapter, configuration, output, deadline):
    audit = {"schemaVersion": 1, "deadlineMonotonic": deadline,
             "commands": [], "temporaryDirectories": [], "productionLogicReplaced": False}
    audit_path = output.with_suffix(".temporary-cleanup.json")

    def bounded_run(command, *args, timeout=None, capture_output=False, check=False, input=None, **kwargs):
        budget = support.remaining(deadline, "Android exact slice subprocess")
        if timeout is not None:
            budget = min(budget, timeout)
        if capture_output:
            kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if input is not None:
            kwargs["stdin"] = subprocess.PIPE
        kwargs["start_new_session"] = True
        process = subprocess.Popen(command, *args, **kwargs)
        timed_out = False
        try:
            stdout, stderr = process.communicate(input=input, timeout=budget)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        log = output.with_name(output.stem + f".subprocess-{len(audit['commands']) + 1:04d}.log")
        data = b"".join(value.encode() if isinstance(value, str) else value or b"" for value in (stdout, stderr))
        log.write_bytes(data)
        audit["commands"].append({"command": list(map(str, command)), "timeoutSeconds": budget,
                                  "exitCode": process.returncode, "timedOut": timed_out,
                                  "log": core.file_record(log)})
        core.write(audit_path, audit)
        if timed_out:
            raise subprocess.TimeoutExpired(command, budget, output=stdout, stderr=stderr)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result

    @contextmanager
    def temporary_directory(*args, **kwargs):
        directory = Path(tempfile.mkdtemp(*args, **kwargs)).resolve()
        record = {"path": str(directory), "removed": False, "hashesRecordedBeforeRemoval": False}
        audit["temporaryDirectories"].append(record)
        try:
            yield str(directory)
        finally:
            record["files"] = [core.file_record(path) for path in sorted(directory.rglob("*")) if path.is_file()]
            record["hashesRecordedBeforeRemoval"] = True
            retained = []
            for item in record["files"]:
                path = Path(item["path"])
                if path.suffix.lower() in {".json", ".log"}:
                    target = output.parent / (output.stem + ".retained-audit") / path.relative_to(directory)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    retained.append(core.file_record(target))
            record["retainedAuditFiles"] = retained
            core.write(audit_path, audit)
            shutil.rmtree(directory)
            record["removed"] = not directory.exists()
            core.write(audit_path, audit)

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ExitStack() as stack:
            stack.enter_context(replace_attribute(exact, "tempfile", Proxy(tempfile, TemporaryDirectory=temporary_directory)))
            for module in (exact, dependencies, resources):
                stack.enter_context(replace_attribute(module, "subprocess", Proxy(subprocess, run=bounded_run)))
            return exact.run_slice(task_id, role, source, adapter, configuration, output,
                                   support.remaining(deadline, "Android exact slice"))
    finally:
        audit["complete"] = all(item["removed"] and item["hashesRecordedBeforeRemoval"]
                                for item in audit["temporaryDirectories"])
        core.write(audit_path, audit)
        if not audit["complete"]:
            raise RuntimeError("Android exact slice temporary cleanup is incomplete")
