#!/usr/bin/env python3
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(r"C:\Users\xiexi\qingyu")
ANDROID_REPO = ROOT / "_sources" / "element-x-android"
REPORT_DIR = ROOT / "verification_reports"


@dataclass(frozen=True)
class TaskSpec:
    directory: str
    task_family: str
    base_tag: str
    final_tag: str
    android_final_evidence: tuple[str, ...]
    android_base_absent_signals: tuple[str, ...]
    arkts_required_signals: tuple[str, ...]
    arkts_absent_signals: tuple[str, ...]
    arkts_function_symbols: tuple[str, ...]


TASKS = (
    TaskSpec(
        directory="01_user_status_base_26_07_0",
        task_family="User Status",
        base_tag="v26.07.0",
        final_tag="v26.08.4",
        android_final_evidence=(
            "features/preferences/impl/src/main/kotlin/io/element/android/features/preferences/impl/userstatus/UserStatusView.kt",
            "features/preferences/impl/src/main/kotlin/io/element/android/features/preferences/impl/userstatus/UserStatusPresenter.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/user/UserStatus.kt",
        ),
        android_base_absent_signals=("UserStatusView.kt", "UserStatusPresenter.kt", "enableAutomaticCallStatus"),
        arkts_required_signals=("SCENARIO_ID: string = \"user_status_base\"", "canSetUserStatus: false", "settings_user_status_absent"),
        arkts_absent_signals=("UserStatusPresenter", "enableAutomaticCallStatus", "setUserStatus("),
        arkts_function_symbols=(
            "PreferencesRootPresenterParity",
            "preferencesRootView()",
            "UserPreferences()",
            "ManageAccountSection()",
            "ManageAppSection()",
            "GeneralSection()",
            "Footer()",
            "userStatusInsertionPoint()",
            "handleEvent(event: PreferencesRootEvent)",
        ),
    ),
    TaskSpec(
        directory="02_gallery_messages_base_26_06_1",
        task_family="Gallery Messages",
        base_tag="v26.06.1",
        final_tag="v26.08.1",
        android_final_evidence=(
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/model/event/TimelineItemGalleryContent.kt",
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/event/TimelineItemGalleryContentProvider.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/media/GalleryItemInfo.kt",
        ),
        android_base_absent_signals=("TimelineItemGalleryContent.kt", "TimelineItemGalleryContentProvider.kt", "GalleryItemInfo.kt"),
        arkts_required_signals=("SCENARIO_ID: string = \"gallery_messages_base\"", "id: 'evt-gallery-fixture'", "kind: TimelineEventKind.Gallery", "supported: false"),
        arkts_absent_signals=("GalleryContentProvider", "GalleryViewer", "handleGalleryItemClick"),
        arkts_function_symbols=(
            "TimelineItemContentMessageFactoryParity",
            "create(content: ParityMessageContent)",
            "createTextMessage(content: ParityMessageContent)",
            "createImageMessage(content: ParityMessageContent)",
            "createUnsupportedGalleryFixture(content: ParityMessageContent)",
            "aspectRatioOf(width?: number, height?: number)",
            "canReact(content: ParityTimelineContent)",
            "isEdited(content: ParityTimelineContent)",
        ),
    ),
    TaskSpec(
        directory="03_active_call_timeline_base_26_07_1",
        task_family="Active Call Timeline Rendering",
        base_tag="v26.07.1",
        final_tag="v26.08.0",
        android_final_evidence=(
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/ActiveCallTimelineItemView.kt",
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/TimelineItemCallNotifyView.kt",
        ),
        android_base_absent_signals=("ActiveCallTimelineItemView.kt",),
        arkts_required_signals=("SCENARIO_ID: string = \"active_call_timeline_base\"", "id: 'evt-call-fixture'", "kind: TimelineEventKind.ActiveCall", "supported: false"),
        arkts_absent_signals=("ActiveCallTimelineItemView", "joinCall", "Join call"),
        arkts_function_symbols=(
            "TimelineItemCallNotifyParity",
            "TimelineItemCallNotifyViewModel(roomInfo: TimelineRoomInfoParity",
            "getTextRes(roomInfo: TimelineRoomInfoParity",
            "getIcon(roomInfo: TimelineRoomInfoParity",
            "supportsTimelineCard(): boolean",
            "activeCallFixtureContent(): ParityTimelineContent",
        ),
    ),
    TaskSpec(
        directory="04_live_location_base_26_04_0",
        task_family="Live Location Sharing",
        base_tag="v26.04.0",
        final_tag="v26.05.1",
        android_final_evidence=(
            "features/location/api/src/main/kotlin/io/element/android/features/location/api/live/ActiveLiveLocationShareManager.kt",
            "features/location/api/src/main/kotlin/io/element/android/features/location/api/LiveLocationSharingBanner.kt",
            "features/location/impl/src/main/kotlin/io/element/android/features/location/impl/live/service/LiveLocationSharingService.kt",
        ),
        android_base_absent_signals=("ActiveLiveLocationShareManager.kt", "LiveLocationSharingBanner.kt", "LiveLocationSharingService.kt"),
        arkts_required_signals=("SCENARIO_ID: string = \"live_location_base\"", "id: 'evt-live-location-fixture'", "kind: TimelineEventKind.LiveLocation", "supported: false"),
        arkts_absent_signals=("startLiveLocation", "stopLiveLocation", "LiveLocationSharingBanner"),
        arkts_function_symbols=(
            "ShareLocationPresenterParity",
            "present(): ShareLocationStateParity",
            "checkLocationConstraints(hasPermission: boolean, isLocationEnabled: boolean)",
            "handleEvent(event: ShareLocationEventParity)",
            "shareStaticLocation(event: ShareLocationEventParity)",
            "handleStartLiveLocationShare(durationMs: number)",
            "getTimeline(timelineMode: string)",
            "generateBody(uri: string)",
            "liveLocationDurations(): number[]",
        ),
    ),
    TaskSpec(
        directory="05_link_new_device_base_26_05_0",
        task_family="Link New Device Flow",
        base_tag="v26.05.0",
        final_tag="v26.08.2",
        android_final_evidence=(
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/screens/qrcode/ShowQrCodePresenter.kt",
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/screens/qrcode/ShowQrCodeState.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/linknewdevice/ContinuationMessageSender.kt",
        ),
        android_base_absent_signals=("ShowQrCodePresenter.kt", "ShowQrCodeState.kt", "ContinuationMessageSender.kt"),
        arkts_required_signals=("SCENARIO_ID: string = \"link_new_device_base\"", "Manual recovery key: available", "QR link placeholder: visible but non-rotating", "Owner verification: not available", "Timeout handling: not available"),
        arkts_absent_signals=("ShowQrCodePresenter", "ContinuationMessageSender", "setInterval", "setTimeout"),
        arkts_function_symbols=(
            "LinkNewDeviceRootPresenterParity",
            "present(canLinkNewDevice: boolean)",
            "handleEvent(event: LinkNewDeviceRootEventParity)",
            "linkMobileDevice(): string",
            "ShowQrCodeNodeParity",
            "ShowQrCodeView(qrCodeData: string)",
            "ScanQrCodePresenterParity",
            "LinkDeviceNumberParity",
            "createEmpty(size: number)",
            "fillWith(text: string)",
            "isComplete(): boolean",
        ),
    ),
)


