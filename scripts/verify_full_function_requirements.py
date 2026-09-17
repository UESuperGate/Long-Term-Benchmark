#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
FINAL_ROOT = ROOT / "final_dev_nodes"
REPORT_DIR = ROOT / "verification_reports"
UI_ROOT = REPORT_DIR / "harmony_dynamic_ui"


@dataclass(frozen=True)
class PairSpec:
    key: str
    task_family: str
    base_dir: str
    final_dir: str
    base_version: str
    final_version: str
    base_scenario: str
    final_scenario: str
    target_flag: str


PAIRS = (
    PairSpec(
        key="01_user_status",
        task_family="User Status",
        base_dir="01_user_status_base_26_07_0",
        final_dir="01_user_status_final_26_08_4",
        base_version="26.07.0",
        final_version="26.08.4",
        base_scenario="user_status_base",
        final_scenario="user_status_final",
        target_flag="userStatus",
    ),
    PairSpec(
        key="02_gallery_messages",
        task_family="Gallery Messages",
        base_dir="02_gallery_messages_base_26_06_1",
        final_dir="02_gallery_messages_final_26_08_1",
        base_version="26.06.1",
        final_version="26.08.1",
        base_scenario="gallery_messages_base",
        final_scenario="gallery_messages_final",
        target_flag="galleryMessages",
    ),
    PairSpec(
        key="03_active_call_timeline",
        task_family="Active Call Timeline Rendering",
        base_dir="03_active_call_timeline_base_26_07_1",
        final_dir="03_active_call_timeline_final_26_08_0",
        base_version="26.07.1",
        final_version="26.08.0",
        base_scenario="active_call_timeline_base",
        final_scenario="active_call_timeline_final",
        target_flag="activeCallTimeline",
    ),
    PairSpec(
        key="04_live_location",
        task_family="Live Location Sharing",
        base_dir="04_live_location_base_26_04_0",
        final_dir="04_live_location_final_26_05_1",
        base_version="26.04.0",
        final_version="26.05.1",
        base_scenario="live_location_base",
        final_scenario="live_location_final",
        target_flag="liveLocationSharing",
    ),
    PairSpec(
        key="05_link_new_device",
        task_family="Link New Device Flow",
        base_dir="05_link_new_device_base_26_05_0",
        final_dir="05_link_new_device_final_26_08_2",
        base_version="26.05.0",
        final_version="26.08.2",
        base_scenario="link_new_device_base",
        final_scenario="link_new_device_final",
        target_flag="richLinkNewDevice",
    ),
)


