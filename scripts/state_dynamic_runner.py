#!/usr/bin/env python3
"""
Build a runnable catalog for Element X state-test dynamic execution.

The production state-test YAML files are intentionally formatted so this parser
can stay dependency-free on the Windows host. It extracts the test identity,
case list, functional areas, fixture kinds, and binding-manifest locations,
then writes a readiness report that the PowerShell device runner can consume.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", r"C:\Users\xiexi\qingyu"))
STATE_TEST_DIR = ROOT / "state_tests"
REPORT_DIR = Path(os.environ.get("QINGYU_STATE_REPORT_DIR", str(ROOT / "verification_reports" / "state_dynamic")))
BINDING_DIR = Path(os.environ.get("QINGYU_BINDING_MANIFEST_DIR", str(STATE_TEST_DIR / "bindings")))


@dataclass
class StateCase:
    task_id: str
    task_title: str
    base: str
    final: str
    case_id: str
    case_title: str
    functional_area: str
    fixture_kind: str


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def parse_state_test(path: Path) -> list[StateCase]:
    task_id = ""
    task_title = ""
    base = ""
    final = ""
    cases: list[StateCase] = []
    current_case_id = ""
    current_case_title = ""
    current_functional_area = ""
    current_fixture_kind = ""
    in_cases = False

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "cases:":
            in_cases = True
            continue

        if not in_cases:
            if stripped.startswith("id:") and raw_line.startswith("  "):
                task_id = unquote(stripped.split(":", 1)[1])
            elif stripped.startswith("title:") and raw_line.startswith("  "):
                task_title = unquote(stripped.split(":", 1)[1])
            elif stripped.startswith("base:"):
                base = unquote(stripped.split(":", 1)[1])
            elif stripped.startswith("final:"):
                final = unquote(stripped.split(":", 1)[1])
            continue

        if line.startswith("  - id:"):
            if current_case_id:
                cases.append(StateCase(task_id, task_title, base, final, current_case_id, current_case_title, current_functional_area, current_fixture_kind))
            current_case_id = unquote(stripped.split(":", 1)[1])
            current_case_title = ""
            current_functional_area = ""
            current_fixture_kind = ""
        elif current_case_id and line.startswith("    title:"):
            current_case_title = unquote(stripped.split(":", 1)[1])
        elif current_case_id and line.startswith("    functional_area:"):
            current_functional_area = unquote(stripped.split(":", 1)[1])
        elif current_case_id and line.startswith("    fixture_kind:"):
            current_fixture_kind = unquote(stripped.split(":", 1)[1])

    if current_case_id:
        cases.append(StateCase(task_id, task_title, base, final, current_case_id, current_case_title, current_functional_area, current_fixture_kind))

    return cases


def iter_cases() -> Iterable[StateCase]:
    for path in sorted(STATE_TEST_DIR.glob("elementx-state-test*.yaml")):
        yield from parse_state_test(path)


def readiness_for_case(case: StateCase) -> dict:
    binding_path = BINDING_DIR / f"{case.task_id}.binding.json"
    return {
        "taskId": case.task_id,
        "taskTitle": case.task_title,
        "base": case.base,
        "final": case.final,
        "caseId": case.case_id,
        "caseTitle": case.case_title,
        "functionalArea": case.functional_area,
        "fixtureKind": case.fixture_kind,
        "dynamicStrategy": "fixture_state_injection",
        "requiresStateInjection": True,
        "android": {
            "runTarget": "debug APK plus Android instrumentation/state-fixture adapter",
            "status": "needs_adapter",
            "reason": "The unmodified Android app exposes real deeplink/share entrypoints, but not an arbitrary declarative state-test injection endpoint.",
        },
        "arkts": {
            "runTarget": "HAP plus Want/deeplink state-test adapter",
            "status": "needs_adapter",
            "reason": "LaunchIntentStore already captures Want data, but Index.ets does not yet map a stateTestCaseId to the semantic state vector.",
        },
        "assertionArtifacts": {
            "android": ["uiautomator XML", "screenshot PNG", "logcat excerpt"],
            "arkts": ["ArkUI uiLayout analysis.md", "screenshot JPEG", "hilog excerpt"],
        },
        "bindingManifest": str(binding_path),
    }


def build_report() -> dict:
    cases = list(iter_cases())
    by_task: dict[str, int] = {}
    for case in cases:
        by_task[case.task_id] = by_task.get(case.task_id, 0) + 1
    by_area: dict[str, dict[str, int]] = {}
    by_fixture: dict[str, dict[str, int]] = {}
    for case in cases:
        area_counts = by_area.setdefault(case.task_id, {})
        area = case.functional_area or "missing"
        area_counts[area] = area_counts.get(area, 0) + 1
        fixture_counts = by_fixture.setdefault(case.task_id, {})
        fixture = case.fixture_kind or "missing"
        fixture_counts[fixture] = fixture_counts.get(fixture, 0) + 1

    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "summary": {
            "totalCases": len(cases),
            "casesByTask": by_task,
            "casesByFunctionalArea": by_area,
            "casesByFixtureKind": by_fixture,
            "androidSourcePolicy": "do not modify production Android source; use generated/external test adapter or throwaway test branch only",
            "primarySignal": "semantic UI tree assertions; screenshots are secondary evidence",
            "polarity": {
                "androidBase": "expected_fail",
                "arktsBase": "expected_fail",
                "androidFinal": "expected_pass",
                "arktsFinal": "expected_pass",
            },
        },
        "requiredAdapters": {
            "android": [
                "A debug/instrumentation-only state fixture entrypoint that accepts stateTestCaseId and applies evaluator-provided state vectors.",
                "Evaluator-generated binding manifests under state_tests/bindings map YAML semantic tokens to Compose semantics text/testTag/contentDescription.",
                "A transition executor that invokes the event sink or fake SDK callback named in the YAML without embedding pass/fail answers in the app.",
            ],
            "arkts": [
                "Extend LaunchIntentPayload with stateTestCaseId or stateTestPayload.",
                "In Index.ets, consume the id and apply the matching fixture ClientSnapshot/@State values.",
                "Expose stable ArkUI ids/text for semantic assertions and transition results.",
            ],
        },
        "executionFlow": [
            "Install Android APK and ArkTS HAP for the matching base/final node.",
            "Launch app with the same stateTestCaseId on both platforms.",
            "Wait for the state-test-ready semantic marker.",
            "Capture Android uiautomator XML + screenshot and ArkTS uiLayout + screenshot.",
            "Assert visible/hidden/enabled/disabled/properties using evaluator-owned binding manifests generated from YAML.",
            "Execute transitions and recapture after each transition.",
            "Merge both platform results by caseId into one JSON/Markdown report.",
        ],
        "cases": [readiness_for_case(case) for case in cases],
    }


def write_markdown(report: dict, path: Path) -> None:
    lines: list[str] = []
    lines.append("# State Dynamic Execution Plan")
    lines.append("")
    lines.append(f"- Generated: {report['generatedAt']}")
    lines.append(f"- Total cases: {report['summary']['totalCases']}")
    lines.append(f"- Android source policy: {report['summary']['androidSourcePolicy']}")
    lines.append(f"- Primary signal: {report['summary']['primarySignal']}")
    lines.append("- Expected polarity: Android base fail; ArkTS base fail; Android final pass; ArkTS final pass")
    lines.append("")
    lines.append("## Readiness")
    lines.append("")
    lines.append("Current state-test specs are ready as semantic input, but full app-dynamic execution needs one test adapter per platform.")
    lines.append("Without those adapters, black-box adb/hdc scripts can only verify naturally reachable screens and will not cover SDK failure callbacks, timers, base/final capability gap states, or synthetic timeline/media states.")
    lines.append("Binding manifests are generated by `scripts/generate_state_binding_manifests.py`; development agents must not generate or modify them during a benchmark run.")
    lines.append("")
    lines.append("## Required Adapters")
    lines.append("")
    lines.append("### Android")
    for item in report["requiredAdapters"]["android"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### ArkTS")
    for item in report["requiredAdapters"]["arkts"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Execution Flow")
    for index, item in enumerate(report["executionFlow"], start=1):
        lines.append(f"{index}. {item}")
    lines.append("")
    lines.append("## Case Counts")
    for task_id, count in report["summary"]["casesByTask"].items():
        lines.append(f"- `{task_id}`: {count}")
    lines.append("")
    lines.append("## Functional Area Counts")
    for task_id, counts in report["summary"]["casesByFunctionalArea"].items():
        rendered = ", ".join(f"{area}={count}" for area, count in sorted(counts.items()))
        lines.append(f"- `{task_id}`: {rendered}")
    lines.append("")
    lines.append("## Fixture Kind Counts")
    for task_id, counts in report["summary"]["casesByFixtureKind"].items():
        rendered = ", ".join(f"{fixture}={count}" for fixture, count in sorted(counts.items()))
        lines.append(f"- `{task_id}`: {rendered}")
    lines.append("")
    lines.append("## Command Shape")
    lines.append("")
    lines.append("Android, after adapter exists:")
    lines.append("")
    lines.append("```powershell")
    lines.append(r"& C:\Users\xiexi\AppData\Local\Android\Sdk\platform-tools\adb.exe install -r <android-debug.apk>")
    lines.append(r"& C:\Users\xiexi\AppData\Local\Android\Sdk\platform-tools\adb.exe shell am start -a android.intent.action.VIEW -d ""elementx://state-test?caseId=<case_id>"" io.element.android.x.debug")
    lines.append(r"& C:\Users\xiexi\AppData\Local\Android\Sdk\platform-tools\adb.exe shell uiautomator dump /sdcard/state-test.xml")
    lines.append("```")
    lines.append("")
    lines.append("ArkTS, after adapter exists:")
    lines.append("")
    lines.append("```powershell")
    lines.append(r"& C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23\toolchains\hdc.exe install -r <entry-default-unsigned.hap>")
    lines.append(r"& C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23\toolchains\hdc.exe shell aa start -b <bundle> -a EntryAbility -U ""elementx://state-test?caseId=<case_id>""")
    lines.append(r"& 'C:\Program Files\Huawei\DevEco Studio\tools\emulator\Emulator.exe' -instance ""Pura 90 Pro Max"" -uiLayout -a")
    lines.append("```")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(REPORT_DIR / "state_dynamic_execution_plan.json"))
    parser.add_argument("--markdown", default=str(REPORT_DIR / "state_dynamic_execution_plan.md"))
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
