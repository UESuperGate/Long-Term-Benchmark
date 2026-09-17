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
class FinalSpec:
    directory: str
    base_tag: str
    final_tag: str
    scenario: str
    flag: str
    android_evidence: tuple[str, ...]
    arkts_evidence: tuple[str, ...]
    ui_evidence: tuple[str, ...]


FINALS = (
    FinalSpec(
        directory="01_user_status_final_26_08_4",
        base_tag="v26.07.0",
        final_tag="v26.08.4",
        scenario="user_status_final",
        flag="userStatus: true",
        android_evidence=(
            "features/preferences/impl/src/main/kotlin/io/element/android/features/preferences/impl/userstatus/UserStatusView.kt",
            "features/preferences/impl/src/main/kotlin/io/element/android/features/preferences/impl/userstatus/UserStatusPresenter.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/user/UserStatus.kt",
        ),
        arkts_evidence=("UserStatusPresenterParity", "emoji: '🌴'", "UserStatusView()", "enableAutomaticCallStatus(enabled: boolean)", "mapDisplayedStatus"),
        ui_evidence=("settings_user_status_connected",),
    ),
    FinalSpec(
        directory="02_gallery_messages_final_26_08_1",
        base_tag="v26.06.1",
        final_tag="v26.08.1",
        scenario="gallery_messages_final",
        flag="galleryMessages: true",
        android_evidence=(
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/model/event/TimelineItemGalleryContent.kt",
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/event/TimelineItemGalleryContentProvider.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/media/GalleryItemInfo.kt",
        ),
        arkts_evidence=("TimelineItemGalleryContentProviderParity", "createGalleryContent", "TimelineItemGalleryView", "handleGalleryItemClick", "toEventGalleryParams"),
        ui_evidence=("gallery_connected_evt-gallery-fixture", "supported: true"),
    ),
    FinalSpec(
        directory="03_active_call_timeline_final_26_08_0",
        base_tag="v26.07.1",
        final_tag="v26.08.0",
        scenario="active_call_timeline_final",
        flag="activeCallTimeline: true",
        android_evidence=(
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/ActiveCallTimelineItemView.kt",
            "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/timeline/components/TimelineItemCallNotifyView.kt",
        ),
        arkts_evidence=("ActiveCallTimelineItemViewParity", "joinCall", "routeCallContent", "renderParticipants"),
        ui_evidence=("join_call_evt-call-fixture", "supported: true"),
    ),
    FinalSpec(
        directory="04_live_location_final_26_05_1",
        base_tag="v26.04.0",
        final_tag="v26.05.1",
        scenario="live_location_final",
        flag="liveLocationSharing: true",
        android_evidence=(
            "features/location/api/src/main/kotlin/io/element/android/features/location/api/live/ActiveLiveLocationShareManager.kt",
            "features/location/api/src/main/kotlin/io/element/android/features/location/api/LiveLocationSharingBanner.kt",
            "features/location/impl/src/main/kotlin/io/element/android/features/location/impl/live/service/LiveLocationSharingService.kt",
        ),
        arkts_evidence=("ActiveLiveLocationShareManagerParity", "startShare(roomId: string, durationMs: number)", "stopShare(session: LiveLocationSessionParity)", "isCurrentlySharing(roomId: string)", "durationMs: number", "updateLocation", "bannerRows", "toLiveTimelineContent"),
        ui_evidence=("open_live_map_evt-live-location-fixture", "supported: true"),
    ),
    FinalSpec(
        directory="05_link_new_device_final_26_08_2",
        base_tag="v26.05.0",
        final_tag="v26.08.2",
        scenario="link_new_device_final",
        flag="richLinkNewDevice: true",
        android_evidence=(
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/screens/qrcode/ShowQrCodePresenter.kt",
            "features/linknewdevice/impl/src/main/kotlin/io/element/android/features/linknewdevice/impl/screens/qrcode/ShowQrCodeState.kt",
            "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/linknewdevice/ContinuationMessageSender.kt",
        ),
        arkts_evidence=("ShowQrCodePresenterParity", "remainingRotations: number", "onQrReady", "onQrRotating", "showLoadingWhileRotating", "onTooManyRotation", "LinkNewDesktopHandlerParity", "startTimer", "timeoutMs: number", "timeoutError", "ContinuationMessageSenderParity", "confirm()", "cancel()"),
        ui_evidence=("QR link: rotating and refreshable", "Owner verification: available", "Timeout handling: available"),
    ),
)


def run(args: list[str]) -> str:
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace").stdout


def git(*args: str) -> str:
    return run(["git", "-C", str(ANDROID_REPO), *args])


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def verify(spec: FinalSpec) -> dict:
    final_dir = FINAL_ROOT / spec.directory
    diff_names = git("diff", "--name-only", f"{spec.base_tag}..{spec.final_tag}", "--")
    source = "\n".join(
        read(path)
        for path in (
            final_dir / "entry" / "src" / "main" / "ets" / "services" / "MockMatrixService.ets",
            final_dir / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
            final_dir / "entry" / "src" / "main" / "ets" / "androidparity" / "FunctionLevelParity.ets",
            final_dir / "verification" / "behavior_contract.json",
            final_dir / "README.md",
            final_dir / "oh-package.json5",
        )
    )
    hap = final_dir / "entry" / "build" / "default" / "outputs" / "default" / "entry-default-unsigned.hap"
    failures: list[str] = []
    failures.extend([f"Android final evidence missing: {item}" for item in spec.android_evidence if item not in diff_names])
    failures.extend([f"ArkTS final evidence missing: {item}" for item in (spec.scenario, spec.flag, *spec.arkts_evidence, *spec.ui_evidence) if item not in source])
    if "Intentionally absent at this base" in source or "Base before" in source or "timeouts are absent" in source:
      failures.append("Final node still contains base-only README/package wording")
    if not hap.exists():
      failures.append("Compiled final HAP missing")
    return {
        "directory": spec.directory,
        "android_range": f"{spec.base_tag}..{spec.final_tag}",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "hap": str(hap),
    }


def render(results: list[dict]) -> str:
    lines = [
        "# Final Migration Review",
        "",
        "Scope: final-development ArkTS nodes generated separately from the version-consistent base nodes. Checks require Android final evidence, ArkTS final symbols, scenario flags, UI semantic ids and compiled HAP outputs.",
        "",
        "| Final node | Android range | Result | HAP |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(f"| `{result['directory']}` | `{result['android_range']}` | {result['status']} | `{result['hap']}` |")

    failures = [result for result in results if result["failures"]]
    if failures:
        lines.extend(["", "## Findings", ""])
        for result in failures:
            lines.append(f"### {result['directory']}")
            for failure in result["failures"]:
                lines.append(f"- {failure}")
    else:
        lines.extend(["", "## Findings", "", "No blocking final-migration issues found by the static review gate."])

    lines.extend([
        "",
        "## Residual Risk",
        "",
        "- The migration is function/state-level ArkTS parity for benchmark nodes, not a complete Element X product port.",
        "- Runtime device verification still needs signed HAP installation and UI automation on an OpenHarmony emulator/device.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [verify(spec) for spec in FINALS]
    (REPORT_DIR / "final_migration_review.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (REPORT_DIR / "final_migration_review.md").write_text(render(results), encoding="utf-8", newline="\n")
    for result in results:
        print(f"{result['status']}\t{result['directory']}\t{len(result['failures'])} failures")
    return 0 if all(result["status"] == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