COMMON_SOURCE_SIGNALS = {
    "build_sdk_23": (
        "build-profile.json5",
        ('"compileSdkVersion": 23', '"compatibleSdkVersion": 23', '"targetSdkVersion": 23', '"runtimeOS": "OpenHarmony"'),
    ),
    "entry_module": (
        "entry/src/main/module.json5",
        ('"srcEntry": "./ets/Application/AbilityStage.ets"', '"mainElement": "EntryAbility"', '"pages": "$profile:main_pages"', '"action.system.home"'),
    ),
    "entry_ability": (
        "entry/src/main/ets/entryability/EntryAbility.ets",
        ("windowStage.loadContent('pages/Index')",),
    ),
    "main_pages": (
        "entry/src/main/resources/base/profile/main_pages.json",
        ('"pages/Index"',),
    ),
    "model_contract": (
        "entry/src/main/ets/model/ElementModels.ets",
        (
            "export enum TimelineEventKind",
            "Text = 'text'",
            "Image = 'image'",
            "Video = 'video'",
            "Gallery = 'gallery'",
            "ActiveCall = 'active_call'",
            "LiveLocation = 'live_location'",
            "Unsupported = 'unsupported'",
            "export interface RoomSummary",
            "export interface TimelineEvent",
            "export interface AccountProfile",
            "export interface BaseFeatureFlags",
            "export interface ScenarioInfo",
        ),
    ),
    "viewmodel_contract": (
        "entry/src/main/ets/viewmodel/ElementBaseViewModel.ets",
        (
            "getScenarioInfo(): ScenarioInfo",
            "getAccountProfile(): AccountProfile",
            "getRooms(): RoomSummary[]",
            "getTimelineEvents(): TimelineEvent[]",
            "getSecurityRows(): string[]",
            "getFunctionLevelAlignmentRows(): string[]",
            "createFunctionLevelAlignmentRows(this.getScenarioInfo().scenarioId)",
        ),
    ),
    "mock_matrix_common": (
        "entry/src/main/ets/services/MockMatrixService.ets",
        (
            "getScenarioInfo(): ScenarioInfo",
            "getFeatureFlags(): BaseFeatureFlags",
            "getAccountProfile(): AccountProfile",
            "getRooms(): RoomSummary[]",
            "getTimelineEvents(): TimelineEvent[]",
            "getSecurityRows(): string[]",
            "Element X General",
            "Design Review",
            "Direct message",
            "Morning! The Android and iOS base snapshots are aligned.",
            "Single image attachment",
            "Session verification: available",
        ),
    ),
    "page_contract": (
        "entry/src/main/ets/pages/Index.ets",
        (
            ".tabBar('Timeline')",
            ".tabBar('Settings')",
            ".tabBar('Security')",
            ".tabBar('Contract')",
            ".onChange((index: number)",
            "this.TimelinePanel()",
            "this.SettingsPanel()",
            "this.SecurityPanel()",
            "this.ContractPanel()",
            "ForEach(this.rooms",
            "ForEach(this.events",
            "ForEach(this.securityRows",
            "ForEach(this.functionAlignmentRows",
            ".id('base_title')",
            ".id('base_release_pair')",
            ".id('timeline_panel')",
            ".id('settings_panel')",
            ".id('security_panel')",
            ".id('contract_panel')",
            ".id('settings_account_card')",
            ".id(`timeline_event_${event.id}`)",
            ".id(`unsupported_${event.id}`)",
            "Unsupported in this base",
        ),
    ),
}


BASE_PARITY_COMMON_SIGNALS = (
    "PreferencesRootPresenterParity",
    "TimelineItemContentMessageFactoryParity",
    "TimelineItemCallNotifyParity",
    "ShareLocationPresenterParity",
    "LinkNewDeviceRootPresenterParity",
    "ShowQrCodeNodeParity",
    "ScanQrCodePresenterParity",
    "LinkDeviceNumberParity",
    "createFunctionLevelAlignmentRows",
)

FINAL_PARITY_COMMON_SIGNALS = (
    "export interface AndroidSymbolAlignment",
    "export class AndroidSymbolAlignmentRow",
    "const FINAL_ALIGNMENTS: AndroidSymbolAlignment[]",
    "getFunctionLevelAlignments(scenarioId: string)",
    "createFunctionLevelAlignmentRows",
)


