"""Additional Task10-only eligibility conjunct; never a source-based semantic scorer."""
import copy
import hashlib
import json
from pathlib import Path

try:
    from . import tasks10_11_runtime_evidence as shared
    from .task10_native_artifacts import read_native_artifact, verify_device_ui_row
except ImportError:
    import tasks10_11_runtime_evidence as shared
    from task10_native_artifacts import read_native_artifact, verify_device_ui_row

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "state_tests/runtime/arkts/native/task10_base_closure/reviewed_closure.json"
FIXTURE_SHA256 = "9aa41b120668bc9b6cfee08c185af24fe99645d6ff7739b52e8ba52d78c46190"
GUARD = "task10.arkts.reviewed-common-closure.v1"
COMMON_POLICY = "tasks10_11.android.common-prefix.v1"
VOLATILE = {"bounds", "origBounds", "hierarchy", "hostWindowId", "focused",
            "windowId", "key", "zIndex", "debugLine", "hashcode", "index"}


def require(value, message):
    if not value:
        raise ValueError("Task10 ArkTS closure eligibility (NS, not semantic fail): " + message)


def load_fixture():
    data = FIXTURE.read_bytes()
    require(hashlib.sha256(data).hexdigest() == FIXTURE_SHA256, "reviewed fixture hash changed")
    value = json.loads(data)
    require(value["guardId"] == GUARD and value["taskId"] == "10_media_upload_quality", "wrong fixture identity")
    return value


def project_tree(node):
    require(isinstance(node, dict) and set(node) <= {"attributes", "children"} and
            isinstance(node.get("attributes"), dict) and isinstance(node.get("children", []), list),
            "incomplete or unknown native UI tree")
    return {"attributes": {key: value for key, value in sorted(node["attributes"].items()) if key not in VOLATILE},
            "children": [project_tree(child) for child in node.get("children", [])]}


def _attributes(node):
    yield node["attributes"]
    for child in node["children"]:
        yield from _attributes(child)


def check_ui(layout, fixture, *, caption="", done=False):
    expected = copy.deepcopy(fixture["initialUiProjection"])
    for node in _attributes(expected):
        if node.get("id") == "attachment_caption":
            node["text"] = node["originalText"] = caption
        if node.get("text") == "Send state: idle" and done:
            node["text"] = node["originalText"] = "Send state: done"
    require(project_tree(layout) == expected,
            "unknown/extra/renamed/hidden controls or incomplete full UI; private ID absence is not eligibility")


def validate_entry_failure(row, report, usedids=None, *, contract):
    """Call AFTER ordinary entry validation, as an extra public dispatcher conjunct."""
    if (report.get("taskId"), report.get("platform")) != ("10_media_upload_quality", "arkts") or \
            row.get("entryFailureEvidence", {}).get("policyId") != COMMON_POLICY:
        return {"applies": False}
    fixture = load_fixture()
    require(report.get("role") in {"base", "final", "agent"} and row.get("role") == report["role"], "entry role changed")
    spec = next((item for item in contract["cases"] if item["caseId"] == row.get("caseId")), None)
    require(contract.get("taskId") == report["taskId"] and spec and spec["traceDigest"] == row["traceDigest"],
            "canonical case binding changed")
    require(json.loads(shared.read_record(report["provenance"]["contract"])) == contract, "canonical contract changed")
    inventory = report["provenance"]["sourceInventory"]
    require(all(inventory.get(key) == fixture["fullInputInventory"][key] for key in ("files", "sha256")),
            "production input closure was not reviewed; commonPreview is insufficient")
    raw = verify_device_ui_row(row, report)
    bundle = row["nativeArtifacts"]
    original = json.loads(read_native_artifact(bundle["execution"]))
    build = json.loads(read_native_artifact(bundle["build"]))
    require(build.get("production") == fixture["compiledProduction"] and
            build.get("bundleName") == fixture["bundleName"] and
            build.get("source") == report["provenance"]["productionSourceRoot"] and
            build.get("productionUnchanged") is True and build.get("copiedProductionUnchanged") is True,
            "actual compiled production closure differs from reviewed closure")
    observed = raw["observed"]
    require(original.get("status") == "passed" and original.get("role") == report["role"] and
            original.get("taskId") == report["taskId"] and
            original.get("diagnostics", {}).get("cleanup", {}).get("ownedAppUninstalled") is True and
            observed.get("commonPreviewVisible") is True and observed.get("originalMediaSendCompleted") is True,
            "real common prefix did not complete")
    points = raw["checkpoints"]
    require([point["name"] for point in points] ==
            ["reachable_common_base", "caption_entered", "original_media_positive_control_done"] and
            len(bundle["layouts"]) == 3, "common prefix actual checkpoint coverage changed")
    layouts = []
    for index, (point, pair) in enumerate(zip(points, bundle["layouts"])):
        require(pair["original"] == point["layout"], "original full UI record was substituted")
        layout = json.loads(read_native_artifact(pair))
        check_ui(layout, fixture, caption="" if index == 0 else observed["caption"], done=index == 2)
        layouts.append(layout)
    commands = [command for command in original["diagnostics"]["commands"] if command.get("caseId") == row["caseId"]]
    logs = {}
    for pair in bundle['commandLogs']:
        path = Path(pair['original']['path'])
        logs[str((path if path.is_absolute() else ROOT / path).resolve())] = read_native_artifact(pair)
    for command in commands:
        record = command['log']
        path = Path(record['path'])
        data = logs.get(str((path if path.is_absolute() else ROOT / path).resolve()))
        require(data is not None and len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'],
                'original common-prefix command log missing/substituted')
    require(any(command.get("exitCode") == 0 and command.get("args", [])[:4] ==
                ["shell", "uitest", "uiInput", "inputText"] and command["args"][-1] == observed["caption"]
                for command in commands), "actual caption input command absent")
    send = next(node for node in _attributes(project_tree(layouts[1])) if node.get("id") == "attachment_send")
    require(send.get("visible") == "true" and send.get("enabled") == "true" and send.get("clickable") == "true",
            "common send not eligible")
    require(any(command.get("exitCode") == 0 and command.get("args", [])[:4] ==
                ["shell", "uitest", "uiInput", "click"] for command in commands), "actual positive-control click absent")
    return {"applies": True, "guardId": GUARD, "closureEligible": True,
            "sourceMatchProducesNoSemanticVerdict": True, "fullUiCheckpoints": 3}


def validate_report(report, contract):
    return [validate_entry_failure(row, report, contract=contract) for row in report["semantic"]["cases"]]