def run(args: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def git(*args: str) -> str:
    return run(["git", "-C", str(ANDROID_REPO), *args])


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(haystack: str, needles: Iterable[str]) -> list[str]:
    return [needle for needle in needles if needle not in haystack]


def assert_absent(haystack: str, needles: Iterable[str]) -> list[str]:
    return [needle for needle in needles if needle in haystack]


def verify_task(task: TaskSpec) -> dict:
    base_dir = ROOT / task.directory
    contract_path = base_dir / "verification" / "behavior_contract.json"
    service_path = base_dir / "entry" / "src" / "main" / "ets" / "services" / "MockMatrixService.ets"
    page_path = base_dir / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets"
    build_profile_path = base_dir / "build-profile.json5"
    app_scope_path = base_dir / "AppScope" / "app.json5"
    parity_path = base_dir / "entry" / "src" / "main" / "ets" / "androidparity" / "FunctionLevelParity.ets"
    hap_path = base_dir / "entry" / "build" / "default" / "outputs" / "default" / "entry-default-unsigned.hap"

    git("rev-parse", "--verify", f"{task.base_tag}^{{commit}}")
    git("rev-parse", "--verify", f"{task.final_tag}^{{commit}}")

    diff_names = git("diff", "--name-only", f"{task.base_tag}..{task.final_tag}", "--")
    missing_android_evidence = assert_contains(diff_names, task.android_final_evidence)

    base_tree = git("ls-tree", "-r", "--name-only", task.base_tag)
    missing_from_base_failures = [signal for signal in task.android_base_absent_signals if signal in base_tree]

    contract = json.loads(read_text(contract_path))
    source = "\n".join([
        read_text(service_path),
        read_text(page_path),
        read_text(build_profile_path),
        read_text(app_scope_path),
        read_text(contract_path),
    ])
    parity_source = read_text(parity_path)

    missing_arkts = assert_contains(source, task.arkts_required_signals)
    leaked_arkts = assert_absent(source + "\n" + parity_source, task.arkts_absent_signals)
    missing_function_symbols = assert_contains(parity_source, task.arkts_function_symbols)
    missing_ui_alignment_panel = assert_contains(source, ("getFunctionLevelAlignmentRows()", "function_alignment_", "Function-level Android parity"))

    sdk_ok = all(
        signal in source
        for signal in (
            '"compileSdkVersion": 23',
            '"compatibleSdkVersion": 23',
            '"targetSdkVersion": 23',
            '"minAPIVersion": 23',
            '"targetAPIVersion": 23',
        )
    )
    contract_ok = (
        contract["task_family"] == task.task_family
        and contract["android_base_tag"] == task.base_tag
        and contract["android_final_tag"] == task.final_tag
        and contract["arkts_sdk"] == 23
    )

    failures = []
    failures.extend([f"Android final evidence missing from diff: {item}" for item in missing_android_evidence])
    failures.extend([f"Android base unexpectedly contains final signal: {item}" for item in missing_from_base_failures])
    failures.extend([f"ArkTS required signal missing: {item}" for item in missing_arkts])
    failures.extend([f"ArkTS final-only signal leaked into base: {item}" for item in leaked_arkts])
    failures.extend([f"ArkTS function-level parity symbol missing: {item}" for item in missing_function_symbols])
    failures.extend([f"ArkTS UI/viewmodel does not expose function-level parity: {item}" for item in missing_ui_alignment_panel])
    if not sdk_ok:
        failures.append("ArkTS SDK 23 settings are incomplete")
    if not contract_ok:
        failures.append("Behavior contract does not match manifest task metadata")
    if not hap_path.exists():
        failures.append("Compiled unsigned HAP is missing")

    return {
        "directory": task.directory,
        "task_family": task.task_family,
        "android_base_tag": task.base_tag,
        "android_final_tag": task.final_tag,
        "android_final_evidence": list(task.android_final_evidence),
        "arkts_required_signals": list(task.arkts_required_signals),
        "arkts_function_symbols": list(task.arkts_function_symbols),
        "sdk23": sdk_ok,
        "contract": contract_ok,
        "hap": str(hap_path),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Android ↔ ArkTS Equivalence Check",
        "",
        "Scope: static code-level validation that each ArkTS base preserves the Android base behavior surface for the selected benchmark task family, while keeping final-version behavior absent.",
        "",
        "| Base | Android range | Result | Key Android final evidence | ArkTS base checks | Function-level ArkTS symbols |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        evidence = "<br>".join(result["android_final_evidence"])
        arkts = "<br>".join(result["arkts_required_signals"])
        functions = "<br>".join(result["arkts_function_symbols"])
        lines.append(
            f"| `{result['directory']}` | `{result['android_base_tag']}..{result['android_final_tag']}` | "
            f"{result['status']} | {evidence} | {arkts} | {functions} |"
        )

    lines.extend(["", "## Notes", ""])
    lines.append("- Android evidence is checked by `git diff --name-only <base>..<final>` and `git ls-tree` against the official `element-hq/element-x-android` repository.")
    lines.append("- ArkTS evidence is checked from `MockMatrixService.ets`, `Index.ets`, `FunctionLevelParity.ets`, `build-profile.json5`, and `verification/behavior_contract.json`.")
    lines.append("- All checks require SDK 23 configuration and an existing `entry-default-unsigned.hap` build output.")
    lines.append("- This is behavior-surface equivalence for benchmark bases, not full Matrix Rust SDK parity or pixel-perfect UI equivalence.")

    failures = [result for result in results if result["failures"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for result in failures:
            lines.append(f"### {result['directory']}")
            for failure in result["failures"]:
                lines.append(f"- {failure}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not ANDROID_REPO.exists():
        raise SystemExit(f"Android repository is missing: {ANDROID_REPO}")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [verify_task(task) for task in TASKS]

    json_path = REPORT_DIR / "android_arkts_equivalence_report.json"
    md_path = REPORT_DIR / "android_arkts_equivalence_report.md"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(results), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for result in results:
        print(f"{result['status']}\t{result['directory']}\t{len(result['failures'])} failures")
    return 0 if all(result["status"] == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