BASE_REQUIREMENTS = {
    "01_user_status": {
        "service": (
            'const SCENARIO_ID: string = "user_status_base"',
            "canSetUserStatus: false",
            "userStatus: false",
            "No own-status row in Settings.",
            "No custom user status composer.",
            "No automatic call status integration.",
        ),
        "page": ("settings_user_status_absent", "Not available in this base"),
        "parity": ("userStatusInsertionPoint()", "reserved without rendering a user-status row"),
        "must_not": ("UserStatusPresenterParity", "enableAutomaticCallStatus"),
    },
    "02_gallery_messages": {
        "service": (
            'const SCENARIO_ID: string = "gallery_messages_base"',
            "galleryMessages: false",
            "Gallery message fixture: unsupported in this base",
            "mediaCount: 4",
            "supported: false",
        ),
        "page": ("Unsupported in this base",),
        "parity": ("createUnsupportedGalleryFixture", "TimelineItemUnknownContent"),
        "must_not": (),
    },
    "03_active_call_timeline": {
        "service": (
            'const SCENARIO_ID: string = "active_call_timeline_base"',
            "activeCallTimeline: false",
            "Active call fixture: unsupported timeline item in this base",
            "supported: false",
        ),
        "page": ("Unsupported in this base",),
        "parity": ("supportsTimelineCard(): boolean", "return false", "activeCallFixtureContent"),
        "must_not": ("ActiveCallTimelineItemViewParity",),
    },
    "04_live_location": {
        "service": (
            'const SCENARIO_ID: string = "live_location_base"',
            "liveLocationSharing: false",
            "Live location fixture: unsupported in this base",
            "supported: false",
        ),
        "page": ("Unsupported in this base",),
        "parity": ("ShareLocationPresenterParity", "handleStartLiveLocationShare", "disabled_side_effect_for_base"),
        "must_not": ("ActiveLiveLocationShareManagerParity",),
    },
    "05_link_new_device": {
        "service": (
            'const SCENARIO_ID: string = "link_new_device_base"',
            "richLinkNewDevice: false",
            "QR link placeholder: visible but non-rotating",
            "Owner verification: not available",
            "Timeout handling: not available",
        ),
        "page": ("settings_user_status_absent",),
        "parity": ("ShowQrCodeNodeParity", "static QR code", "LinkDeviceNumberParity"),
        "must_not": ("ShowQrCodePresenterParity", "ContinuationMessageSenderParity", "LinkNewDesktopHandlerParity"),
    },
}


FINAL_REQUIREMENTS = {
    "01_user_status": {
        "service": (
            'const SCENARIO_ID: string = "user_status_final"',
            "userStatus: true",
            "canSetUserStatus: true",
        ),
        "page": ("settings_user_status_connected", "🌴 Away - editable"),
        "parity": (
            "UserStatusPresenterParity",
            "emoji: '🌴'",
            "text: 'Away'",
            "event === 'SetStatus'",
            "event === 'ClearStatus'",
            "enableAutomaticCallStatus(enabled: boolean)",
            "mapDisplayedStatus",
        ),
        "ui": {"settings.ui.md": ("User status", "🌴 Away - editable"), "contract.ui.md": ("UserStatusPresenterParity.present()", "enableAutomaticCallStatus")},
    },
    "02_gallery_messages": {
        "service": (
            'const SCENARIO_ID: string = "gallery_messages_final"',
            "galleryMessages: true",
            "Gallery message: four attachments",
            "mediaCount: 4",
            "supported: true",
        ),
        "page": ("Gallery renderer connected", "event.kind === TimelineEventKind.Gallery"),
        "parity": (
            "TimelineItemGalleryContentProviderParity",
            "createGalleryContent(items: GalleryItemDataParity[])",
            "TimelineItemGalleryContent(items: GalleryItemDataParity[])",
            "TimelineItemGalleryView(items: GalleryItemDataParity[])",
            "handleGalleryItemClick",
            "toEventGalleryParams",
            "formatSummary(items: GalleryItemDataParity[])",
        ),
        "ui": {"timeline.ui.md": ("Gallery message: four attachments", "Gallery renderer connected"), "contract.ui.md": ("TimelineItemGalleryContentProviderParity.createGalleryContent()", "TimelineItemGalleryView")},
    },
    "03_active_call_timeline": {
        "service": (
            'const SCENARIO_ID: string = "active_call_timeline_final"',
            "activeCallTimeline: true",
            "Active call in progress",
            "supported: true",
        ),
        "page": ("Button('Join call')", "event.kind === TimelineEventKind.ActiveCall"),
        "parity": (
            "ActiveCallTimelineItemViewParity",
            "ActiveCallTimelineItemView(state: ActiveCallStateParity)",
            "joinCall(state: ActiveCallStateParity)",
            "routeCallContent(kind: string)",
            "renderParticipants(state: ActiveCallStateParity)",
        ),
        "ui": {"timeline.ui.md": ("Active call in progress", "Join call"), "contract.ui.md": ("ActiveCallTimelineItemViewParity", "joinCall", "renderParticipants")},
    },
    "04_live_location": {
        "service": (
            'const SCENARIO_ID: string = "live_location_final"',
            "liveLocationSharing: true",
            "Live location sharing active",
            "supported: true",
        ),
        "page": ("Button('Open live map')", "event.kind === TimelineEventKind.LiveLocation"),
        "parity": (
            "ActiveLiveLocationShareManagerParity",
            "private sharingRoomIds: string[] = []",
            "startShare(roomId: string, durationMs: number)",
            "stopShare(session: LiveLocationSessionParity)",
            "isCurrentlySharing(roomId: string)",
            "durationMs: number",
            "bannerRows(session: LiveLocationSessionParity)",
            "toLiveTimelineContent(session: LiveLocationSessionParity)",
        ),
        "ui": {"timeline.ui.md": ("Live location sharing active", "Open live map"), "contract.ui.md": ("ActiveLiveLocationShareManagerParity.startShare()", "ActiveLiveLocationShareManagerParity.stopShare()", "ActiveLiveLocationShareManagerParity.isCurrentlySharing()")},
    },
    "05_link_new_device": {
        "service": (
            'const SCENARIO_ID: string = "link_new_device_final"',
            "richLinkNewDevice: true",
            "QR link: rotating and refreshable",
            "Owner verification: available",
            "Timeout handling: available",
        ),
        "page": ("SecurityPanel()",),
        "parity": (
            "ShowQrCodePresenterParity",
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
        ),
        "ui": {"security.ui.md": ("QR link: rotating and refreshable", "Owner verification: available", "Timeout handling: available"), "contract.ui.md": ("ShowQrCodePresenterParity.onQrRotating()", "ContinuationMessageSenderParity.confirm()/cancel()", "LinkNewDesktopHandlerParity.timeoutError()")},
    },
}


