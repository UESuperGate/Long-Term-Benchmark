"""Lossless retention of original Task10 device artifacts before scratch deletion."""
import copy
import gzip
import hashlib
import json
from pathlib import Path

try:
    from . import tasks10_11_runtime_evidence as shared
except ImportError:
    import tasks10_11_runtime_evidence as shared

ROOT = Path(__file__).resolve().parents[2]


def require(value, message):
    if not value:
        raise ValueError("Task10 native artifact retention: " + message)


def read_native_artifact(pair):
    """Verify the retained container AND exact decompressed original bytes."""
    original = pair["original"]
    data = shared.read_record(pair["retained"])
    if pair.get("encoding") == "gzip":
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError) as error:
            raise ValueError("Task10 retained artifact is not lossless gzip") from error
    else:
        require(pair.get("encoding") == "identity", "unsupported retained encoding")
    require(len(data) == original["bytes"] and hashlib.sha256(data).hexdigest() == original["sha256"],
            "decompressed original byte length/hash mismatch")
    return data


def _original_bytes(item):
    path = Path(item["path"])
    data = (path if path.is_absolute() else ROOT / path).read_bytes()
    require(hashlib.sha256(data).hexdigest() == item["sha256"] and
            ("bytes" not in item or len(data) == item["bytes"]), "original artifact changed before retention")
    return data


def retain_pair(original, destination):
    data = _original_bytes(original)
    require(type(original.get("bytes")) is int, "original byte receipt is required")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / (original["sha256"] + ".gz")
    compressed = gzip.compress(data, mtime=0)
    if target.exists():
        require(target.read_bytes() == compressed, "refusing conflicting retained artifact")
    else:
        target.write_bytes(compressed)
    result = {"original": copy.deepcopy(original), "retained": shared.record(target), "encoding": "gzip"}
    require(read_native_artifact(result) == data, "lossless verification failed")
    return result


def retain_logs(artifacts, retained):
    return [retain_pair(shared.record(path), retained) for path in sorted(Path(artifacts).rglob("*.log"))]


def retain_repository_rows(report, artifacts, retained):
    destination = Path(retained) / "native-artifacts"
    logs = retain_logs(artifacts, destination)
    require(logs, "no original command logs available")
    for row in report["semantic"]["cases"]:
        execution_pair = retain_pair(row["execution"], destination)
        execution = json.loads(read_native_artifact(execution_pair))
        artifact = execution["rowArtifact"]
        native_record = {"path": artifact["local"], "bytes": artifact["bytes"], "sha256": artifact["sha256"]}
        row["nativeArtifacts"] = {
            "schemaVersion": 1, "backend": "native_ohosTest",
            "execution": execution_pair, "build": retain_pair(row["build"], destination),
            "nativeResult": retain_pair(native_record, destination), "commandLogs": copy.deepcopy(logs),
            "executionAttempts": [retain_pair(shared.record(path), destination) for path in
                sorted(Path(row["execution"]["path"]).parent.parent.glob("execution-*/device-execution.json"))]}
        verify_repository_row(row, report)
    report["provenance"]["nativeArtifactsRetention"] = {
        "schemaVersion": 1, "encoding": "gzip", "originalRowReferencesUnchanged": True,
        "originalNativeExecutionBuildBytesRetained": True,
        "retainedBlobFiles": len(list(destination.glob("*.gz")))}


def verify_repository_row(row, report):
    retained = row.get("nativeArtifacts")
    require(isinstance(retained, dict) and retained.get("backend") == "native_ohosTest",
            "original nativeArtifacts unavailable; snapshot-only history is incomplete")
    require(retained["execution"]["original"] == row["execution"] and
            retained["build"]["original"] == row["build"], "original row execution/build references changed")
    execution = json.loads(read_native_artifact(retained["execution"]))
    build = json.loads(read_native_artifact(retained["build"]))
    native = json.loads(read_native_artifact(retained["nativeResult"]))
    artifact = execution["rowArtifact"]
    require(retained["nativeResult"]["original"] == {
        "path": artifact["local"], "bytes": artifact["bytes"], "sha256": artifact["sha256"]},
        "native result does not bind the execution's original rowArtifact")
    require(execution.get("rows") == [native], "native result differs from complete original execution")
    require(execution.get("buildReport", {}).get("sha256") == row["build"]["sha256"] and
            execution["buildReport"]["path"] == row["build"]["path"] and
            build.get("source") == report["provenance"]["productionSourceRoot"] and
            build.get("task10SourceInventory", {}).get("sha256") == report["provenance"]["sourceInventory"]["sha256"],
            "original executed build/source differs from formal report")
    require(all(native.get(key) == row.get(key) for key in ("taskId", "role", "caseId", "traceDigest")),
            "actual native identity differs from formal row")
    if row.get("entryFailureEvidence"):
        require(native["status"] == "not_scored" and
                row["caseId"] == "mq_state_009_failure_cancel_retry" and
                row["entryFailureEvidence"]["nativeRow"]["sha256"] == artifact["sha256"],
                "prefix proof is not the same original native row")
    else:
        require(all(row.get(key) == native.get(key) for key in ("status", "observed", "invariantChecks")),
                "formal verdict/state/invariants differ from exact original native row")
    require(retained.get("commandLogs"), "original native command logs unavailable")
    for pair in retained["commandLogs"]:
        read_native_artifact(pair)
    for pair in retained.get("executionAttempts", []):
        read_native_artifact(pair)
    return native


