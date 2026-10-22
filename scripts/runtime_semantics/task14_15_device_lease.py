"""Task-scoped canonical API23 leases with explicit borrowing by nested evaluators."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import hashlib
import os
from pathlib import Path
import time
import types
import tempfile
import uuid

import arkts_strict_agent_scorer as shared

CURRENT = ContextVar("task14_15_device_lease", default=None)
TOKEN_ENV = "LTB_TASK14_15_DEVICE_LEASE_TOKEN"
SERIAL_ENV = "LTB_TASK14_15_DEVICE_SERIAL"


def verify(lease, serial):
    if lease is None or lease["serial"] != serial:
        raise RuntimeError("Nested device execution does not match the task lease")
    owner = json.loads((Path(lease["path"]) / "owner.json").read_text())
    if owner != {key: lease[key] for key in ("taskId", "serial", "pid", "token")}:
        raise RuntimeError("Task device lease ownership changed")


@contextmanager
def task_scope(task_id, deadline, device_serial=None):
    serial = shared.discover_device(device_serial, deadline)
    existing = CURRENT.get()
    if existing is not None:
        verify(existing, serial)
        yield existing
        return
    started = time.monotonic()
    lock = shared.acquire_device(serial, deadline)
    lease = {"taskId": task_id, "serial": serial, "pid": os.getpid(), "token": uuid.uuid4().hex,
             "path": str(lock), "waitSeconds": round(time.monotonic() - started, 3)}
    owner = lock / "owner.json"
    previous = os.environ.get(TOKEN_ENV)
    previous_serial = os.environ.get(SERIAL_ENV)
    context_token = None
    try:
        owner.write_text(json.dumps({key: lease[key] for key in ("taskId", "serial", "pid", "token")}))
        context_token = CURRENT.set(lease)
        os.environ[TOKEN_ENV] = lease["token"]
        os.environ[SERIAL_ENV] = serial
        yield lease
    finally:
        if context_token is not None:
            CURRENT.reset(context_token)
        if previous is None:
            os.environ.pop(TOKEN_ENV, None)
        else:
            os.environ[TOKEN_ENV] = previous
        if previous_serial is None:
            os.environ.pop(SERIAL_ENV, None)
        else:
            os.environ[SERIAL_ENV] = previous_serial
        if owner.is_file() and json.loads(owner.read_text()).get("token") == lease["token"]:
            owner.unlink()
            lock.rmdir()


class BorrowedLock:
    def exists(self):
        return False


def derive_executor_source(original):
    content = original.read_text()
    changes = []
    imports = ("require('node:os')", "require('os')", 'require("node:os")', 'require("os")')
    if "os.homedir()" in content and not any(value in content for value in imports):
        content = content.replace("'use strict';", "'use strict';\nconst os = require('node:os');", 1)
        changes.append("Declare the node:os dependency used by hdc discovery")
    provider = "path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs')"
    if content.count(provider) != 1:
        raise RuntimeError("Device executor provider-path derivation changed")
    content = content.replace(provider, json.dumps(str(shared.ROOT /
        "state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs")))
    changes.append("Resolve the unchanged provider module from a temporary executor")
    return content, changes


def score_device(**kwargs):
    lease = CURRENT.get()

    def borrow(serial, deadline):
        shared.remaining(deadline, "Task14/15 inherited device lease")
        if lease is None:
            return shared.acquire_device(serial, deadline)
        verify(lease, serial)
        return BorrowedLock()

    original = shared.ROOT / "scripts/runtime_semantics/arkts_device_execute.cjs"
    content, changes = derive_executor_source(original)
    with tempfile.TemporaryDirectory(prefix="ltb-task14-15-device-executor-") as raw:
        derived = Path(raw) / "device-execute.cjs"
        derived.write_text(content)

        class ExecutorSubprocess:
            def run(self, command, **options):
                if len(command) >= 2 and command[1] == str(original):
                    command = [*command[:1], str(derived), *command[2:]]
                return shared.subprocess.run(command, **options)

            def __getattr__(self, name):
                return getattr(shared.subprocess, name)

        function = types.FunctionType(shared.score.__code__, {
            **shared.score.__globals__, "acquire_device": borrow, "subprocess": ExecutorSubprocess()},
            name=shared.score.__name__, argdefs=shared.score.__defaults__, closure=shared.score.__closure__)
        function.__kwdefaults__ = shared.score.__kwdefaults__
        report = function(**kwargs)
        report.setdefault("provenance", {})["deviceExecutorDerivation"] = {
            "original": {"path": str(original), "sha256": hashlib.sha256(original.read_bytes()).hexdigest()},
            "derivedSha256": hashlib.sha256(derived.read_bytes()).hexdigest(), "changes": changes,
            "sharedModuleModified": False}
    report.setdefault("diagnostics", {})["taskLocalDeviceExecutorRemoved"] = not Path(raw).exists()
    return report


def derive_js_lock_borrowing(script):
    acquisition = "fs.mkdirSync(lock);"
    release = "fs.rmdirSync(lock);"
    if script.count(acquisition) != 1 or script.count(release) != 1:
        raise RuntimeError("Task14/15 device runner lock derivation changed")
    borrowed = """if (process.env.LTB_TASK14_15_DEVICE_LEASE_TOKEN) {
          const inherited = JSON.parse(fs.readFileSync(path.join(lock, 'owner.json'), 'utf8'));
          if (inherited.token !== process.env.LTB_TASK14_15_DEVICE_LEASE_TOKEN || inherited.serial !== serial) {
            throw new Error('Task14/15 inherited device lease mismatch');
          }
        } else {
          fs.mkdirSync(lock);
        }"""
    script = script.replace(acquisition, borrowed).replace(
        release, "if (!process.env.LTB_TASK14_15_DEVICE_LEASE_TOKEN) fs.rmdirSync(lock);")
    script = script.replace("report.diagnostics.cleanup.deviceLockRemoved = true;",
                            "report.diagnostics.cleanup.deviceLockRemoved = !process.env.LTB_TASK14_15_DEVICE_LEASE_TOKEN; "
                            "report.diagnostics.cleanup.deviceLockBorrowed = Boolean(process.env.LTB_TASK14_15_DEVICE_LEASE_TOKEN);")
    if "const serial = targets[0];" in script:
        script = script.replace("if (targets.length !== 1)",
                                "if (!process.env.LTB_TASK14_15_DEVICE_SERIAL && targets.length !== 1)")
        script = script.replace("const serial = targets[0];", """const serial = process.env.LTB_TASK14_15_DEVICE_SERIAL || targets[0];
  if (!targets.includes(serial)) throw new Error('Requested Task14/15 device is not connected');""")
    startup = "run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);"
    if startup in script:
        if script.count(startup) != 1:
            raise RuntimeError("Task14/15 base startup derivation changed")
        script = script.replace(startup, """run(['shell', 'power-shell', 'wakeup']);
      const launch = run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);
      if (!String(launch.text ?? launch).includes('start ability successfully')) {
        throw new Error('Task14/15 environment: application launch was rejected: ' + String(launch.text ?? launch));
      }""")
    return script