def project_root(kind: str, name: str) -> Path:
    return ROOT / name if kind == "base" else FINAL_ROOT / name


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def missing_signals(text: str, signals: tuple[str, ...]) -> list[str]:
    return [signal for signal in signals if signal not in text]


def check_file_signals(root: Path, rel_path: str, signals: tuple[str, ...]) -> list[str]:
    path = root / rel_path
    if not path.exists():
        return [f"missing file {rel_path}"]
    return [f"{rel_path} missing {signal}" for signal in missing_signals(read_text(path), signals)]


def check_absent(root: Path, rel_paths: tuple[str, ...], forbidden: tuple[str, ...]) -> list[str]:
    failures: list[str] = []
    for rel_path in rel_paths:
        path = root / rel_path
        if not path.exists():
            continue
        text = read_text(path)
        failures.extend(f"{rel_path} unexpectedly contains {signal}" for signal in forbidden if signal in text)
    return failures


def check_common_project(name: str, kind: str, spec: PairSpec) -> dict:
    root = project_root(kind, name)
    failures: list[str] = []
    checked: list[str] = []

    if not root.exists():
        return {"project": name, "kind": kind, "scope": "common_project", "status": "FAIL", "checked": [], "failures": [f"missing project root {root}"]}

    for label, (rel_path, signals) in COMMON_SOURCE_SIGNALS.items():
        failures.extend(check_file_signals(root, rel_path, signals))
        checked.append(label)

    parity_signals = BASE_PARITY_COMMON_SIGNALS if kind == "base" else FINAL_PARITY_COMMON_SIGNALS
    failures.extend(check_file_signals(root, "entry/src/main/ets/androidparity/FunctionLevelParity.ets", parity_signals))
    checked.append("function_parity_common")

    app_json = root / "AppScope/app.json5"
    if not app_json.exists():
        failures.append("missing AppScope/app.json5")
    else:
        app_text = read_text(app_json)
        if '"bundleName": "com.qingyu.elementx.' not in app_text:
            failures.append("AppScope/app.json5 missing qingyu Element X bundle name")
        checked.append("bundle_name")

    contract_json = root / "verification/behavior_contract.json"
    if not contract_json.exists():
        failures.append("missing verification/behavior_contract.json")
    else:
        contract = json.loads(read_text(contract_json))
        if contract.get("arkts_sdk") != 23:
            failures.append("behavior_contract arkts_sdk is not 23")
        if contract.get("task_family") != spec.task_family:
            failures.append(f"behavior_contract task_family mismatch: {contract.get('task_family')}")
        semantic_ids = set(contract.get("semantic_ids", []))
        for semantic_id in ("base_title", "base_release_pair", "timeline_panel", "settings_panel", "security_panel", "contract_panel", "settings_account_card"):
            if semantic_id not in semantic_ids:
                failures.append(f"behavior_contract missing semantic id {semantic_id}")
        checked.append("behavior_contract")

    return {
        "project": name,
        "kind": kind,
        "scope": "common_project",
        "status": "PASS" if not failures else "FAIL",
        "checked": checked,
        "failures": failures,
    }


