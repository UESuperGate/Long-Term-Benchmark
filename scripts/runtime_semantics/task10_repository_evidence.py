"""Retain actual repository-bound device snapshots before temporary cleanup."""
import copy
import json
from pathlib import Path

try:
    from . import tasks10_11_runtime_evidence as shared
    from .task10_native_artifacts import (
        read_native_artifact, retain_repository_rows, retain_device_ui_rows, verify_repository_row,
    )
except ImportError:
    import tasks10_11_runtime_evidence as shared
    from task10_native_artifacts import (
        read_native_artifact, retain_repository_rows, retain_device_ui_rows, verify_repository_row,
    )

BINDING = "task10.original-page.repository.v2"


def attach_child(report, contract, artifacts, retained):
    if report["taskId"] != "10_media_upload_quality" or report["provenance"].get("runtimeBinding") != BINDING:
        raise ValueError("Task10 repository evidence requires its actual runner binding")
    result = copy.deepcopy(report)
    retained = Path(retained)
    retained.mkdir(parents=True, exist_ok=True)
    sources = shared.collect_slice_sources(Path(artifacts))
    if not sources:
        raise ValueError("No actual compiled production source manifests")
    manifests = {}
    for source in sources:
        old = source["runtimeSlice"]
        key = old["path"], old["sha256"]
        if key not in manifests:
            target = retained / f"slice-{len(manifests)}.json"
            target.write_bytes(shared.read_record(old))
            manifests[key] = shared.record(target)
        source["runtimeSlice"] = manifests[key]
    result["provenance"]["productionSources"] = sources
    # Retain original bytes before normalization or any scratch deletion.
    retain_repository_rows(result, artifacts, retained)
    capability = result["provenance"].get("entryCapability", {})
    if capability.get("snapshot"):
        target = retained / "actual-entry-capability.snapshot.json"
        target.write_bytes(shared.read_record(capability["snapshot"]))
        capability["snapshot"] = shared.record(target)
    for index, row in enumerate(result["semantic"]["cases"]):
        if row.get("caseId") == "mq_state_009_failure_cancel_retry" and row.get("status") == "not_scored" and \
                str(row.get("reason", "")).startswith("Canonical pre-event prepared media is not established"):
            try:
                from . import task10_repository_prefix_policy as prefix
            except ImportError:
                import task10_repository_prefix_policy as prefix
            execution_path = Path(row["execution"]["path"])
            try:
                bound = prefix.bind(row, result, contract, execution_path.parent / "native-result.json",
                                    execution_path, retained / "prepared-prefix")
                prefix.validate_entry_failure(bound, result, set(), contract=contract)
                row = bound
                result["semantic"]["cases"][index] = row
            except ValueError as error:
                row["prefixPolicyDiagnostic"] = str(error)
        for point_index, point in enumerate(row.get("checkpoints", [])):
            if point.get("actualSnapshot"):
                data = shared.read_record(point["actualSnapshot"])
            elif point.get("label"):
                data = (json.dumps({"label": point["label"], "state": point["state"]}, indent=2) + "\n").encode()
            else:
                continue
            original = json.loads(data)
            frame = original["state"]
            production = frame.get("state") if isinstance(frame.get("state"), dict) else frame.get("stateAfter")
            if not isinstance(production, dict) or not isinstance(frame.get("controls"), dict):
                raise ValueError("Actual device state/control snapshot unavailable")
            target = retained / f"actual-{index}-{point_index}.snapshot.json"
            target.write_bytes(data)
            point.update(name=original.get("label", point.get("name")), actualSnapshot=shared.record(target),
                         state={"production": production, "controls": frame["controls"],
                                "routeName": frame.get("routeName"), "windowId": frame.get("windowId"),
                                "viewport": frame.get("viewport")})
    for key, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored")):
        result["semantic"][key] = sum(row["status"] == status for row in result["semantic"]["cases"])
    # This is diagnostic evidence only until the unmodified public route accepts it.
    (retained / "diagnostic.pending-public.runtime.json").write_text(json.dumps(result, indent=2) + "\n")
    validate_report(result, contract)
    return result


def validate_report(report, contract):
    if report["provenance"].get("runtimeBinding") != BINDING:
        raise ValueError("Task10 repository runtime binding missing")
    for row in report["semantic"]["cases"]:
        verify_repository_row(row, report)
        for point in row.get("checkpoints", []):
            if point.get("name") not in {"before:event", "after:event"}:
                continue
            frame = json.loads(shared.read_record(point["actualSnapshot"]))["state"]
            production = frame.get("state") if isinstance(frame.get("state"), dict) else frame.get("stateAfter")
            if point["state"]["production"] != production or point["state"]["controls"] != frame["controls"]:
                raise ValueError("Actual Task10 snapshot differs from retained state")
    shared.validate_report(report, contract)


def attach_control(report, contract, artifacts, retained):
    """Retain the exact original host-observer output used by legacy controls."""
    if report.get("provenance", {}).get("entryEligibilityRejected") is True:
        try:
            from .task10_arkts_closure_retention import attach_unbound_entry
        except ImportError:
            from task10_arkts_closure_retention import attach_unbound_entry
        return attach_unbound_entry(report, contract, artifacts, retained)
    result = shared.attach_child(report, contract, artifacts, Path(retained))
    retain_device_ui_rows(result, artifacts, retained)
    # Keep the complete lossless map even if the additional eligibility conjunct rejects it.
    bound = Path(retained) / 'pre-closure-validation.runtime.json'
    bound.write_text(json.dumps(result, indent=2) + '\n')
    shared.validate_report(result, contract)
    try:
        from .task10_arkts_closure_evidence import validate_report as validate_closure
    except ImportError:
        from task10_arkts_closure_evidence import validate_report as validate_closure
    validate_closure(result, contract)
    return result
