"""Choose a task harness by loaded production runtime capability, never role."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import android_robolectric
from android_robolectric_ui_resources import compile_resources

ROOT = Path(__file__).resolve().parents[2]


def probe(task: str, source: Path, role: str, output: Path, timeout: float) -> dict:
    if task == "10_media_upload_quality":
        config_file = ROOT / "state_tests/runtime/android" / task / "android10_11_followup/rendered_final.config.json"
        entry = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/attachments/preview/AttachmentsPreviewState.kt"
        key = "task10_entry"
    elif task == "11_room_upgrade_navigation":
        config_file = ROOT / "state_tests/runtime/android" / task / "rendered/adapter.json"
        entry = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesState.kt"
        key = "task11_entry"
    else:
        raise ValueError("Unsupported runtime entry probe task")
    configuration = json.loads(config_file.read_text())
    configuration.update(scope="loaded_production_entry_capability", sourceClosure=True,
                         sources=[], entrypoints=[entry], testClass="runtime.ProductionEntryProbe",
                         keys=[key], scoringExclusions={}, evaluatorSources=[
                             str(Path(__file__).with_name("tasks10_11") / "ProductionEntryProbe.kt"),
                             str(ROOT / "state_tests/runtime/android/08_threads/robolectric/Anvil.kt")])
    output.parent.mkdir(parents=True, exist_ok=True)
    config_path = output.with_suffix(".config.json")
    config_path.write_text(json.dumps(configuration, indent=2)+"\n")
    previous_resources = android_robolectric.compile_resources
    try:
        android_robolectric.compile_resources = compile_resources
        result = android_robolectric.run_slice(task, role, source, config_path.parent,
                                               config_path, output, timeout)
    finally:
        android_robolectric.compile_resources = previous_resources
    rows = result.get("observations", [])
    if result.get("runtimeCompile", {}).get("status") != "passed" or len(rows) != 1 or rows[0].get("status") != "pass":
        raise RuntimeError("Common production runtime capability probe did not execute; no semantic failure assigned")
    capability = rows[0].get("observed", {}).get("fullFeatureEntry")
    if type(capability) is not bool or not result.get("provenance", {}).get("productionSources"):
        raise RuntimeError("Common runtime capability has no actual candidate evidence")
    return {"fullFeatureEntry": capability, "report": str(output),
            "scope": "runtime harness selection only; semantic verdict requires the actual production prefix"}