def check_pair_requirements(spec: PairSpec) -> list[dict]:
    rows = []
    for kind, name, requirements, scenario in (
        ("base", spec.base_dir, BASE_REQUIREMENTS[spec.key], spec.base_scenario),
        ("final", spec.final_dir, FINAL_REQUIREMENTS[spec.key], spec.final_scenario),
    ):
        root = project_root(kind, name)
        failures: list[str] = []
        service = root / "entry/src/main/ets/services/MockMatrixService.ets"
        page = root / "entry/src/main/ets/pages/Index.ets"
        parity = root / "entry/src/main/ets/androidparity/FunctionLevelParity.ets"
        failures.extend(check_file_signals(root, "entry/src/main/ets/services/MockMatrixService.ets", requirements["service"]))
        failures.extend(check_file_signals(root, "entry/src/main/ets/pages/Index.ets", requirements["page"]))
        failures.extend(check_file_signals(root, "entry/src/main/ets/androidparity/FunctionLevelParity.ets", requirements["parity"]))

        service_text = read_text(service) if service.exists() else ""
        for flag in ("userStatus", "galleryMessages", "activeCallTimeline", "liveLocationSharing", "richLinkNewDevice"):
            expected = "true" if kind == "final" and flag == spec.target_flag else "false"
            signal = f"{flag}: {expected}"
            if signal not in service_text:
                failures.append(f"feature flag {flag} expected {expected}")

        if scenario not in service_text:
            failures.append(f"scenario id {scenario} missing from service")

        if kind == "base":
            failures.extend(check_absent(root, ("entry/src/main/ets/androidparity/FunctionLevelParity.ets",), tuple(requirements.get("must_not", ()))))

        rows.append({
            "pair": spec.key,
            "project": name,
            "kind": kind,
            "scope": "base_final_requirements",
            "status": "PASS" if not failures else "FAIL",
            "checked": ["scenario", "feature_flags", "service_fixture", "page_surface", "function_parity"],
            "failures": failures,
        })
    return rows


def load_ui_manifest() -> list[dict]:
    manifest_path = UI_ROOT / "manifest.json"
    if not manifest_path.exists():
        return []
    return json.loads(read_text(manifest_path))


