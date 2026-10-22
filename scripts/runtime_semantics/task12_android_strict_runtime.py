#!/usr/bin/env python3
"""Live source-parameterized Android strict runtime evaluator for Task12."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time

try:
    from . import android_robolectric
    from .android_robolectric_ui_resources import compile_resources
    from . import task12_13_formal_core as formal
    from . import task12_13_runtime_support as support
    from . import task12_live_entry_validation as entry_validation
    from .task12_13_android_slice import run_slice
    from .task14_15_formal_core import bounded_file_lock, filesystem_closure
except ImportError:
    import android_robolectric
    from android_robolectric_ui_resources import compile_resources
    import task12_13_formal_core as formal
    import task12_13_runtime_support as support
    import task12_live_entry_validation as entry_validation
    from task12_13_android_slice import run_slice
    from task14_15_formal_core import bounded_file_lock, filesystem_closure


ROOT = formal.ROOT
TASK_ID = "12_report_room"
BASE_ASSETS = ROOT / "state_tests/runtime/android/12_report_room/action_prefix"
FINAL_ASSETS = ROOT / "state_tests/runtime/android/12_report_room/action_prefix_final_25_05_4"
TEMPLATE = ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task12-entry/base-v2.config.json"
CONTRACT = ROOT / "experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/12_report_room/transitions.json"
ONBOARDING = "appconfig/src/main/kotlin/io/element/android/appconfig/OnBoardingConfig.kt"


def _base_config(source: Path, keys: list[str]) -> dict:
    config = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    config.update(
        scope="base_independent_action_prefix_entries",
        sourceClosure=False,
        testClass="runtime.RoomDetailsActionPrefixTest",
        keys=keys,
        evaluatorSources=[
            str(BASE_ASSETS / "RoomDetailsActionPrefixTest.kt"),
            str(ROOT / "state_tests/runtime/android/common/Anvil.kt"),
        ],
    )
    config["entrypoints"] += [
        "features/roomdetails/impl/src/main/kotlin/io/element/android/features/roomdetails/impl/RoomDetailsPresenter.kt",
        "features/leaveroom/impl/src/main/kotlin/io/element/android/features/leaveroom/impl/LeaveRoomPresenter.kt",
        "features/roomcall/impl/src/main/kotlin/io/element/android/features/roomcall/impl/RoomCallStatePresenter.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/DefaultIsPinnedMessagesFeatureEnabled.kt",
    ]
    config["sources"] = filesystem_closure(source, config["entrypoints"])
    if (source / ONBOARDING).is_file() and ONBOARDING not in config["sources"]:
        config["sources"].append(ONBOARDING)
    return config


def _final_config(source: Path, keys: list[str]) -> dict:
    config = json.loads(
        (ROOT / "experiment_results/runtime_transition_20261020/task12_prefix/android-final-25_05_4-v3.config.json")
        .read_text(encoding="utf-8")
    )
    config.update(
        sourceClosure=False,
        keys=keys,
        evaluatorSources=[str(FINAL_ASSETS / "ReportRoomActionPrefixFinalTest.kt")],
    )
    config["sources"] = filesystem_closure(source, config["entrypoints"])
    catalog_path = source / "gradle/libs.versions.toml"
    try:
        import tomllib
        catalog = tomllib.loads(catalog_path.read_text())
    except ImportError:
        catalog = json.loads(subprocess.check_output([
            "/opt/homebrew/bin/python3", "-c",
            "import json,sys,tomllib;json.dump(tomllib.loads(sys.stdin.read()),sys.stdout)",
        ], input=catalog_path.read_bytes(), timeout=10))
    coroutines = catalog["versions"]["coroutines"]
    config["alignedGroups"] = [item for item in config.get("alignedGroups", [])
                               if item[0] != "org.jetbrains.kotlinx"] + [["org.jetbrains.kotlinx", coroutines]]
    return config


def _common_config(source: Path, keys: list[str], evidence: Path) -> dict:
    config = _base_config(source, keys)
    fixture = (BASE_ASSETS / "RoomDetailsActionPrefixTest.kt").read_text()
    before = """            try { compose.onNode(reportMatcher and hasClickAction()).performClick() }
            catch (failure: AssertionError) { attemptError = failure.message }
            check(reportCount == 0 && attemptError != null) { "New entry behavior requires separate review" }"""
    after = """            if (reportCount == 0) {
                try { compose.onNode(reportMatcher and hasClickAction()).performClick() }
                catch (failure: AssertionError) { attemptError = failure.message }
                check(attemptError != null) { "Missing entry did not produce a real UI attempt" }
            } else {
                check(reportCount == 1) { "Ambiguous production report entry" }
                compose.onNode(reportMatcher and hasClickAction()).assertIsDisplayed().assertIsEnabled()
            }"""
    if fixture.count(before) != 1:
        raise ValueError("Task12 common Android entry fixture shape changed")
    fixture = fixture.replace(before, after)
    # SDK API binding only; the verdict is obtained later from executed UI evidence.
    if any(path.endswith("/JoinedRoom.kt") for path in config["sources"]):
        for old, new in (("MatrixRoomMembersState", "RoomMembersState"),
                         ("MatrixRoomInfo", "RoomInfo"),
                         ("MatrixRoomNotificationSettingsState", "RoomNotificationSettingsState")):
            fixture = re.sub(r"\b" + old + r"\b", new, fixture)
        fixture = fixture.replace("isTombstoned = false", "tombstone = null")
        fixture = fixture.replace("): MatrixRoom {", "): JoinedRoom {").replace("port<MatrixRoom>", "port<JoinedRoom>")
        fixture = fixture.replace('name.startsWith("getRoom-") || name == "getRoom" -> {',
                                  'name == "canReportRoom" -> true\n                name.startsWith("getRoom-") || name == "getRoom" -> {')
    view = source / "features/roomdetails/impl/src/main/kotlin/io/element/android/features/roomdetails/impl/RoomDetailsView.kt"
    if "onReportRoomClick: () -> Unit" in view.read_text():
        fixture = fixture.replace('onProfileClick = { error("Unexpected profile") })',
                                  'onProfileClick = { error("Unexpected profile") }, onReportRoomClick = { error("Common entry must not skip route test") })')
        fixture = fixture.replace("io.element.android.features.roomdetails.impl.R.string.screen_room_details_leave_room_title",
                                  "CommonStrings.action_leave_room")
    path = evidence / "Task12CommonEntryProbeTest.kt"
    path.write_text(fixture)
    config["evaluatorSources"][0] = str(path)
    return config


def evaluate(*, task, platform: str, source: Path, role: str, output: Path,
             deadline: float, device_serial: str | None = None) -> dict:
    del device_serial
    if platform != "android":
        raise ValueError("Task12 Android evaluator received another platform")
    source = source.resolve()
    if not (source / "gradlew").is_file():
        raise ValueError("Task12 runtime requires a materialized standalone source; ref reconstruction is forbidden")
    contract = formal.load(task.contract)
    evidence = output.with_suffix(".android-evidence")
    evidence.mkdir(parents=True, exist_ok=False)
    config = _common_config(source, [case["key"] for case in contract["cases"]], evidence)
    config_path = evidence / "runtime.config.json"
    formal.write(config_path, config)
    raw_path = evidence / "runtime.raw.json"
    original_prepare = android_robolectric.prepare
    original_resources = android_robolectric.compile_resources

    def prepare(configuration, work):
        environment = original_prepare(configuration, work)
        environment["jvmArgs"] += [
            f"-Druntime.contract.path={task.contract}",
            f"-Druntime.rendered.output={evidence / 'rendered'}",
        ]
        return environment

    android_robolectric.prepare = prepare
    android_robolectric.compile_resources = compile_resources
    try:
        with bounded_file_lock(
            ROOT / "state_tests/runtime/android/.build.lock", deadline,
            "Task12 Android exact runtime lock",
        ):
            raw = run_slice(
                TASK_ID, role, source, BASE_ASSETS,
                config_path, raw_path, deadline,
            )
            if raw.get("runtimeCompile", {}).get("status") != "passed":
                raise RuntimeError(f"Task12 common-entry evaluator compile failed: {raw.get('error')}")
            observations = raw.get("observations", [])
            missing = len(observations) == 10 and all(row.get("status") == "fail" and
                      row.get("observed", {}).get("reportControlCount") == 0 for row in observations)
            available = len(observations) == 10 and all(row.get("status") == "pass" and
                        row.get("observed", {}).get("reportControlCount") == 1 for row in observations)
            common_path = raw_path
            if available:
                config_path = evidence / "final.config.json"
                formal.write(config_path, _final_config(source, [case["key"] for case in contract["cases"]]))
                raw_path = evidence / "final.raw.json"
                raw = run_slice(
                    TASK_ID, role, source, FINAL_ASSETS, config_path, raw_path,
                    deadline)
            elif not missing:
                raise RuntimeError("Task12 common production UI prefix incomplete or inconsistent")
    finally:
        android_robolectric.prepare = original_prepare
        android_robolectric.compile_resources = original_resources
    compile_status = raw.get("runtimeCompile", {}).get("status")
    if compile_status != "passed":
        raise RuntimeError(f"Task12 Android evaluator compile failed: {raw.get('error')}")
    if missing:
        rows = entry_validation.entry_rows(contract, raw, raw_path, "android")
    else:
        rows = support.canonical_rows(contract, raw.get("observations", []), role=role)
    lineage = formal.calibrator_lineage(task, "android")
    return support.strict_report(
        task=task, platform="android", source=source, role=role, rows=rows,
        runtime_compile={"passed": True, "status": "passed",
                         "command": raw.get("runtimeCompile", {}).get("command")},
        lineage=lineage, runtime_kind="android robolectric original production compose and appyx",
        transport="host_runtime_completed",
        evidence={"raw": formal.file_record(raw_path), "configuration": formal.file_record(config_path),
                  "commonEntry": formal.file_record(common_path)},
        output=output,
    )


def main() -> int:
    args = support.parse_args(__doc__ or "Task12 Android strict runtime")
    try:
        from .task12_formal_agent import SPEC
    except ImportError:
        from task12_formal_agent import SPEC
    deadline = time.monotonic() + args.deadline_seconds
    report = evaluate(task=SPEC, platform="android", source=args.source, role=args.role,
                      output=args.output, deadline=deadline)
    print(json.dumps({"output": str(args.output), "semantic": report["semantic"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
