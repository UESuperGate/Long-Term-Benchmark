#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
UI_ROOT = ROOT / "verification_reports" / "harmony_dynamic_ui"
REPORT_DIR = ROOT / "verification_reports"


@dataclass(frozen=True)
class UiExpectation:
    project: str
    kind: str
    file: str
    contains: tuple[str, ...]


EXPECTATIONS = (
    UiExpectation(
        "01_user_status_base_26_07_0",
        "base",
        "settings.ui.md",
        ("User status", "Not available in this base"),
    ),
    UiExpectation(
        "01_user_status_base_26_07_0",
        "base",
        "contract.ui.md",
        ("PreferencesRootPresenterParity.userStatusInsertionPoint()", "keeps the reserved point but returns no user-status row"),
    ),
    UiExpectation(
        "01_user_status_final_26_08_4",
        "final",
        "settings.ui.md",
        ("User status", "🌴 Away - editable"),
    ),
    UiExpectation(
        "01_user_status_final_26_08_4",
        "final",
        "contract.ui.md",
        ("UserStatusPresenterParity.present()", "enableAutomaticCallStatus", "mapDisplayedStatus"),
    ),
    UiExpectation(
        "02_gallery_messages_base_26_06_1",
        "base",
        "timeline.ui.md",
        ("Gallery message fixture: unsupported in this base", "Unsupported in this base"),
    ),
    UiExpectation(
        "02_gallery_messages_final_26_08_1",
        "final",
        "timeline.ui.md",
        ("Gallery message: four attachments", "Gallery renderer connected"),
    ),
    UiExpectation(
        "02_gallery_messages_final_26_08_1",
        "final",
        "contract.ui.md",
        ("TimelineItemGalleryContentProviderParity.createGalleryContent()", "TimelineItemGalleryView"),
    ),
    UiExpectation(
        "03_active_call_timeline_base_26_07_1",
        "base",
        "timeline.ui.md",
        ("Active call fixture: unsupported timeline item in this base", "Unsupported in this base"),
    ),
    UiExpectation(
        "03_active_call_timeline_final_26_08_0",
        "final",
        "timeline.ui.md",
        ("Active call in progress", "Join call"),
    ),
    UiExpectation(
        "03_active_call_timeline_final_26_08_0",
        "final",
        "contract.ui.md",
        ("ActiveCallTimelineItemViewParity", "joinCall", "renderParticipants"),
    ),
    UiExpectation(
        "04_live_location_base_26_04_0",
        "base",
        "timeline.ui.md",
        ("Live location fixture: unsupported in this base", "Unsupported in this base"),
    ),
    UiExpectation(
        "04_live_location_final_26_05_1",
        "final",
        "timeline.ui.md",
        ("Live location sharing active", "Open live map"),
    ),
    UiExpectation(
        "04_live_location_final_26_05_1",
        "final",
        "contract.ui.md",
        ("ActiveLiveLocationShareManagerParity.startShare()", "ActiveLiveLocationShareManagerParity.stopShare()", "ActiveLiveLocationShareManagerParity.isCurrentlySharing()", "toLiveTimelineContent"),
    ),
    UiExpectation(
        "05_link_new_device_base_26_05_0",
        "base",
        "security.ui.md",
        ("QR link placeholder: visible but non-rotating", "Owner verification: not available", "Timeout handling: not available"),
    ),
    UiExpectation(
        "05_link_new_device_final_26_08_2",
        "final",
        "security.ui.md",
        ("QR link: rotating and refreshable", "Owner verification: available", "Timeout handling: available"),
    ),
    UiExpectation(
        "05_link_new_device_final_26_08_2",
        "final",
        "contract.ui.md",
        ("ShowQrCodePresenterParity.onQrRotating()", "ContinuationMessageSenderParity.confirm()/cancel()", "LinkNewDesktopHandlerParity.startTimer()", "LinkNewDesktopHandlerParity.timeoutError()"),
    ),
)


def verify(expectation: UiExpectation) -> dict:
    path = UI_ROOT / expectation.project / expectation.file
    failures: list[str] = []
    if not path.exists():
        failures.append(f"Missing UI capture: {path}")
        text = ""
    else:
        text = path.read_text(encoding="utf-8")

    for signal in expectation.contains:
        if signal not in text:
            failures.append(f"Missing UI signal in {expectation.file}: {signal}")

    return {
        "project": expectation.project,
        "kind": expectation.kind,
        "file": expectation.file,
        "requiredSignals": list(expectation.contains),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Harmony Dynamic UI Verification",
        "",
        "Scope: runtime UI-tree checks for the five ArkTS base-final mirror pairs on the Harmony emulator. Each check is backed by captured `uiLayout` output from an installed HAP.",
        "",
        "| Project | Kind | UI capture | Result | Required signals |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        signals = "<br>".join(result["requiredSignals"])
        lines.append(f"| `{result['project']}` | {result['kind']} | `{result['file']}` | {result['status']} | {signals} |")

    failures = [result for result in results if result["failures"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for result in failures:
            lines.append(f"### {result['project']} / {result['file']}")
            for failure in result["failures"]:
                lines.append(f"- {failure}")
    else:
        lines.extend(["", "## Findings", "", "All captured Harmony UI-tree checks passed."])

    lines.extend([
        "",
        "## Evidence",
        "",
        f"- Capture manifest: `{UI_ROOT / 'manifest.json'}`",
        f"- Capture root: `{UI_ROOT}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [verify(expectation) for expectation in EXPECTATIONS]
    json_path = REPORT_DIR / "harmony_dynamic_ui_report.json"
    md_path = REPORT_DIR / "harmony_dynamic_ui_report.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(results), encoding="utf-8", newline="\n")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for result in results:
        print(f"{result['status']}\t{result['project']}\t{result['file']}")
    return 0 if all(result["status"] == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
