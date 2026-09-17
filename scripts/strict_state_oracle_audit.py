#!/usr/bin/env python3
"""
Audit Element X state-test YAML files before dynamic execution.

This is intentionally deterministic and evaluator-side only. It does not ask
the development agent to create bindings, and it does not treat legacy
state_test_result markers as a functional oracle.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", r"C:\Users\xiexi\qingyu"))
STATE_TEST_DIR = ROOT / "state_tests"
REPORT_DIR = Path(os.environ.get("QINGYU_STATE_REPORT_DIR", str(ROOT / "verification_reports" / "state_dynamic")))


COMPONENT_ONLY_EVENTS = (
    "sdk_",
    "timer_tick",
    "profile_status_refreshed",
    "remote_user_status_",
    "permission_",
    "biometric_",
    "qr_data_",
    "scan_result_",
    "continuation_",
    "cancel_connection",
)


@dataclass
class StateCase:
    file: Path
    task_id: str
    task_title: str
    case_id: str
    title: str
    raw: str
    start_line: int


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_task_header(text: str) -> tuple[str, str]:
    task_match = re.search(r"(?ms)^task:\s*\n(?P<body>.*?)(?:^source:|^platform_bindings:|^state_dimensions:|^cases:)", text)
    if not task_match:
        return "", ""
    body = task_match.group("body")
    task_id = ""
    title = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("id:"):
            task_id = unquote(stripped.split(":", 1)[1])
        elif stripped.startswith("title:"):
            title = unquote(stripped.split(":", 1)[1])
    return task_id, title


def parse_cases(path: Path) -> list[StateCase]:
    text = path.read_text(encoding="utf-8-sig")
    task_id, task_title = parse_task_header(text)
    lines = text.splitlines()
    starts: list[int] = []
    for index, line in enumerate(lines):
        if re.match(r"^  - id:\s*", line):
            starts.append(index)

    cases: list[StateCase] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        block_lines = lines[start:end]
        raw = "\n".join(block_lines)
        case_id = unquote(block_lines[0].split(":", 1)[1])
        title = ""
        for line in block_lines[1:]:
            if line.startswith("    title:"):
                title = unquote(line.strip().split(":", 1)[1])
                break
        cases.append(StateCase(path, task_id, task_title, case_id, title, raw, start + 1))
    return cases


def extract_inline_tokens(raw: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"visible": [], "hidden": [], "enabled": [], "disabled": [], "properties": []}
    for key in ("visible", "hidden", "enabled", "disabled"):
        for match in re.finditer(rf"^\s*{key}:\s*\[([^\]]*)\]", raw, re.MULTILINE):
            tokens = [unquote(part) for part in match.group(1).split(",") if part.strip()]
            buckets[key].extend(tokens)

    in_properties = False
    prop_indent = 0
    for line in raw.splitlines():
        if re.match(r"^\s*properties:\s*$", line):
            in_properties = True
            prop_indent = len(line) - len(line.lstrip(" "))
            continue
        if in_properties:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if not stripped:
                continue
            if indent <= prop_indent:
                in_properties = False
                continue
            match = re.match(r"^\s*([A-Za-z0-9_]+)\s*:", line)
            if match:
                buckets["properties"].append(match.group(1))
                value = stripped.split(":", 1)[1].strip()
                if value and value not in ("{}", "[]", "null"):
                    buckets["properties"].append(unquote(value))
    for key, values in buckets.items():
        buckets[key] = sorted(set(values))
    return buckets


def extract_indented_block(raw: str, key: str, indent: int) -> str:
    lines = raw.splitlines()
    start = None
    prefix = " " * indent + key + ":"
    for index, line in enumerate(lines):
        current_indent = len(line) - len(line.lstrip(" "))
        if (line == prefix or line.strip() == f"{key}:") and current_indent == indent:
            start = index + 1
            break
    if start is None:
        return ""

    body: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        current_indent = len(line) - len(line.lstrip(" "))
        if stripped and current_indent <= indent:
            break
        body.append(line)
    return "\n".join(body)


def extract_root_expect_ui(raw: str) -> str:
    return extract_indented_block(raw, "expect_ui", 4)


def split_transition_expect_ui_blocks(raw: str) -> list[str]:
    blocks: list[str] = []
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        if not re.match(r"^\s{6}-\s*event:\s*", lines[index]):
            index += 1
            continue
        start = index
        index += 1
        while index < len(lines):
            stripped = lines[index].strip()
            current_indent = len(lines[index]) - len(lines[index].lstrip(" "))
            if stripped and current_indent <= 6:
                break
            index += 1
        block = "\n".join(lines[start:index])
        expect_ui = extract_indented_block(block, "expect_ui", 8)
        if expect_ui:
            blocks.append(expect_ui)
    return blocks


def extract_scalar(raw: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", raw, re.MULTILINE)
    return unquote(match.group(1)) if match else ""


def extract_list_items(raw: str, key: str) -> list[str]:
    lines = raw.splitlines()
    items: list[str] = []
    in_block = False
    block_indent = 0
    for line in lines:
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            in_block = True
            block_indent = len(line) - len(line.lstrip(" "))
            continue
        if not in_block:
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if not stripped:
            continue
        if indent <= block_indent:
            in_block = False
            continue
        if stripped.startswith("- "):
            items.append(unquote(stripped.removeprefix("- ")))
    return items


def count_transition_events(raw: str) -> int:
    return len(re.findall(r"^\s*-\s*event:", raw, re.MULTILINE))


def parse_quality_gate(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    gate_match = re.search(r"(?ms)^quality_gates:\s*\n(?P<body>.*?)(?:^cases:)", text)
    if not gate_match:
        return {"minimumCases": 0, "requiredFunctionalAreas": [], "discriminationRules": []}
    body = gate_match.group("body")
    minimum_match = re.search(r"^\s*minimum_cases:\s*(\d+)\s*$", body, re.MULTILINE)
    area_match = re.search(r"^\s*required_functional_areas:\s*\[([^\]]*)\]", body, re.MULTILINE)
    areas = [unquote(part) for part in area_match.group(1).split(",") if part.strip()] if area_match else []
    return {
        "minimumCases": int(minimum_match.group(1)) if minimum_match else 0,
        "requiredFunctionalAreas": areas,
        "discriminationRules": extract_list_items(body, "discrimination_rules"),
    }


def classify_case(case: StateCase) -> dict:
    issues: list[dict] = []
    quality_warnings: list[dict] = []
    status = "valid_oracle"
    polarity_role = "new_feature_discriminator"

    if case.case_id == "us_state_003_custom_input_and_emoji_sheet" and "visible: [emoji_sheet_loading]" in case.raw:
        status = "invalid_oracle"
        issues.append({
            "severity": "P1",
            "kind": "oracle_contradiction",
            "message": (
                "Original Android final does not render a visible sheet for EmojiPickerSheetState.Loading; "
                "UserStatusView handles Hidden and Loading as no-op UI states."
            ),
        })

    if case.case_id == "us_state_004_save_success_propagates_surfaces" and "visible: [user_status_saving_indicator]" in case.raw:
        status = "invalid_oracle"
        issues.append({
            "severity": "P1",
            "kind": "oracle_contradiction",
            "message": (
                "Original Android final hides the picker immediately on SetStatus before the SDK call; "
                "a visible saving indicator inside the editor is not a reliable final expectation."
            ),
        })

    if case.case_id == "us_state_012_custom_input_dirty_state" and "disabled: [save_status_button]" in case.raw:
        status = "invalid_oracle"
        issues.append({
            "severity": "P1",
            "kind": "oracle_contradiction",
            "message": (
                "Original Android final's custom Layout places Cancel, not a disabled Save button, "
                "when the edited status is empty or unchanged."
            ),
        })

    if case.case_id == "us_state_014_update_loading_disables_mutating_actions" and "disabled: [save_status_button" in case.raw:
        status = "invalid_oracle"
        issues.append({
            "severity": "P1",
            "kind": "oracle_contradiction",
            "message": (
                "The expected disabled controls are not established by the original Android final view; "
                "this needs recalibration against the tagged final before scoring."
            ),
        })

    if case.case_id == "lnd_state_027_final_qr_timeout_notice_and_retry" and "qr_data: available" in case.raw and "timeout: expired" in case.raw:
        status = "invalid_oracle"
        issues.append({
            "severity": "P1",
            "kind": "oracle_contradiction",
            "message": (
                "The given state combines an expired timeout with available QR data and a visible QR surface; "
                "the preceding timeout case expects expired QR data and QR hidden, so reachability is not proven."
            ),
        })

    if case.case_id == "lnd_state_029_no_qr_without_supported_capability" and "support: unknown" in case.raw and "flow_mode: show_qr" in case.raw:
        status = "invalid_oracle"
        issues.append({
            "severity": "P1",
            "kind": "oracle_contradiction",
            "message": (
                "The given state asks for support=unknown while also being in show_qr/qr_loading; "
                "that conflicts with the capability gate described by the test itself."
            ),
        })

    legacy_regression_ids = {
        "gm_state_022_base_single_media_unchanged": (
            "This is a regression guard for pre-existing single-media behavior, not a new-feature "
            "base-fail/final-pass discriminator."
        ),
        "ll_state_021_static_location_unchanged": (
            "This is a regression guard for existing static-location behavior, not a new-feature "
            "base-fail/final-pass discriminator."
        ),
        "tp_state_011_text_event_not_scanned": (
            "This is a regression guard for ordinary text events, not a new-feature base-fail/final-pass discriminator."
        ),
    }
    if case.case_id in legacy_regression_ids:
        if status == "valid_oracle":
            polarity_role = "regression_guard"
        issues.append({"severity": "P1", "kind": "not_base_fail_discriminator", "message": legacy_regression_ids[case.case_id]})

    synthetic_events = sorted({event for event in COMPONENT_ONLY_EVENTS if event in case.raw})
    if synthetic_events:
        issues.append({
            "severity": "P2",
            "kind": "requires_controlled_runtime_fixture",
            "message": "Case includes synthetic SDK/timer/permission/service events and needs evaluator-owned controlled fixtures.",
            "events": synthetic_events,
        })

    release_semantics_final = "release_semantics: final" in case.raw
    if release_semantics_final and polarity_role == "new_feature_discriminator":
        polarity_role = "final_positive_discriminator"

    root_tokens = extract_inline_tokens(extract_root_expect_ui(case.raw))
    transition_tokens_by_step = [extract_inline_tokens(block) for block in split_transition_expect_ui_blocks(case.raw)]
    transition_tokens: dict[str, list[str]] = {"visible": [], "hidden": [], "enabled": [], "disabled": [], "properties": []}
    for step_tokens in transition_tokens_by_step:
        for bucket, values in step_tokens.items():
            transition_tokens[bucket].extend(values)
    transition_tokens = {key: sorted(set(values)) for key, values in transition_tokens.items()}
    root_assertion_token_count = sum(len(value) for value in root_tokens.values())
    transition_assertion_token_count = sum(len(value) for value in transition_tokens.values())
    assertion_token_count = root_assertion_token_count + transition_assertion_token_count
    transition_count = count_transition_events(case.raw)
    functional_area = extract_scalar(case.raw, "functional_area")
    fixture_kind = extract_scalar(case.raw, "fixture_kind")
    base_failure_signal = extract_scalar(case.raw, "base_failure_signal")
    mutation_guards = extract_list_items(case.raw, "mutation_guards")
    has_runtime_oracle = "runtime_oracle:" in case.raw
    if not functional_area:
        quality_warnings.append({"severity": "P2", "kind": "missing_functional_area", "message": "Case lacks functional_area metadata."})
    if not fixture_kind:
        quality_warnings.append({"severity": "P2", "kind": "missing_fixture_kind", "message": "Case lacks fixture_kind metadata."})
    if not has_runtime_oracle:
        quality_warnings.append({"severity": "P1", "kind": "missing_runtime_oracle", "message": "Case lacks runtime_oracle metadata."})
    if not mutation_guards:
        quality_warnings.append({"severity": "P1", "kind": "missing_mutation_guard", "message": "Case has no mutation guard."})
    if assertion_token_count < 3:
        quality_warnings.append({"severity": "P2", "kind": "low_assertion_token_count", "message": "Case has fewer than three UI/property assertion tokens."})
    discriminative_score = assertion_token_count + (transition_count * 2) + (2 if root_tokens["properties"] else 0) + min(len(mutation_guards), 3)
    return {
        "taskId": case.task_id,
        "taskTitle": case.task_title,
        "caseId": case.case_id,
        "caseTitle": case.title,
        "file": str(case.file),
        "line": case.start_line,
        "status": status,
        "polarityRole": polarity_role,
        "releaseSemanticsFinal": release_semantics_final,
        "functionalArea": functional_area,
        "fixtureKind": fixture_kind,
        "baseFailureSignal": base_failure_signal,
        "transitionCount": transition_count,
        "rootAssertionTokenCount": root_assertion_token_count,
        "transitionAssertionTokenCount": transition_assertion_token_count,
        "assertionTokenCount": assertion_token_count,
        "hasPropertyAssertions": bool(root_tokens["properties"] or transition_tokens["properties"]),
        "hasRuntimeOracle": has_runtime_oracle,
        "mutationGuards": mutation_guards,
        "discriminativeScore": discriminative_score,
        "requiresControlledRuntimeFixture": bool(synthetic_events),
        "assertionTokens": root_tokens,
        "transitionAssertionTokens": transition_tokens,
        "issues": issues,
        "qualityWarnings": quality_warnings,
    }


def build_report() -> dict:
    cases: list[StateCase] = []
    for path in sorted(STATE_TEST_DIR.glob("elementx-state-test*.yaml")):
        cases.extend(parse_cases(path))
    audited = [classify_case(case) for case in cases]
    counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    by_task: dict[str, dict[str, int]] = {}
    functional_area_counts: dict[str, dict[str, int]] = {}
    fixture_kind_counts: dict[str, dict[str, int]] = {}
    quality_gate_results: dict[str, dict] = {}
    transition_cases = 0
    property_cases = 0
    warning_cases = 0
    for item in audited:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
        role_counts[item["polarityRole"]] = role_counts.get(item["polarityRole"], 0) + 1
        task_counts = by_task.setdefault(item["taskId"], {})
        task_counts[item["status"]] = task_counts.get(item["status"], 0) + 1
        area_counts = functional_area_counts.setdefault(item["taskId"], {})
        area = item["functionalArea"] or "missing"
        area_counts[area] = area_counts.get(area, 0) + 1
        fixture_counts = fixture_kind_counts.setdefault(item["taskId"], {})
        fixture = item["fixtureKind"] or "missing"
        fixture_counts[fixture] = fixture_counts.get(fixture, 0) + 1
        if item["transitionCount"] > 0:
            transition_cases += 1
        if item["hasPropertyAssertions"]:
            property_cases += 1
        if item["qualityWarnings"]:
            warning_cases += 1

    for path in sorted(STATE_TEST_DIR.glob("elementx-state-test*.yaml")):
        file_cases = [item for item in audited if Path(item["file"]).name == path.name]
        gate = parse_quality_gate(path)
        task_id = file_cases[0]["taskId"] if file_cases else path.stem
        observed_areas = sorted({item["functionalArea"] for item in file_cases if item["functionalArea"]})
        missing_areas = sorted(set(gate["requiredFunctionalAreas"]) - set(observed_areas))
        quality_gate_results[task_id] = {
            "file": str(path),
            "minimumCases": gate["minimumCases"],
            "actualCases": len(file_cases),
            "requiredFunctionalAreas": gate["requiredFunctionalAreas"],
            "observedFunctionalAreas": observed_areas,
            "missingFunctionalAreas": missing_areas,
            "passesMinimumCases": len(file_cases) >= gate["minimumCases"],
            "passesRequiredAreas": not missing_areas,
        }

    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "summary": {
            "totalCases": len(audited),
            "statusCounts": counts,
            "polarityRoleCounts": role_counts,
            "byTask": by_task,
            "functionalAreaCounts": functional_area_counts,
            "fixtureKindCounts": fixture_kind_counts,
            "casesWithTransitions": transition_cases,
            "casesWithPropertyAssertions": property_cases,
            "casesWithQualityWarnings": warning_cases,
            "qualityGateResults": quality_gate_results,
            "strictPolicy": (
                "Only valid_oracle cases may be scored. Regression guards are reported separately. "
                "Legacy version/feature markers are contaminated evidence and cannot produce a pass verdict."
            ),
        },
        "cases": audited,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines: list[str] = [
        "# Strict State Oracle Audit",
        "",
        f"- Generated: {report['generatedAt']}",
        f"- Total cases: {report['summary']['totalCases']}",
        f"- Status counts: {report['summary']['statusCounts']}",
        f"- Polarity roles: {report['summary']['polarityRoleCounts']}",
        f"- Cases with transitions: {report['summary']['casesWithTransitions']}",
        f"- Cases with property assertions: {report['summary']['casesWithPropertyAssertions']}",
        f"- Cases with quality warnings: {report['summary']['casesWithQualityWarnings']}",
        "",
        "## Production Quality Gates",
        "",
    ]
    for task_id, gate in report["summary"]["qualityGateResults"].items():
        status = "PASS" if gate["passesMinimumCases"] and gate["passesRequiredAreas"] else "FAIL"
        lines.append(f"- `{task_id}`: {status}; cases {gate['actualCases']}/{gate['minimumCases']}; missing areas: {gate['missingFunctionalAreas']}")
    lines.extend([
        "",
        "## Blocking Issues",
        "",
    ])
    blocking = [case for case in report["cases"] if case["status"] != "valid_oracle" or case["polarityRole"] == "regression_guard"]
    if not blocking:
        lines.append("- None")
    for case in blocking:
        lines.append(f"- `{case['caseId']}` `{case['status']}` `{case['polarityRole']}` at `{case['file']}:{case['line']}`")
        for issue in case["issues"]:
            lines.append(f"  - {issue['severity']} {issue['kind']}: {issue['message']}")
    lines.extend([
        "",
        "## Runtime Fixture Needs",
        "",
    ])
    fixture_cases = [case for case in report["cases"] if case["requiresControlledRuntimeFixture"]]
    lines.append(f"- Cases requiring controlled SDK/timer/permission fixtures: {len(fixture_cases)}")
    lines.extend([
        "",
        "## Functional Area Coverage",
        "",
    ])
    for task_id, counts in report["summary"]["functionalAreaCounts"].items():
        rendered = ", ".join(f"{area}={count}" for area, count in sorted(counts.items()))
        lines.append(f"- `{task_id}`: {rendered}")
    lines.extend([
        "",
        "## Fixture Kind Coverage",
        "",
    ])
    for task_id, counts in report["summary"]["fixtureKindCounts"].items():
        rendered = ", ".join(f"{fixture}={count}" for fixture, count in sorted(counts.items()))
        lines.append(f"- `{task_id}`: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(REPORT_DIR / "strict_state_oracle_audit.json"))
    parser.add_argument("--markdown", default=str(REPORT_DIR / "strict_state_oracle_audit.md"))
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    json_path = Path(args.json)
    md_path = Path(args.markdown)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Cases: {report['summary']['totalCases']}")
    print(f"Status counts: {report['summary']['statusCounts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
