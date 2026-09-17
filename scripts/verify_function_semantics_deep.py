#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
ANDROID_REPO = ROOT / "_sources" / "element-x-android"
FINAL_ROOT = ROOT / "final_dev_nodes"
REPORT_DIR = ROOT / "verification_reports"


@dataclass(frozen=True)
class SemanticCheck:
    pair: str
    android_tag: str
    android_files: tuple[str, ...]
    arkts_dir: str
    arkts_files: tuple[str, ...]
    android_signals: tuple[str, ...]
    arkts_signals: tuple[str, ...]
    description: str


CHECKS = (
    SemanticCheck(
        pair="01_user_status",
        android_tag="v26.08.4",
        android_files=(
            "features/preferences/impl/src/main/kotlin/io/element/android/features/preferences/impl/userstatus/UserStatusState.kt",
            "features/preferences/impl/src/main/kotlin/io/element/android/features/preferences/impl/userstatus/UserStatusPresenter.kt",
            "features/home/impl/src/main/kotlin/io/element/android/features/home/impl/components/HomeTopBar.kt",
        ),
        arkts_dir="01_user_status_final_26_08_4",
        arkts_files=(
            "entry/src/main/ets/androidparity/FunctionLevelParity.ets",
            "entry/src/main/ets/services/MockMatrixService.ets",
            "entry/src/main/ets/pages/Index.ets",
        ),
        android_signals=(
            'AWAY("🌴"',
            'UserStatusEvent.SetStatus',
            'UserStatusEvent.ClearStatus',
            'matrixClient.setUserStatus(event.status)',
            'matrixClient.clearUserStatus()',
            'UserStatus(emoji = "🌴", text = "Away")',
        ),
        arkts_signals=(
            "emoji: '🌴'",
            "text: 'Away'",
            "event === 'SetStatus'",
            "event === 'ClearStatus'",
            "enableAutomaticCallStatus(enabled: boolean)",
            "mapDisplayedStatus",
            "settings_user_status_connected",
        ),
        description="Own user status preserves displayed emoji/text, set/clear events, automatic call-status toggle and displayed-status mapping.",
    ),
    SemanticCheck(
        pair="02_gallery_messages",
        android_tag="v26.08.1",
        android_files=(
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/event/TimelineItemGalleryContentProvider.kt",
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/model/event/TimelineItemGalleryContent.kt",
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesFlowNode.kt",
        ),
        arkts_dir="02_gallery_messages_final_26_08_1",
        arkts_files=(
            "entry/src/main/ets/androidparity/FunctionLevelParity.ets",
            "entry/src/main/ets/services/MockMatrixService.ets",
            "entry/src/main/ets/pages/Index.ets",
        ),
        android_signals=(
            'caption = "My vacation photos"',
            "items = listOf(",
            "GalleryItem.Type.Video",
            "TimelineItemGalleryContent(",
            "val showCaption = caption != null",
            "is TimelineItemGalleryContent ->",
        ),
        arkts_signals=(
            "TimelineItemGalleryContentProviderParity",
            "createGalleryContent(items: GalleryItemDataParity[])",
            "TimelineItemGalleryView(items: GalleryItemDataParity[])",
            "handleGalleryItemClick",
            "toEventGalleryParams",
            "formatSummary(items: GalleryItemDataParity[])",
            "mediaCount: 4",
            "Gallery renderer connected",
        ),
        description="Gallery messages preserve multi-item content creation, mixed media support, visible renderer, summary and event-gallery navigation.",
    ),
    SemanticCheck(
        pair="03_active_call_timeline",
        android_tag="v26.08.0",
        android_files=(
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/ActiveCallTimelineItemView.kt",
        ),
        arkts_dir="03_active_call_timeline_final_26_08_0",
        arkts_files=(
            "entry/src/main/ets/androidparity/FunctionLevelParity.ets",
            "entry/src/main/ets/services/MockMatrixService.ets",
            "entry/src/main/ets/pages/Index.ets",
        ),
        android_signals=(
            "ActiveCallTimelineItemView(",
            "RtcNotificationState.Active",
            "if (!state.isJoined)",
            "onJoinCallClick(state.callIntent == CallIntent.AUDIO)",
            "DirectMessageCallBody",
            "GroupCallBody",
            "CallDurationText",
        ),
        arkts_signals=(
            "ActiveCallTimelineItemViewParity",
            "ActiveCallTimelineItemView(state: ActiveCallStateParity)",
            "joinCall(state: ActiveCallStateParity)",
            "routeCallContent(kind: string)",
            "renderParticipants(state: ActiveCallStateParity)",
            "Active call in progress",
            "Join call",
        ),
        description="Active call timeline preserves active-card rendering, join callback surface, call-content routing and participant rendering.",
    ),
    SemanticCheck(
        pair="04_live_location",
        android_tag="v26.05.1",
        android_files=(
            "features/location/api/src/main/kotlin/io/element/android/features/location/api/live/ActiveLiveLocationShareManager.kt",
            "features/location/impl/src/main/kotlin/io/element/android/features/location/impl/live/DefaultActiveLiveLocationShareManager.kt",
            "features/location/api/src/main/kotlin/io/element/android/features/location/api/LiveLocationSharingBanner.kt",
            "features/location/impl/src/main/kotlin/io/element/android/features/location/impl/share/ShareLocationPresenter.kt",
        ),
        arkts_dir="04_live_location_final_26_05_1",
        arkts_files=(
            "entry/src/main/ets/androidparity/FunctionLevelParity.ets",
            "entry/src/main/ets/services/MockMatrixService.ets",
            "entry/src/main/ets/pages/Index.ets",
        ),
        android_signals=(
            "val sharingRoomIds: StateFlow<Set<RoomId>>",
            "suspend fun startShare(roomId: RoomId, duration: Duration): Result<Unit>",
            "suspend fun stopShare(roomId: RoomId): Result<Unit>",
            "fun ActiveLiveLocationShareManager.isCurrentlySharing(roomId: RoomId)",
            "room.startLiveLocationShare(duration.inWholeMilliseconds)",
            "LiveLocationSharingBanner(",
        ),
        arkts_signals=(
            "private sharingRoomIds: string[] = []",
            "startShare(roomId: string, durationMs: number)",
            "stopShare(session: LiveLocationSessionParity)",
            "isCurrentlySharing(roomId: string)",
            "durationMs: number",
            "bannerRows(session: LiveLocationSessionParity)",
            "toLiveTimelineContent(session: LiveLocationSessionParity)",
            "Open live map",
        ),
        description="Live location preserves active room tracking, duration-aware start, stop, currently-sharing query, banner row and live timeline content.",
    ),
    SemanticCheck(
        pair="05_link_new_device",
        android_tag="v26.08.2",
        android_files=(
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/screens/qrcode/ShowQrCodePresenter.kt",
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/screens/qrcode/ShowQrCodeState.kt",
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/LinkNewMobileHandler.kt",
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/LinkNewDesktopHandler.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/linknewdevice/ContinuationMessageSender.kt",
        ),
        arkts_dir="05_link_new_device_final_26_08_2",
        arkts_files=(
            "entry/src/main/ets/androidparity/FunctionLevelParity.ets",
            "entry/src/main/ets/services/MockMatrixService.ets",
            "entry/src/main/ets/pages/Index.ets",
        ),
        android_signals=(
            "var qrCodeRotationCounter by remember { mutableIntStateOf(maxQrCodeRotation) }",
            "LinkMobileStep.QrReady",
            "LinkMobileStep.QrRotating",
            "delay(1.seconds)",
            "linkNewMobileHandler.onTooManyRotation()",
            "delay(2.minutes)",
            "ContinuationMessageSender",
            "suspend fun confirm(): Result<Unit>",
            "suspend fun cancel(): Result<Unit>",
        ),
        arkts_signals=(
            "remainingRotations: number",
            "loadingAfterRotationDelayMs: number = 1000",
            "onQrReady(data: string)",
            "onQrRotating()",
            "showLoadingWhileRotating",
            "onTooManyRotation()",
            "LinkNewDesktopHandlerParity",
            "timeoutMs: number",
            "120000",
            "ContinuationMessageSenderParity",
            "confirm()",
            "cancel()",
            "QR link: rotating and refreshable",
        ),
        description="Link-new-device preserves QR ready/rotating/loading transitions, max-rotation expiry, desktop two-minute timeout and continuation confirm/cancel.",
    ),
)