def check_dynamic_ui(spec: PairSpec, ui_manifest: list[dict]) -> list[dict]:
    rows = []
    entries = {entry["name"]: entry for entry in ui_manifest}
    for kind, name, version in (
        ("base", spec.base_dir, spec.base_version),
        ("final", spec.final_dir, spec.final_version),
    ):
        failures: list[str] = []
        entry = entries.get(name)
        if entry is None:
            failures.append("missing Harmony dynamic UI manifest entry")
            output_dir = UI_ROOT / name
        else:
            output_dir = Path(entry["outputDir"])
            if entry.get("kind") != kind:
                failures.append(f"UI manifest kind mismatch: {entry.get('kind')}")
            captured = set(entry.get("captured", []))
            for filename in ("timeline.ui.md", "settings.ui.md", "security.ui.md", "contract.ui.md"):
                if filename not in captured:
                    failures.append(f"UI manifest missing capture {filename}")

        required_common = {
            "timeline.ui.md": (spec.task_family, f"base {spec.base_version} -> final {spec.final_version}", "Element X General", "Design Review", "Selected room timeline", "Timeline", "Settings", "Security", "Contract"),
            "settings.ui.md": (spec.task_family, "Alice", "@alice:matrix.org", "Notifications", "Privacy", "Appearance"),
            "security.ui.md": (spec.task_family, "Session verification: available"),
            "contract.ui.md": (spec.task_family, "Function-level Android parity"),
        }
        for filename, signals in required_common.items():
            path = output_dir / filename
            if not path.exists():
                failures.append(f"missing UI capture {filename}")
                continue
            text = read_text(path)
            failures.extend(f"{filename} missing {signal}" for signal in missing_signals(text, signals))

        if kind == "base":
            ui_requirements: dict[str, tuple[str, ...]] = {
                "01_user_status": {"settings.ui.md": ("User status", "Not available in this base")},
                "02_gallery_messages": {"timeline.ui.md": ("Gallery message fixture: unsupported in this base", "Unsupported in this base")},
                "03_active_call_timeline": {"timeline.ui.md": ("Active call fixture: unsupported timeline item in this base", "Unsupported in this base")},
                "04_live_location": {"timeline.ui.md": ("Live location fixture: unsupported in this base", "Unsupported in this base")},
                "05_link_new_device": {"security.ui.md": ("QR link placeholder: visible but non-rotating", "Owner verification: not available", "Timeout handling: not available")},
            }[spec.key]
        else:
            ui_requirements = FINAL_REQUIREMENTS[spec.key]["ui"]

        for filename, signals in ui_requirements.items():
            path = output_dir / filename
            if path.exists():
                text = read_text(path)
                failures.extend(f"{filename} missing {signal}" for signal in missing_signals(text, signals))

        rows.append({
            "pair": spec.key,
            "project": name,
            "kind": kind,
            "scope": "dynamic_ui",
            "status": "PASS" if not failures else "FAIL",
            "checked": ["timeline", "settings", "security", "contract", "target_surface"],
            "failures": failures,
        })
    return rows


def check_existing_reports() -> list[dict]:
    report_specs = (
        ("android_arkts_equivalence_report.json", "base static equivalence", "directory"),
        ("final_migration_review.json", "final migration review", "directory"),
        ("function_semantics_deep_review.json", "deep function semantics", "pair"),
        ("harmony_dynamic_ui_report.json", "target dynamic UI assertions", "project"),
    )
    rows = []
    for filename, label, key_field in report_specs:
        path = REPORT_DIR / filename
        failures: list[str] = []
        if not path.exists():
            failures.append(f"missing report {filename}")
            data = []
        else:
            data = json.loads(read_text(path))
            if filename == "android_arkts_equivalence_report.json":
                expected = {pair.base_dir for pair in PAIRS}
                statuses = {row.get(key_field): row.get("status") for row in data}
                for name in expected:
                    if statuses.get(name) != "PASS":
                        failures.append(f"{name} status is {statuses.get(name)}")
            elif filename == "final_migration_review.json":
                expected = {pair.final_dir for pair in PAIRS}
                statuses = {row.get(key_field): row.get("status") for row in data}
                for name in expected:
                    if statuses.get(name) != "PASS":
                        failures.append(f"{name} status is {statuses.get(name)}")
            elif filename == "function_semantics_deep_review.json":
                expected = {pair.key for pair in PAIRS}
                statuses = {row.get(key_field): row.get("status") for row in data}
                for key in expected:
                    if statuses.get(key) != "PASS":
                        failures.append(f"{key} status is {statuses.get(key)}")
            elif filename == "harmony_dynamic_ui_report.json":
                failed = [row for row in data if row.get("status") != "PASS"]
                failures.extend(f"{row.get('project')} {row.get('file')} status is {row.get('status')}" for row in failed)
        rows.append({
            "scope": "dependent_report",
            "name": label,
            "file": filename,
            "status": "PASS" if not failures else "FAIL",
            "checked": [key_field],
            "failures": failures,
        })

    android_refs_path = REPORT_DIR / "android_tag_target_references.json"
    failures = []
    if not android_refs_path.exists():
        failures.append("missing report android_tag_target_references.json")
    else:
        data = json.loads(read_text(android_refs_path))
        pairs = {row["key"]: row for row in data.get("pairs", [])}
        for spec in PAIRS:
            row = pairs.get(spec.key)
            if row is None:
                failures.append(f"missing Android reference pair {spec.key}")
                continue
            if row["final"]["sourceMatchCount"] <= 0:
                failures.append(f"{spec.key} has no Android final source matches")
            if row["final"]["snapshotCount"] <= 0:
                failures.append(f"{spec.key} has no Android final snapshots")
            if len(row.get("changedPaths", [])) <= 0:
                failures.append(f"{spec.key} has no changed target paths")
            if len(row.get("commits", [])) <= 0:
                failures.append(f"{spec.key} has no relevant commit evidence")
    rows.append({
        "scope": "dependent_report",
        "name": "Android tag source/snapshot anchors",
        "file": "android_tag_target_references.json",
        "status": "PASS" if not failures else "FAIL",
        "checked": ["final source refs", "snapshots", "changed paths", "commits"],
        "failures": failures,
    })
    return rows


