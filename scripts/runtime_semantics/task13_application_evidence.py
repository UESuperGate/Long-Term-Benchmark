"""Task13 application compile reuse bound to an audited source inventory.

Only application compilation may be reused. Every semantic phase is executed
again by the formal scorer under its own single deadline.
"""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path

try:
    from . import task12_13_formal_core as core
except ImportError:
    import task12_13_formal_core as core


TASK_ID = "13_user_verification"
FINAL_COMMIT = "bee248e2d59149d0deab4da4b8265199cb722ffe"


def verify_record(record: dict) -> Path:
    path = Path(record["path"])
    if core.file_record(path) != record:
        raise ValueError("Task13 application evidence hash mismatch")
    return path


def verify_compile_report(path: Path) -> dict:
    report = core.load(path)
    compile_result = report.get("compile", {})
    if (report.get("taskId") != TASK_ID or report.get("platform") != "android" or
            compile_result.get("passed") is not True or
            compile_result.get("status") != "passed" or compile_result.get("exitCode") != 0):
        raise ValueError("Task13 prior application compilation did not pass")
    verify_record(compile_result["log"])
    verify_record(compile_result["repositoryConfiguration"])
    cleanups = [item for item in report["diagnostics"]["cleanup"]
                if item["role"] == "application_compile"]
    if len(cleanups) != 1:
        raise ValueError("Task13 application cleanup evidence is missing")
    cleanup = cleanups[0]
    if (cleanup.get("binaryHashesRecordedBeforeRemoval") is not True or
            cleanup.get("binariesRetained") is not False or
            cleanup.get("temporaryBuildRemoved") is not True):
        raise ValueError("Task13 application binaries were not audited and removed")
    artifacts = compile_result.get("artifacts", [])
    recorded = [{key: item[key] for key in ("path", "bytes", "sha256")}
                for item in cleanup.get("binaryHashes", [])]
    if not artifacts or artifacts != recorded:
        raise ValueError("Task13 compiled APK hashes differ from cleanup hashes")
    return report


def bind_verified_final_copy(*, source: Path, prior_report: Path, output: Path) -> dict:
    """Persist the session-authorized immutable final-copy compile binding."""
    source = source.resolve()
    report = verify_compile_report(prior_report)
    if Path(report["compile"]["source"]).resolve() != source:
        raise ValueError("Task13 compiled source path differs")
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"], text=True)
    if commit != FINAL_COMMIT or dirty:
        raise ValueError("Task13 compile reuse requires the verified clean immutable final copy")
    receipt = {
        "schemaVersion": 1, "taskId": TASK_ID, "platform": "android",
        "scope": "application_compile_only", "runtimeEvidenceReused": False,
        "bindingAudit": "Session-verified unchanged final-copy commit; inventory captured on recovery",
        "commit": commit, "priorReport": core.file_record(prior_report),
        "sourceInventory": core.source_inventory(source),
    }
    core.write(output, receipt)
    return receipt


def reuse_compiler(receipt_path: Path):
    def compile_application(*, platform, source, output, deadline, command):
        del command
        if core.time.monotonic() >= deadline:
            raise TimeoutError("Task13 application evidence validation exhausted the shared deadline")
        receipt = core.load(receipt_path)
        if (platform != "android" or receipt.get("taskId") != TASK_ID or
                receipt.get("scope") != "application_compile_only" or
                receipt.get("runtimeEvidenceReused") is not False or
                receipt.get("commit") != FINAL_COMMIT):
            raise ValueError("Task13 application compile receipt identity mismatch")
        prior_path = verify_record(receipt["priorReport"])
        prior = verify_compile_report(prior_path)
        inventory = core.source_inventory(source)
        if inventory != receipt["sourceInventory"]:
            raise ValueError("Task13 application compile source inventory differs")
        if Path(prior["compile"]["source"]).resolve() != source.resolve():
            raise ValueError("Task13 application compile source binding differs")
        result = copy.deepcopy(prior["compile"])
        result.update(reused=True, evidenceScope="application_compile_only",
                      reuseReceipt=core.file_record(receipt_path),
                      sourceInventorySha256=inventory["sha256"],
                      runtimeEvidenceReused=False)
        output.mkdir(parents=True, exist_ok=False)
        core.write(output / "application-compile-reuse.json", result)
        return result

    return compile_application
