"""Task12 fresh source-bound entry evidence using the exact calibration validators."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

try:
    from . import task12_13_formal_core as core
    from . import verify_task12_base_device_entry as arkts
except ImportError:
    import task12_13_formal_core as core
    import verify_task12_base_device_entry as arkts


POLICY_ID = "task12.live-exact-calibration-entry.v1"
ANDROID_VALIDATOR = core.ROOT / "state_tests/runtime/android/12_report_room/action_prefix/verify.py"


def android_validator():
    spec = importlib.util.spec_from_file_location("task12_live_android_entry", ANDROID_VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_compiled_sources(compiled, report):
    declared = report.get("provenance", {}).get("productionSources", [])
    indexed = {item["path"]: item for item in declared}
    if not indexed or len(indexed) != len(declared):
        raise ValueError("Task12 production source provenance missing or duplicated")
    production = [item for item in compiled if Path(item["path"]).suffix in {".kt", ".ets"}]
    if not production or len({item["path"] for item in production}) != len(production):
        raise ValueError("Task12 compiled production source manifest missing or duplicated")
    for item in production:
        digest, size = item.get("sha256"), item.get("bytes")
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(char not in "0123456789abcdef" for char in digest) or
                type(size) is not int or size <= 0):
            raise ValueError("Task12 compiled production source hash/size missing")
        bound = indexed.get(item["path"], {})
        if any(item.get(key) != bound.get(key) for key in ("sha256", "bytes")):
            raise ValueError("Task12 compiled production source hash binding differs")


def entry_rows(contract, raw_report, raw_path, platform, *, device_verification=None):
    rows = raw_report.get("observations") if platform == "android" else raw_report["semantic"]["cases"]
    indexed = {item.get("key", item.get("caseId")): item for item in rows}
    result = []
    used_ids, used_pixels = set(), set()
    verifier = android_validator() if platform == "android" else None
    for spec in contract["cases"]:
        raw = indexed.get(spec["key"], indexed.get(spec["caseId"]))
        if raw is None:
            raise ValueError("Task12 live entry case missing")
        if platform == "android":
            row = verifier.validate_probe(raw, spec, used_ids, used_pixels)
        else:
            if device_verification is None:
                raise ValueError("Task12 device entry independent assessment missing")
            row = copy.deepcopy(raw)
        row.update(key=spec["key"], given=copy.deepcopy(spec["given"]), event=copy.deepcopy(spec["event"]),
                   observed=None, invariantChecks=[], unevaluatedInvariants=copy.deepcopy(spec["invariants"]),
                   unobservedExpectedFields=list(spec["expected"]))
        row["entryFailureEvidence"] = {
            "policyId": POLICY_ID, "canonicalGivenEstablished": True, "positiveControlCompleted": True,
            "rawReport": core.file_record(raw_path), "platform": platform,
            "deviceVerification": device_verification,
        }
        result.append(row)
    return result


def validate_entry_failure(row, report, used_observation_ids, *, contract):
    if (report.get("taskId") != "12_report_room" or report.get("role") not in {"base", "final", "agent"} or
            report.get("platform") not in {"android", "arkts"} or
            row.get("entryFailureEvidence", {}).get("policyId") != POLICY_ID):
        raise ValueError("Task12 live entry policy identity differs")
    evidence = row["entryFailureEvidence"]
    raw_path = Path(evidence["rawReport"]["path"]).resolve()
    if not raw_path.is_relative_to(core.ROOT / "experiment_results") or core.file_record(raw_path) != evidence["rawReport"]:
        raise ValueError("Task12 live entry raw report hash differs")
    raw = core.load(raw_path)
    if report["platform"] == "arkts":
        build_path = arkts.verify_record(raw["compile"]["build"])
        build = core.load(build_path)
        source = report.get("provenance", {}).get("candidateSource")
        if not source or build.get("source") != source or build.get("productionUnchanged") is not True:
            raise ValueError("Task12 executed ArkTS source binding differs")
        application = core.load(arkts.verify_record(build["applicationBuild"]))
        if (application.get("source") != source or application.get("passed") is not True or
                application.get("productionUnchanged") is not True or
                any(application["hap"].get(key) != raw["compile"]["hap"].get(key)
                    for key in ("sha256", "bytes"))):
            raise ValueError("Task12 executed ArkTS application/HAP binding differs")
        validate_compiled_sources(application.get("sources", []), report)
        receipt = evidence.get("deviceVerification")
        if not receipt or core.file_record(Path(receipt["path"])) != receipt:
            raise ValueError("Task12 device verification receipt changed")
        assessment = core.load(Path(receipt["path"]))
        if assessment.get("validated") is not True or assessment.get("rawReport") != evidence["rawReport"]:
            raise ValueError("Task12 independent device verification failed")
        for item in raw["diagnostics"]["commands"]:
            arkts.verify_record(item["log"])
        for raw_row in raw["semantic"]["cases"]:
            kinds = ("details", "stable", "confirmation", "restored")
            for point, kind in zip(raw_row["checkpoints"], kinds):
                arkts.verify_layout(point["layout"], kind)
    else:
        source = report.get("provenance", {}).get("candidateSource")
        if not source or raw.get("provenance", {}).get("source") != source:
            raise ValueError("Task12 executed Android source binding differs")
        validate_compiled_sources(raw.get("provenance", {}).get("productionSources", []), report)
        log = raw.get("log", {})
        if raw.get("runtimeCompile", {}).get("status") != "passed" or not log.get("path"):
            raise ValueError("Task12 Android runtime compile/log evidence missing")
        log_path = Path(log["path"])
        if core.sha256(log_path) != log.get("sha256"):
            raise ValueError("Task12 Android runtime log hash differs")
        logged = [json.loads(line[len("RUNTIME_RESULT "):]) for line in log_path.read_text().splitlines()
                  if line.startswith("RUNTIME_RESULT ")]
        if logged != raw.get("observations"):
            raise ValueError("Task12 Android observations differ from executed trace")
    expected = next(item for item in entry_rows(contract, raw, raw_path, report["platform"],
                    device_verification=evidence.get("deviceVerification")) if item["caseId"] == row["caseId"])
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError("Task12 entry metadata differs: " + key)
    raw_rows = raw.get("observations", raw.get("semantic", {}).get("cases", []))
    selected = next(item for item in raw_rows if item.get("key", item.get("caseId")) in {row["key"], row["caseId"]})
    run_id = (selected["checkpoints"][0]["state"].get("executionId") if report["platform"] == "android"
              else selected["entryFailureEvidence"]["caseRunId"])
    identity = (evidence["rawReport"]["sha256"], run_id)
    if not run_id or identity in used_observation_ids:
        raise ValueError("Task12 execution missing or reused")
    used_observation_ids.add(identity)