def render_markdown(report: dict) -> str:
    lines = [
        "# Full Function Requirements Verification",
        "",
        "Scope: acceptance testcase for the five ArkTS base-final mirror pairs. It verifies the shared client baseline, each base's intentionally absent behavior, each final's Android-derived feature behavior, existing Android evidence reports, and Harmony emulator UI captures.",
        "",
        f"Overall status: **{report['status']}**",
        "",
        "| Scope | Subject | Result | Checks | Failures |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in report["checks"]:
        subject = row.get("project") or row.get("name") or row.get("pair")
        lines.append(
            f"| `{row['scope']}` | `{subject}` | {row['status']} | {len(row.get('checked', []))} | {len(row.get('failures', []))} |"
        )
    failures = [row for row in report["checks"] if row.get("failures")]
    if failures:
        lines.extend(["", "## Failures", ""])
        for row in failures:
            subject = row.get("project") or row.get("name") or row.get("pair")
            lines.append(f"### {row['scope']} / {subject}")
            for failure in row["failures"]:
                lines.append(f"- {failure}")
    else:
        lines.extend([
            "",
            "## Result",
            "",
            "All full-function requirement testcase checks passed for the benchmark mirror scope.",
        ])
    lines.extend([
        "",
        "## Coverage",
        "",
        "- 10 ArkTS projects: 5 bases plus 5 finals.",
        "- Common app baseline: SDK 23, entry ability, page routing, model/viewmodel/service contracts, four top-level panels, common timeline/settings/security behavior.",
        "- Base contracts: target feature remains intentionally absent or unsupported at the selected Android base tag.",
        "- Final contracts: target feature behavior is present and mapped to Android final source-level semantics.",
        "- Runtime evidence: Harmony UI captures for Timeline, Settings, Security, and Contract screens are present and asserted.",
        "- Dependency evidence: prior base static equivalence, final migration, deep semantic, Android tag reference, and target dynamic UI reports are all required to pass.",
        "",
        "Note: this is a full-function testcase for the constructed benchmark/mirror client scope, not a claim that the entire production Element X Matrix SDK stack has been reimplemented in ArkTS.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ui_manifest = load_ui_manifest()
    checks: list[dict] = []
    for spec in PAIRS:
        checks.append(check_common_project(spec.base_dir, "base", spec))
        checks.append(check_common_project(spec.final_dir, "final", spec))
        checks.extend(check_pair_requirements(spec))
        checks.extend(check_dynamic_ui(spec, ui_manifest))
    checks.extend(check_existing_reports())

    report = {
        "status": "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL",
        "scope": "benchmark mirror full-function requirements",
        "projectCount": 10,
        "pairCount": len(PAIRS),
        "checks": checks,
    }
    json_path = REPORT_DIR / "full_function_requirements.json"
    md_path = REPORT_DIR / "full_function_requirements.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for row in checks:
        subject = row.get("project") or row.get("name") or row.get("pair")
        print(f"{row['status']}\t{row['scope']}\t{subject}\t{len(row.get('failures', []))} failures")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
