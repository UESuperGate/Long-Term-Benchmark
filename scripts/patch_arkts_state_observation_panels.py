#!/usr/bin/env python3
"""
Replace legacy ArkTS feature-availability assertion panels with observation-only
state-test panels in the five benchmark base and golden final projects.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
MANIFEST = ROOT / "manifest.json"
FINAL_ROOT = ROOT / "final_dev_nodes"
TASK_IDS = [
    "01_user_status",
    "02_gallery_messages",
    "03_timeline_protection_rich_events",
    "04_live_location",
    "05_link_new_device",
]


OLD = """      Text(`strict_state_assertion:final_feature_available:observed=${this.stateTestFeatureEnabled()}`)
        .fontSize(12)
        .fontWeight(FontWeight.Medium)
        .fontColor(this.stateTestFeatureEnabled() ? '#166534' : '#991B1B')
        .id('strict_state_assertion')"""

NEW = """      Text('strict_state_observed:adapter=arkts_state_observation_only')
        .fontSize(11)
        .fontColor('#334155')
        .id('strict_state_observed_adapter')
      Text('strict_state_binding:per_case_ui_tokens_required')
        .fontSize(12)
        .fontWeight(FontWeight.Medium)
        .fontColor('#334155')
        .id('strict_state_binding_required')"""


def final_dir_for(base_dir: str, final_tag: str) -> str:
    prefix = base_dir.split("_base_", 1)[0]
    version = final_tag.removeprefix("v").replace(".", "_")
    return f"{prefix}_final_{version}"


def project_dirs() -> list[Path]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    dirs: list[Path] = []
    for item in manifest["bases"]:
        dirs.append(ROOT / item["directory"])
        dirs.append(FINAL_ROOT / final_dir_for(item["directory"], item["android_final_tag"]))
    return dirs


def patch_index(path: Path) -> bool:
    text = path.read_text(encoding="utf-8-sig")
    updated = text.replace(OLD, NEW)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    patched = []
    skipped = []
    for project in project_dirs():
        index = project / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets"
        if not index.exists():
            skipped.append(str(index))
            continue
        if patch_index(index):
            patched.append(str(index))
    print(f"Patched ArkTS panels: {len(patched)}")
    for item in patched:
        print(item)
    if skipped:
        print(f"Skipped missing Index.ets files: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