def retain_device_ui_rows(report, artifacts, retained):
    """Legacy exact calibration is a host device observer, not an ohosTest row."""
    destination = Path(retained) / "native-artifacts"
    require(report.get("provenance", {}).get("deviceReport") and
            report["provenance"].get("buildReport"), "original host device/build report receipt missing")
    execution_pair = retain_pair(report["provenance"]["deviceReport"], destination)
    build_pair = retain_pair(report["provenance"]["buildReport"], destination)
    original = json.loads(read_native_artifact(execution_pair))
    logs = retain_logs(artifacts, destination)
    require(logs, "original host observer command logs missing")
    for row in report["semantic"]["cases"]:
        matches = [(index, raw) for index, raw in enumerate(original["semantic"]["cases"])
                   if raw["caseId"] == row["caseId"]]
        require(len(matches) == 1, "host observer case absent or ambiguous")
        index, raw = matches[0]
        layouts = [retain_pair(point["layout"], destination) for point in raw["checkpoints"]]
        row["nativeArtifacts"] = {"schemaVersion": 1, "backend": "host_device_ui_observer",
            "execution": copy.deepcopy(execution_pair), "build": copy.deepcopy(build_pair),
            "nativeResult": copy.deepcopy(execution_pair), "caseResultPath": ["semantic", "cases", index],
            "commandLogs": copy.deepcopy(logs), "layouts": layouts}
        verify_device_ui_row(row, report)
    report["provenance"]["nativeArtifactsRetention"] = {
        "schemaVersion": 1, "encoding": "gzip", "originalRowReferencesUnchanged": True,
        "originalObserverReportBytesRetained": True, "ohosTestResultClaimed": False,
        "retainedBlobFiles": len(list(destination.glob("*.gz")))}


def verify_device_ui_row(row, report):
    bundle = row.get("nativeArtifacts", {})
    require(bundle.get("backend") == "host_device_ui_observer", "original host observer artifacts unavailable")
    require(bundle["execution"]["original"] == report["provenance"]["deviceReport"] and
            bundle["build"]["original"] == report["provenance"]["buildReport"] and
            bundle["nativeResult"]["original"] == bundle["execution"]["original"],
            "original host observer references changed")
    execution_bytes = read_native_artifact(bundle["execution"])
    require(read_native_artifact(bundle["nativeResult"]) == execution_bytes,
            "original host observer result bytes differ")
    read_native_artifact(bundle["build"])
    original = json.loads(execution_bytes)
    location = bundle["caseResultPath"]
    require(location[:2] == ["semantic", "cases"] and len(location) == 3 and type(location[2]) is int and
            0 <= location[2] < len(original["semantic"]["cases"]),
            "original observer case locator invalid")
    raw = original["semantic"]["cases"][location[2]]
    require(raw["caseId"] == row["caseId"] and raw["traceDigest"] == row["traceDigest"],
            "original observer case identity differs")
    if not row.get("entryFailureEvidence"):
        checks = []
        for item in raw["invariantChecks"]:
            check = copy.deepcopy(item)
            if not check.get("description"):
                check["description"] = check.get("invariant", check.get("text"))
            checks.append(check)
        require(row["status"] == raw["status"] and row["observed"] == raw["observed"] and
                row["invariantChecks"] == checks, "formal host observer verdict/state/invariants differ")
    for pair in bundle["layouts"] + bundle["commandLogs"]:
        read_native_artifact(pair)
    return raw
