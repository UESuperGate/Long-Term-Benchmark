#!/usr/bin/env python3
"""Score Android implementations against platform-neutral transition structure.

The strict official-JUnit observer remains useful diagnostic evidence, but its tests
compile against one exact upstream API shape. This observer checks the same shared
transition contract through evaluator-owned, implementation-tolerant bindings. Each
case requires model/state, event, and effect evidence in production Kotlin sources.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "state_tests/canonical/cross_platform_contract.json"
MANIFEST = ROOT / "state_tests/android_observer/probes.json"
SOURCE_REPO = ROOT / "_sources/element-x-android"
TASK_ROOTS = {
    "01_user_status": ("features/preferences/", "features/messages/", "libraries/matrix/"),
    "02_gallery_messages": ("features/messages/", "libraries/matrix/", "libraries/mediaviewer/"),
    "03_timeline_protection_rich_events": ("features/messages/", "features/contentscanner/", "libraries/eventformatter/", "libraries/matrixui/"),
    "04_live_location": ("features/location/",),
    "05_link_new_device": ("features/linknewdevice/", "features/lockscreen/"),
}


def o(*patterns: str, path: str = r"\.kt$") -> dict[str, Any]:
    return {"path": path, "patterns": list(patterns)}


def c(*options: dict[str, Any]) -> list[dict[str, Any]]:
    return list(options)


RULES: dict[str, list[list[dict[str, Any]]]] = {
    # Task 1: user status picker and persistence transitions.
    "cross_01_user_status_empty_initial": [c(o(r"UserStatusState", r"displayedStatus", r"rawStatus", r"pickerState", path=r"UserStatusPresenter"))],
    "cross_01_user_status_open_picker": [c(o(r"UserStatusEvent\.OpenPicker\s*->\s*pickerState\s*=\s*UserStatusPickerState\.(ShowingPicker|Predefined)", path=r"UserStatusPresenter"))],
    "cross_01_user_status_dismiss_picker": [c(o(r"UserStatusEvent\.DismissPicker\s*->\s*pickerState\s*=\s*UserStatusPickerState\.Hidden", path=r"UserStatusPresenter"))],
    "cross_01_user_status_set_success": [c(o(r"SelectPredefined|SetStatus|\bSave\b", r"setUserStatus|updateUserStatus", path=r"UserStatus")), c(o(r"AsyncAction|Result", r"Success|runCatchingUpdatingState|runUpdatingState", path=r"UserStatus"))],
    "cross_01_user_status_set_failure": [c(o(r"setUserStatus|updateUserStatus", r"Failure|runCatchingUpdatingState|runUpdatingState", path=r"UserStatus")), c(o(r"displayedStatus|rawStatus|currentStatus", path=r"UserStatus"))],
    "cross_01_user_status_custom_input_defaults": [c(o(r"OpenCustomInput|EnterCustomStatus", r"CustomInput")), c(o(r"raw\?\.emoji\s*\?:\s*\"|defaultEmoji"))],
    "cross_01_user_status_custom_input_prefill": [c(o(r"OpenCustomInput", r"rawStatus|userProfile\.rawStatus", r"CustomInput", path=r"UserStatusPresenter"))],
    "cross_01_user_status_cancel_custom_input": [c(o(r"CancelCustomInput", r"rawStatus|displayedStatus|saved"))],
    "cross_01_user_status_clear_status": [c(o(r"ClearStatus|UserStatusEvent\.Clear", r"clearUserStatus", path=r"UserStatusPresenter")), c(o(r"Hidden|pickerState", path=r"UserStatus"))],

    # Task 2: gallery mapping must retain the complete ordered attachment set.
    "cross_02_gallery_messages_visual_gallery": [c(o(r"GalleryMessageType", r"TimelineItemAttachmentsContent|TimelineItemGalleryContent", path=r"Factory\.kt$|Content\.kt$")), c(o(r"Image", r"Video", r"items", path=r"Gallery|Factory|Content"))],
    "cross_02_gallery_messages_file_gallery": [c(o(r"GalleryMessageType", r"File|attachments", path=r"Factory\.kt$|Content\.kt$"))],
    "cross_02_gallery_messages_mixed_gallery": [c(o(r"GalleryMessageType", r"items", r"map|forEach", path=r"Factory\.kt$")), c(o(r"Image", r"File|Audio|Unknown", path=r"Gallery|Factory|Content"))],
    "cross_02_gallery_messages_thumbnail_fallback": [c(o(r"GalleryMessageType", r"TimelineItemAttachmentsContent|TimelineItemGalleryContent", path=r"Factory\.kt$|Content\.kt$")), c(o(r"thumbnailSource", r"\?:|fallback|mediaSource"))],
    "cross_02_gallery_messages_empty_gallery_fallback": [c(o(r"GalleryMessageType", r"TimelineItemAttachmentsContent|TimelineItemGalleryContent", path=r"Factory\.kt$|Content\.kt$")), c(o(r"items\.isEmpty|emptyList|isEmpty", r"fallback|safe|empty", path=r"Gallery|Factory|Content"))],
    "cross_02_gallery_messages_formatted_caption": [c(o(r"GalleryMessageType", r"formattedCaption", path=r"Factory\.kt$|Content\.kt$"))],

    # Task 3: content-validation state and active-call rendering.
    "cross_03_timeline_protection_rich_events_unknown_requests_scan": [c(o(r"ContentValidationValue", r"Unknown", r"getCurrentMediaState|states\.values\.isEmpty|initial"))],
    "cross_03_timeline_protection_rich_events_single_media_scan": [c(o(r"ContentScannerService|contentScanner", r"scan\(|validate", path=r"Presenter|Service")), c(o(r"ContentValidation", r"update|value"))],
    "cross_03_timeline_protection_rich_events_gallery_scan_aggregation": [c(o(r"updateAll|perMediaUrl|validationFor|calculateOverallState", r"Map|values", path=r"Validation|Scanner")), c(o(r"Invalid", r"Loading", r"Valid", path=r"Validation|Scanner"))],
    "cross_03_timeline_protection_rich_events_cached_validation_stable": [c(o(r"cache|cached|containsKey", r"Unknown|validation", path=r"Validation|Scanner"))],
    "cross_03_timeline_protection_rich_events_scanner_recoverable_failure": [c(o(r"recoverable|Retryable", r"Unknown", path=r"Validation|Scanner"))],
    "cross_03_timeline_protection_rich_events_scanner_unrecoverable_failure": [c(o(r"UnrecoverableError", r"shouldHideOriginalContent|fallback|Invalid"))],
    "cross_03_timeline_protection_rich_events_render_only_private_room": [c(o(r"TimelineProtection|ContentValidation", r"isPublic|private|protected|shouldHideOriginalContent")), c(o(r"ContentValidationValue", r"Unknown", path=r"Validation|Protection"))],
    "cross_03_timeline_protection_rich_events_declined_call_not_joinable": [c(o(r"RtcNotificationState\.Declined", r"showAsDeclined|canJoin|join")), c(o(r"RtcNotificationState\.Active|RtcNotificationEventType\.Start"))],
    "cross_03_timeline_protection_rich_events_dm_call_started": [c(o(r"RtcNotificationState\.Active|RtcNotificationEventType\.Start", r"JoinActiveCall|canJoin|active"))],

    # Task 4: live-share manager/coordinator/store lifecycle.
    "cross_04_live_location_start_share": [c(o(r"startShare|startLiveLocation", r"ActiveLiveLocationShare", r"update|persist"))],
    "cross_04_live_location_stop_share": [c(o(r"stopShare|stopLiveLocation", r"remove|current\s*-|emptyMap"))],
    "cross_04_live_location_restore_share": [c(o(r"restore|setup", r"expiresAt|expiry", path=r"LiveLocation|ShareManager"))],
    "cross_04_live_location_timeout_expiry": [c(o(r"markExpired|timeout|delay", r"stopShare|remove", path=r"LiveLocation|ShareManager|Coordinator"))],
    "cross_04_live_location_location_dispatch": [c(o(r"updateLastLocation|onLocation|dispatch", r"lastGeoUri|receiver|location"))],
    "cross_04_live_location_disclaimer_acceptance": [c(o(r"Disclaimer", r"DataStore|Preferences|persist|sessionId", path=r"Store|Preferences"))],
    "cross_04_live_location_expiry_store": [c(o(r"LiveLocationStore|expiry", r"Preferences|DataStore|stringPreferencesKey"))],

    # Task 5: QR lifecycle, number confirmation, and owner-verification gate.
    "cross_05_link_new_device_qr_available": [c(o(r"ShowQrCodePresenter|QrRotating", r"QrReady|qrCodeData|data"))],
    "cross_05_link_new_device_qr_rotation": [c(o(r"QrRotating|RotateQr|onQrRotation", r"QrReady|request|generate"))],
    "cross_05_link_new_device_qr_rotation_bound": [c(o(r"QrRotating|RotateQr", r"maxQrCodeRotation|TooManyRotation|bound|disabled"))],
    "cross_05_link_new_device_owner_biometric": [c(o(r"deviceUnlockCallback", r"canUseDeviceUnlock", r"authenticate", path=r"DeviceUnlockPresenter"))],
    "cross_05_link_new_device_owner_pin_fallback": [c(o(r"DeviceUnlockCallbackHolder|OwnerVerificationState", r"showApplicationPinCode|PinCode|device PIN", path=r"DeviceUnlock|Owner|Root"))],
    "cross_05_link_new_device_owner_cancel": [c(o(r"CancelPinCode|OwnerVerificationCancel", r"cancel|Cancelled", r"reset|clear|callback", path=r"DeviceUnlock|Root|Owner"))],
}


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def candidate_sources(root: Path, roots: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("*.kt"):
        relative = path.relative_to(root).as_posix()
        if (
            "/src/main/" not in f"/{relative}"
            or "/build/" in f"/{relative}"
            or not relative.startswith(roots)
        ):
            continue
        result[relative] = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    return result


def tag_sources(repo: Path, tag: str, roots: tuple[str, ...]) -> dict[str, str]:
    names = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", tag], text=True).splitlines()
    result: dict[str, str] = {}
    for name in names:
        if not name.endswith(".kt") or "/src/main/" not in f"/{name}" or not name.startswith(roots):
            continue
        text = subprocess.check_output(["git", "-C", str(repo), "show", f"{tag}:{name}"], text=True, errors="replace")
        result[name] = strip_comments(text)
    return result


def option_matches(option: dict[str, Any], sources: dict[str, str]) -> tuple[bool, str | None]:
    path_pattern = re.compile(option["path"])
    patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in option["patterns"]]
    for path, text in sources.items():
        if path_pattern.search(path) and all(pattern.search(text) for pattern in patterns):
            return True, path
    return False, None


def score_case(case: dict[str, Any], sources: dict[str, str]) -> dict[str, Any]:
    clauses = RULES[case["caseId"]]
    evidence = []
    for index, clause in enumerate(clauses, start=1):
        matched_path = None
        for option in clause:
            matched, path = option_matches(option, sources)
            if matched:
                matched_path = path
                break
        evidence.append({"clause": index, "passed": matched_path is not None, "path": matched_path})
    passed = all(item["passed"] for item in evidence)
    return {
        "caseId": case["caseId"],
        "taskId": case["taskId"],
        "traceDigest": case["traceDigest"],
        "semanticStatus": "passed" if passed else "failed",
        "evidenceSource": "portable_production_transition_structure",
        "clauses": evidence,
    }


def evaluate(contract: dict[str, Any], sources_by_task: dict[str, dict[str, str]]) -> dict[str, Any]:
    rows = [score_case(case, sources_by_task[case["taskId"]]) for case in contract["cases"]]
    counts = Counter(row["semanticStatus"] for row in rows)
    return {"rows": rows, "counts": {"passed": counts["passed"], "failed": counts["failed"], "total": len(rows)}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--source-repo", type=Path, default=SOURCE_REPO)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
    if set(RULES) != {case["caseId"] for case in contract["cases"]}:
        raise RuntimeError("portable rule set does not exactly cover the shared contract")

    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "contract": str(CONTRACT.resolve()),
        "observerOwner": "evaluator",
        "method": "portable production transition structure",
    }
    if args.calibrate:
        base_sources = {task: tag_sources(args.source_repo, data["baseTag"], TASK_ROOTS[task]) for task, data in manifest.items()}
        final_sources = {task: tag_sources(args.source_repo, data["finalTag"], TASK_ROOTS[task]) for task, data in manifest.items()}
        payload["base"] = evaluate(contract, base_sources)
        payload["final"] = evaluate(contract, final_sources)
        payload["polarityValid"] = payload["base"]["counts"]["passed"] == 0 and payload["final"]["counts"]["passed"] == len(contract["cases"])
    if args.candidate_root:
        candidate = {
            task: candidate_sources(args.candidate_root / data["candidateDir"], TASK_ROOTS[task])
            for task, data in manifest.items()
        }
        payload["agent"] = evaluate(contract, candidate)
        payload["candidateRoot"] = str(args.candidate_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value["counts"] for key, value in payload.items() if key in {"base", "final", "agent"}} | {"polarityValid": payload.get("polarityValid")}, ensure_ascii=False))
    return 0 if not args.calibrate or payload["polarityValid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
