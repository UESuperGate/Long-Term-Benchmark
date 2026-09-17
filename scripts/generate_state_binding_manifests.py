#!/usr/bin/env python3
"""
Generate evaluator-owned semantic binding manifests from state-test YAML files.

This does not ask a development agent to produce bindings. It converts the
public state-test contract into a deterministic manifest that runners can use
to score per-case UI tree captures.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", r"C:\Users\xiexi\qingyu"))
STATE_TEST_DIR = ROOT / "state_tests"
OUT_DIR = Path(os.environ.get("QINGYU_BINDING_MANIFEST_DIR", str(STATE_TEST_DIR / "bindings")))


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_task_header(text: str) -> dict:
    task_match = re.search(r"(?ms)^task:\s*\n(?P<body>.*?)(?:^source:|^platform_bindings:|^state_dimensions:|^quality_gates:|^cases:)", text)
    if not task_match:
        return {}
    task: dict[str, str] = {}
    for line in task_match.group("body").splitlines():
        stripped = line.strip()
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            task[key.strip()] = unquote(value)
    return task


def split_cases(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("  - id:")]
    cases: list[tuple[int, str]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        cases.append((start + 1, "\n".join(lines[start:end])))
    return cases


def extract_inline_tokens(raw: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"visible": [], "hidden": [], "enabled": [], "disabled": []}
    for key in buckets:
        for match in re.finditer(rf"^\s*{key}:\s*\[([^\]]*)\]", raw, re.MULTILINE):
            buckets[key].extend(unquote(part) for part in match.group(1).split(",") if part.strip())
    return {key: sorted(set(values)) for key, values in buckets.items()}


def extract_indented_block(raw: str, key: str, indent: int) -> str:
    lines = raw.splitlines()
    start = None
    prefix = " " * indent + key + ":"
    for index, line in enumerate(lines):
        if line == prefix or line.strip() == f"{key}:".strip() and (len(line) - len(line.lstrip(" "))) == indent:
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


def split_transition_blocks(raw: str) -> list[dict]:
    lines = raw.splitlines()
    transitions: list[dict] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        event_match = re.match(r"^\s{6}-\s*event:\s*(.+?)\s*$", line)
        if not event_match:
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
        transitions.append({
            "event": unquote(event_match.group(1)),
            "expectUi": extract_indented_block(block, "expect_ui", 8),
            "raw": block,
        })
    return transitions


def extract_properties(raw: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    lines = raw.splitlines()
    in_properties = False
    prop_indent = 0
    for line in lines:
        if re.match(r"^\s*properties:\s*$", line):
            in_properties = True
            prop_indent = len(line) - len(line.lstrip(" "))
            continue
        if not in_properties:
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if not stripped:
            continue
        if indent <= prop_indent:
            in_properties = False
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            properties[key.strip()] = unquote(value)
    return properties


def extract_scalar(raw: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", raw, re.MULTILINE)
    return unquote(match.group(1)) if match else ""


def extract_case_id(raw: str) -> str:
    first = raw.splitlines()[0].strip()
    return unquote(first.split(":", 1)[1])


def extract_case_title(raw: str) -> str:
    return extract_scalar(raw, "title")


def extract_transition_count(raw: str) -> int:
    return len(re.findall(r"^\s*-\s*event:", raw, re.MULTILINE))


def manifest_for(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    task = parse_task_header(text)
    cases = []
    for line_no, raw in split_cases(text):
        root_expect_ui = extract_root_expect_ui(raw)
        tokens = extract_inline_tokens(root_expect_ui)
        props = extract_properties(root_expect_ui)
        case_id = extract_case_id(raw)
        all_positive_tokens = sorted(set(tokens["visible"] + tokens["enabled"] + list(props.keys()) + list(props.values())))
        negative_tokens = sorted(set(tokens["hidden"] + tokens["disabled"]))
        transition_selectors = []
        for ordinal, transition in enumerate(split_transition_blocks(raw), start=1):
            transition_tokens = extract_inline_tokens(transition["expectUi"])
            transition_props = extract_properties(transition["expectUi"])
            transition_selectors.append({
                "ordinal": ordinal,
                "event": transition["event"],
                "visible": transition_tokens["visible"],
                "hidden": transition_tokens["hidden"],
                "enabled": transition_tokens["enabled"],
                "disabled": transition_tokens["disabled"],
                "properties": transition_props,
                "traceMarker": f"strict_state_transition:{case_id}:{ordinal}",
            })
        cases.append({
            "caseId": case_id,
            "caseTitle": extract_case_title(raw),
            "line": line_no,
            "functionalArea": extract_scalar(raw, "functional_area"),
            "fixtureKind": extract_scalar(raw, "fixture_kind"),
            "transitionCount": extract_transition_count(raw),
            "selectors": {
                "visible": tokens["visible"],
                "hidden": tokens["hidden"],
                "enabled": tokens["enabled"],
                "disabled": tokens["disabled"],
                "properties": props,
            },
            "transitionSelectors": transition_selectors,
            "scoring": {
                "readyMarker": f"state_test_ready:{case_id}",
                "caseMarker": f"strict_state_case:{case_id}",
                "requiredPositiveSignals": all_positive_tokens,
                "forbiddenSignals": negative_tokens,
                "requiresPerCaseCapture": True,
                "requiresTransitionTrace": bool(transition_selectors),
                "featureAvailabilityIsSmokeOnly": True,
            },
        })
    return {
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "evaluatorOwned": True,
        "mustNotBeGeneratedByDevelopmentAgent": True,
        "sourceYaml": str(path),
        "task": task,
        "caseCount": len(cases),
        "cases": cases,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifests = []
    for path in sorted(STATE_TEST_DIR.glob("elementx-state-test*.yaml")):
        manifest = manifest_for(path)
        task_id = manifest["task"].get("id", path.stem)
        out_path = OUT_DIR / f"{task_id}.binding.json"
        out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifests.append({
            "taskId": task_id,
            "path": str(out_path),
            "caseCount": manifest["caseCount"],
        })
        print(f"Wrote {out_path}")

    index = {
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "evaluatorOwned": True,
        "mustNotBeGeneratedByDevelopmentAgent": True,
        "manifests": manifests,
    }
    index_path = OUT_DIR / "state_binding_manifest_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {index_path}")
    print(f"Cases: {sum(item['caseCount'] for item in manifests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
