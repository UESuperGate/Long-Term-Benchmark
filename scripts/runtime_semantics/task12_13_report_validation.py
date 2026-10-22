"""Direct public-matrix validation for Task12/13 formal reports.

The Task13 entry extension is audited separately until the parent adds its
public routing. A successful extension check does not turn a public rejection
into a public validation success.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from . import task12_13_formal_core as core
    from . import task13_android_entry_validation as entry
    from . import task12_live_entry_validation as task12_entry
except ImportError:
    import task12_13_formal_core as core
    import task13_android_entry_validation as entry
    import task12_live_entry_validation as task12_entry

sys.path.insert(0, str(core.ROOT))
from scripts.run_runtime_transition_matrix import validate_report


def validate_formal_output(report_path: Path, contract: dict) -> dict:
    result = core.load(report_path)
    root = report_path.resolve().with_suffix(".strict-evidence")
    paths = {role: root / role / "runtime.json" for role in ("base", "final", "agent")}
    paths["formal"] = report_path.resolve()
    assessments = []
    for role, path in paths.items():
        assessment = {"role": role, "path": str(path)}
        if not path.is_file():
            assessment.update(status="not_scored", reason="runtime report unavailable")
            assessments.append(assessment)
            continue
        report = core.load(path)
        assessment["report"] = core.file_record(path)
        try:
            validate_report(report, contract)
            assessment["status"] = "passed"
        except (ValueError, KeyError, OSError) as error:
            assessment.update(status="rejected", reason=str(error))
        extension = (entry if report.get("taskId") == "13_user_verification" and report.get("platform") == "android"
                     else task12_entry if report.get("taskId") == "12_report_room" else None)
        if extension is not None and any(row.get("entryFailureEvidence") for row in report["semantic"]["cases"]):
            used = set()
            try:
                for row in report["semantic"]["cases"]:
                    if row.get("entryFailureEvidence"):
                        extension.validate_entry_failure(row, report, used, contract=contract)
                assessment["taskEntryExtension"] = {"status": "passed", "caseCount": len(used),
                                                     "validator": core.file_record(Path(extension.__file__))}
            except (ValueError, KeyError, OSError) as error:
                assessment["taskEntryExtension"] = {"status": "rejected", "reason": str(error)}
        assessments.append(assessment)
    return {
        "schemaVersion": 1, "taskId": result["taskId"], "platform": result["platform"],
        "directCall": "run_runtime_transition_matrix.validate_report(report, canonical_contract)",
        "ready": all(item["status"] == "passed" for item in assessments),
        "reports": assessments,
    }


def finalize(result: dict, output: Path, contract: dict) -> dict:
    assessment = validate_formal_output(output, contract)
    result.setdefault("diagnostics", {})["publicMatrixValidation"] = {
        "ready": assessment["ready"],
        "directCall": assessment["directCall"],
        "reports": [{key: value for key, value in item.items() if key not in {"report", "path"}}
                    for item in assessment["reports"]],
    }
    if not assessment["ready"]:
        result["publication"] = {
            "eligible": False,
            "reason": "Public matrix validation incomplete; see publicMatrixValidation and task entry extension assessment",
        }
    core.write(output, result)
    core.write(output.with_suffix(".matrix-validation.json"), validate_formal_output(output, contract))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assessment = validate_formal_output(args.report, core.load(args.contract))
    core.write(args.output, assessment)
    print(json.dumps(assessment, ensure_ascii=False))
    return 0 if assessment["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
