#!/usr/bin/env python3
"""Preserve and summarize selected Element X Android reference tests."""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "_worktrees" / "element-x-android-v26.04.0"
OUTPUT = ROOT / "elementx_harmony_full" / "verification" / "android-reference-tests"
INVENTORY = ROOT / "elementx_harmony_full" / "verification" / "android-module-inventory.json"

TESTS = (
    ("authentication", "features/login/impl", "io.element.android.features.login.impl.screens.loginpassword.LoginPasswordPresenterTest"),
    ("room-list", "features/home/impl", "io.element.android.features.home.impl.roomlist.RoomListPresenterTest"),
    ("timeline", "features/messages/impl", "io.element.android.features.messages.impl.timeline.TimelineControllerTest"),
    ("session-verification", "features/verifysession/impl", "io.element.android.features.verifysession.impl.outgoing.OutgoingVerificationPresenterTest"),
    ("link-new-device", "features/linknewdevice/impl", "io.element.android.features.linknewdevice.impl.screens.root.LinkNewDeviceRootPresenterTest"),
    ("location", "features/location/impl", "io.element.android.features.location.impl.DefaultLocationServiceTest"),
    ("media-gallery", "libraries/mediaviewer/impl", "io.element.android.libraries.mediaviewer.impl.gallery.MediaGalleryPresenterTest"),
    ("room-details", "features/roomdetails/impl", "io.element.android.features.roomdetails.impl.RoomDetailsPresenterTest"),
    ("room-details-edit", "features/roomdetailsedit/impl", "io.element.android.features.roomdetailsedit.impl.RoomDetailsEditPresenterTest"),
    ("space", "features/space/impl", "io.element.android.features.space.impl.root.SpacePresenterTest"),
)


def xml_path(module: str, class_name: str) -> Path:
    return ANDROID / module / "build" / "test-results" / "testDebugUnitTest" / f"TEST-{class_name}.xml"


def main() -> int:
    xml_output = OUTPUT / "xml"
    xml_output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for domain, module, class_name in TESTS:
        source = xml_path(module, class_name)
        if not source.exists():
            missing.append(class_name)
            continue
        suite = ET.parse(source).getroot()
        target = xml_output / f"{domain}.xml"
        shutil.copy2(source, target)
        rows.append({
            "domain": domain,
            "module": module,
            "class": class_name,
            "tests": int(suite.attrib.get("tests", "0")),
            "failures": int(suite.attrib.get("failures", "0")),
            "errors": int(suite.attrib.get("errors", "0")),
            "skipped": int(suite.attrib.get("skipped", "0")),
            "time_seconds": float(suite.attrib.get("time", "0")),
            "evidence": str(target.relative_to(ROOT)),
        })

    inventory = json.loads(INVENTORY.read_text(encoding="utf-8")) if INVENTORY.exists() else {}
    totals = {
        key: sum(int(row[key]) for row in rows)
        for key in ("tests", "failures", "errors", "skipped")
    }
    status = "PASS" if not missing and totals["failures"] == 0 and totals["errors"] == 0 else "FAIL"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "platform": "android",
        "source_tag": inventory.get("android_tag"),
        "source_commit": inventory.get("android_commit"),
        "scope": "selected official reference tests for reconstructed domains",
        "test_classes": len(rows),
        "totals": totals,
        "missing": missing,
        "results": rows,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Android Reference Test Summary",
        "",
        f"- Status: **{status}**",
        f"- Source: `{report['source_tag']}` / `{report['source_commit']}`",
        f"- Test classes: {len(rows)}/{len(TESTS)}",
        f"- Test methods: {totals['tests']}",
        f"- Failures/errors/skipped: {totals['failures']}/{totals['errors']}/{totals['skipped']}",
        "",
        "| Domain | Tests | Failures | Errors | Skipped |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['domain']} | {row['tests']} | {row['failures']} | {row['errors']} | {row['skipped']} |"
        )
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "test_classes": len(rows), "totals": totals, "missing": missing}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
