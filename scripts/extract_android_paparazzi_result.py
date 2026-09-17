#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
ANDROID_REPO = ROOT / "_sources" / "element-x-android"
RESULT_DIR = ANDROID_REPO / "tests" / "uitests" / "build" / "test-results" / "testDebugUnitTest"
FAILURE_DIR = ANDROID_REPO / "tests" / "uitests" / "build" / "paparazzi" / "failures" / "debug"
REPORT_DIR = ROOT / "verification_reports"

TARGETS = {
    "user_status": "UserStatusView",
    "gallery_messages": "TimelineItemGalleryView",
    "active_call_timeline": "ActiveCallTimelineItemView",
    "live_location_banner": "LiveLocationSharingBanner",
    "live_location_share": "ShareLocationView",
    "link_new_device_qr": "ShowQrCodeView",
}


def classify(test_name: str) -> str | None:
    for key, needle in TARGETS.items():
        if needle in test_name:
            return key
    return None


def parse_failure_message(message: str) -> dict:
    percent_match = re.search(r"Images differ \(by ([0-9.]+)%\)", message)
    delta_match = re.search(r"file://([^ \n]+delta-[^\n]+\.png)", message)
    current_match = re.search(r"Thumbnail for current rendering stored at file://([^\n]+\.png)", message)
    return {
        "differencePercent": float(percent_match.group(1)) if percent_match else None,
        "deltaImage": delta_match.group(1) if delta_match else None,
        "currentImage": current_match.group(1) if current_match else None,
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict]] = defaultdict(list)
    total_tests = 0
    total_failures = 0

    for xml_path in sorted(RESULT_DIR.glob("TEST-*.xml")):
        root = ET.parse(xml_path).getroot()
        total_tests += int(root.attrib.get("tests", "0"))
        total_failures += int(root.attrib.get("failures", "0"))
        shard = root.attrib.get("name", xml_path.stem)
        for testcase in root.findall("testcase"):
            name = testcase.attrib.get("name", "")
            target = classify(name)
            if target is None:
                continue
            failure = testcase.find("failure")
            item = {
                "shard": shard,
                "name": name,
                "status": "FAIL" if failure is not None else "PASS",
                "timeSeconds": float(testcase.attrib.get("time", "0") or 0),
            }
            if failure is not None:
                item.update(parse_failure_message(failure.attrib.get("message", "")))
            grouped[target].append(item)

    summary = []
    for key in TARGETS:
        items = grouped.get(key, [])
        failures = [item for item in items if item["status"] == "FAIL"]
        summary.append({
            "target": key,
            "previewNeedle": TARGETS[key],
            "total": len(items),
            "passed": len(items) - len(failures),
            "failed": len(failures),
            "failures": failures,
        })

    report = {
        "command": ":tests:uitests:verifyPaparazziDebug",
        "androidRepo": str(ANDROID_REPO),
        "resultDir": str(RESULT_DIR),
        "failureDir": str(FAILURE_DIR),
        "totalPaparazziTests": total_tests,
        "totalPaparazziFailures": total_failures,
        "targetSummary": summary,
    }

    json_path = REPORT_DIR / "android_paparazzi_target_report.json"
    md_path = REPORT_DIR / "android_paparazzi_target_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for row in summary:
        print(f"{row['target']}\t{row['passed']}/{row['total']} pass\t{row['failed']} failed")
    return 0


def render_markdown(report: dict) -> str:
    lines = [
        "# Android Paparazzi Target Report",
        "",
        "Scope: extraction of the target Android Compose previews from the full `:tests:uitests:verifyPaparazziDebug` run.",
        "",
        f"- Total Paparazzi tests: {report['totalPaparazziTests']}",
        f"- Total Paparazzi failures: {report['totalPaparazziFailures']}",
        f"- Result XML: `{report['resultDir']}`",
        f"- Failure PNG root: `{report['failureDir']}`",
        "",
        "| Target | Preview needle | Passed | Failed |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in report["targetSummary"]:
        lines.append(f"| `{row['target']}` | `{row['previewNeedle']}` | {row['passed']} / {row['total']} | {row['failed']} |")

    failing_rows = [row for row in report["targetSummary"] if row["failed"]]
    if failing_rows:
        lines.extend(["", "## Target Failures", ""])
        for row in failing_rows:
            lines.append(f"### {row['target']}")
            for failure in row["failures"][:12]:
                percent = failure.get("differencePercent")
                diff = f"{percent:.6f}%" if isinstance(percent, float) else "unknown difference"
                lines.append(f"- {failure['shard']} `{failure['name']}`: {diff}")
                if failure.get("deltaImage"):
                    lines.append(f"  delta: `{failure['deltaImage']}`")
                if failure.get("currentImage"):
                    lines.append(f"  current: `{failure['currentImage']}`")
    else:
        lines.extend(["", "## Target Failures", "", "No target preview failures were found."])

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- The Android UI rendering path is now runnable locally with JDK 21 and Android SDK environment variables.",
        "- The full repository Paparazzi gate is not green at the current checkout, so mirror validation should use target preview extraction instead of treating the whole repository result as the benchmark verdict.",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