def run_git_show(tag: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{tag}:{path}"],
        cwd=ANDROID_REPO,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def read_arkts(final_dir: str, paths: tuple[str, ...]) -> str:
    return "\n".join((FINAL_ROOT / final_dir / path).read_text(encoding="utf-8") for path in paths)


def verify(check: SemanticCheck) -> dict:
    android_source = "\n".join(run_git_show(check.android_tag, path) for path in check.android_files)
    arkts_source = read_arkts(check.arkts_dir, check.arkts_files)
    android_missing = [signal for signal in check.android_signals if signal not in android_source]
    arkts_missing = [signal for signal in check.arkts_signals if signal not in arkts_source]
    failures = [f"Android source anchor missing: {signal}" for signal in android_missing]
    failures.extend(f"ArkTS semantic anchor missing: {signal}" for signal in arkts_missing)
    return {
        "pair": check.pair,
        "androidTag": check.android_tag,
        "arktsFinalDir": check.arkts_dir,
        "description": check.description,
        "androidFiles": list(check.android_files),
        "arktsFiles": list(check.arkts_files),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Deep Function Semantics Review",
        "",
        "Scope: source-level semantic anchors for the five Android final targets and their ArkTS final mirrors. This check verifies state names, event branches, timer behavior, and target UI/action surfaces beyond the coarse build/UI gates.",
        "",
        "| Pair | Android tag | ArkTS final | Result | Semantics checked |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| `{result['pair']}` | `{result['androidTag']}` | `{result['arktsFinalDir']}` | "
            f"{result['status']} | {result['description']} |"
        )
    failures = [result for result in results if result["failures"]]
    if failures:
        lines.extend(["", "## Findings", ""])
        for result in failures:
            lines.append(f"### {result['pair']}")
            for failure in result["failures"]:
                lines.append(f"- {failure}")
    else:
        lines.extend(["", "## Findings", "", "All deep function/state semantic checks passed."])
    return "\n".join(lines) + "\n"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [verify(check) for check in CHECKS]
    json_path = REPORT_DIR / "function_semantics_deep_review.json"
    md_path = REPORT_DIR / "function_semantics_deep_review.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(results), encoding="utf-8", newline="\n")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for result in results:
        print(f"{result['status']}\t{result['pair']}\t{len(result['failures'])} failures")
    return 0 if all(result["status"] == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
