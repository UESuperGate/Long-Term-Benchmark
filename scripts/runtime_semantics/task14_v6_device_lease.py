"""Task14 V6 device lease with nonce-bound external Matrix provider arguments."""
from __future__ import annotations

import hashlib
from pathlib import Path
import types

from . import task14_15_device_lease as prior


CONFIG_ENV = "TASK14_NATIVE_E2E_CONFIG"


def derive_executor_source(original: Path):
    content, changes = prior.derive_executor_source(original)
    nonce_line = "if (build.supportsExecutionNonce) report.executionNonce = crypto.randomBytes(16).toString('hex');"
    if content.count(nonce_line) != 1:
        raise RuntimeError("Task14 execution-nonce derivation changed")
    content = content.replace(nonce_line, """const task14NativeE2E = process.env.TASK14_NATIVE_E2E_CONFIG ?
    JSON.parse(process.env.TASK14_NATIVE_E2E_CONFIG) : undefined;
  if (task14NativeE2E) {
    if (!build.supportsExecutionNonce || !/^[a-f0-9]{32}$/.test(task14NativeE2E.nonce || '') ||
        !/^127\\.0\\.0\\.1:[1-9][0-9]{0,4}$/.test(task14NativeE2E.homeserver || '') ||
        !/^[a-f0-9]{64}$/.test(task14NativeE2E.caSha256 || '')) {
      throw new Error('Invalid Task14 native E2E executor configuration');
    }
    report.executionNonce = task14NativeE2E.nonce;
    report.task14ExternalProvider = { homeserver: task14NativeE2E.homeserver,
      caSha256: task14NativeE2E.caSha256, nonceSha256: crypto.createHash('sha256')
        .update(task14NativeE2E.nonce).digest('hex') };
  } else if (build.supportsExecutionNonce) report.executionNonce = crypto.randomBytes(16).toString('hex');""")
    argument_line = "if (report.executionNonce) command.push('-s', 'ltbExecutionNonce', report.executionNonce);"
    if content.count(argument_line) != 1:
        raise RuntimeError("Task14 Ability argument derivation changed")
    content = content.replace(argument_line, argument_line + """
    if (task14NativeE2E) command.push('-s', 'task14E2E', '1', '-s', 'task14Nonce',
      task14NativeE2E.nonce, '-s', 'task14Homeserver', task14NativeE2E.homeserver,
      '-s', 'task14CaSha256', task14NativeE2E.caSha256);""")
    timeout_line = "const transcript = run('aa-test', command, 150000);"
    if content.count(timeout_line) != 1:
        raise RuntimeError("Task14 aa-test timeout derivation changed")
    content = content.replace(timeout_line, "const transcript = run('aa-test', command, 240000);")
    changes.extend([
        "Bind execution nonce to the external Task14 HTTPS provider",
        "Pass validated provider homeserver and CA digest as Ability arguments",
        "Allow four minutes for certificate UI, login, transition, and certificate cleanup",
    ])
    return content, changes


def score_device(**kwargs):
    original = prior.shared.ROOT / "scripts/runtime_semantics/arkts_device_execute.cjs"
    content, changes = derive_executor_source(original)

    def derived_source(_original):
        return content, changes

    function = types.FunctionType(prior.score_device.__code__, {
        **prior.score_device.__globals__, "derive_executor_source": derived_source},
        name=prior.score_device.__name__, argdefs=prior.score_device.__defaults__,
        closure=prior.score_device.__closure__)
    function.__kwdefaults__ = prior.score_device.__kwdefaults__
    report = function(**kwargs)
    report.setdefault("provenance", {})["task14V6Executor"] = {
        "environment": CONFIG_ENV,
        "original": {"path": str(original), "sha256": hashlib.sha256(original.read_bytes()).hexdigest()},
        "derivedSha256": hashlib.sha256(content.encode()).hexdigest(),
        "changes": changes,
        "sharedModuleModified": False,
    }
    return report


task_scope = prior.task_scope
