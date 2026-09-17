#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
OUT = ROOT / "final_dev_nodes"


FINALS = [
    {
        "base_dir": "01_user_status_base_26_07_0",
        "final_dir": "01_user_status_final_26_08_4",
        "scenario_base": "user_status_base",
        "scenario_final": "user_status_final",
        "bundle": "com.qingyu.elementx.userstatus.final",
        "label": "Element X User Status Final",
        "version": "26.08.4-final",
        "flag": "userStatus",
        "description": "Final development node with user status connected. Settings exposes editable own status and room/profile surfaces can consume user status data.",
    },
    {
        "base_dir": "02_gallery_messages_base_26_06_1",
        "final_dir": "02_gallery_messages_final_26_08_1",
        "scenario_base": "gallery_messages_base",
        "scenario_final": "gallery_messages_final",
        "bundle": "com.qingyu.elementx.gallery.final",
        "label": "Element X Gallery Messages Final",
        "version": "26.08.1-final",
        "flag": "galleryMessages",
        "description": "Final development node with gallery timeline content connected. Gallery fixtures render as supported multi-attachment messages.",
    },
    {
        "base_dir": "03_active_call_timeline_base_26_07_1",
        "final_dir": "03_active_call_timeline_final_26_08_0",
        "scenario_base": "active_call_timeline_base",
        "scenario_final": "active_call_timeline_final",
        "bundle": "com.qingyu.elementx.activecall.final",
        "label": "Element X Active Call Timeline Final",
        "version": "26.08.0-final",
        "flag": "activeCallTimeline",
        "description": "Final development node with active call timeline rendering connected. Active call fixtures expose a supported timeline action.",
    },
    {
        "base_dir": "04_live_location_base_26_04_0",
        "final_dir": "04_live_location_final_26_05_1",
        "scenario_base": "live_location_base",
        "scenario_final": "live_location_final",
        "bundle": "com.qingyu.elementx.livelocation.final",
        "label": "Element X Live Location Final",
        "version": "26.05.1-final",
        "flag": "liveLocationSharing",
        "description": "Final development node with active live location sharing connected. Timeline, banner-like status and start/stop side effects are represented.",
    },
    {
        "base_dir": "05_link_new_device_base_26_05_0",
        "final_dir": "05_link_new_device_final_26_08_2",
        "scenario_base": "link_new_device_base",
        "scenario_final": "link_new_device_final",
        "bundle": "com.qingyu.elementx.linkdevice.final",
        "label": "Element X Link New Device Final",
        "version": "26.08.2-final",
        "flag": "richLinkNewDevice",
        "description": "Final development node with richer link-new-device QR flow connected. QR rotation, owner verification and timeout states are available.",
    },
]


IGNORE = shutil.ignore_patterns(
    "build",
    ".hvigor",
    "oh_modules",
    "oh-package-lock.json5",
    "*.hap",
)


def replace(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_service(path: Path, spec: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(f'const SCENARIO_ID: string = "{spec["scenario_base"]}";', f'const SCENARIO_ID: string = "{spec["scenario_final"]}";')
    text = re.sub(
        r'const DESCRIPTION: string = "[^"]*";',
        f'const DESCRIPTION: string = {json.dumps(spec["description"], ensure_ascii=False)};',
        text,
    )
    text = re.sub(
        r'const INTENTIONALLY_ABSENT: string\[\] = \[[\s\S]*?\];',
        'const INTENTIONALLY_ABSENT: string[] = [];',
        text,
    )
    text = text.replace('flags: this.getFeatureFlags()', 'flags: this.getFeatureFlags()')
    text = text.replace(f"{spec['flag']}: false", f"{spec['flag']}: true")

    if spec["scenario_final"] == "user_status_final":
        text = text.replace("canSetUserStatus: false", "canSetUserStatus: true")

    text = text.replace("if (SCENARIO_ID === 'gallery_messages_base') {", "if (SCENARIO_ID === 'gallery_messages_base' || SCENARIO_ID === 'gallery_messages_final') {")
    text = text.replace("if (SCENARIO_ID === 'active_call_timeline_base') {", "if (SCENARIO_ID === 'active_call_timeline_base' || SCENARIO_ID === 'active_call_timeline_final') {")
    text = text.replace("if (SCENARIO_ID === 'live_location_base') {", "if (SCENARIO_ID === 'live_location_base' || SCENARIO_ID === 'live_location_final') {")
    text = text.replace("if (SCENARIO_ID === 'link_new_device_base') {", "if (SCENARIO_ID === 'link_new_device_base' || SCENARIO_ID === 'link_new_device_final') {")

    if spec["scenario_final"] == "gallery_messages_final":
        text = text.replace("Gallery message fixture: unsupported in this base", "Gallery message: four attachments")
        text = text.replace("mediaCount: 4,\n        supported: false", "mediaCount: 4,\n        supported: true")
    if spec["scenario_final"] == "active_call_timeline_final":
        text = text.replace("Active call fixture: unsupported timeline item in this base", "Active call in progress")
        text = text.replace("kind: TimelineEventKind.ActiveCall,\n        body: 'Active call in progress',\n        supported: false", "kind: TimelineEventKind.ActiveCall,\n        body: 'Active call in progress',\n        supported: true")
    if spec["scenario_final"] == "live_location_final":
        text = text.replace("Live location fixture: unsupported in this base", "Live location sharing active")
        text = text.replace("kind: TimelineEventKind.LiveLocation,\n        body: 'Live location sharing active',\n        supported: false", "kind: TimelineEventKind.LiveLocation,\n        body: 'Live location sharing active',\n        supported: true")
    if spec["scenario_final"] == "link_new_device_final":
        text = text.replace("'QR link placeholder: visible but non-rotating'", "'QR link: rotating and refreshable'")
        text = text.replace("'Owner verification: not available'", "'Owner verification: available'")
        text = text.replace("'Timeout handling: not available'", "'Timeout handling: available'")

    path.write_text(text, encoding="utf-8", newline="\n")


def patch_app_json(path: Path, spec: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"bundleName":\s*"[^"]+"', f'"bundleName": "{spec["bundle"]}"', text)
    text = re.sub(r'"versionName":\s*"[^"]+"', f'"versionName": "{spec["version"]}"', text)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_index(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "        if (!this.account.canSetUserStatus) {\n"
        "          this.SettingsRow('User status', 'Not available in this base', 'settings_user_status_absent')\n"
        "        }\n",
        "        if (this.account.canSetUserStatus) {\n"
        "          this.SettingsRow('User status', '🌴 Away - editable', 'settings_user_status_connected')\n"
        "        } else {\n"
        "          this.SettingsRow('User status', 'Not available in this base', 'settings_user_status_absent')\n"
        "        }\n",
    )
    text = text.replace(
        "      if (!event.supported) {\n"
        "        Text('Unsupported in this base')",
        "      if (event.supported && event.kind === TimelineEventKind.Gallery) {\n"
        "        Text('Gallery renderer connected')\n"
        "          .fontSize(12)\n"
        "          .fontColor('#14532D')\n"
        "          .padding({ left: 8, right: 8, top: 4, bottom: 4 })\n"
        "          .backgroundColor('#DCFCE7')\n"
        "          .borderRadius(6)\n"
        "          .id(`gallery_connected_${event.id}`)\n"
        "      }\n"
        "      if (event.supported && event.kind === TimelineEventKind.ActiveCall) {\n"
        "        Button('Join call')\n"
        "          .id(`join_call_${event.id}`)\n"
        "      }\n"
        "      if (event.supported && event.kind === TimelineEventKind.LiveLocation) {\n"
        "        Button('Open live map')\n"
        "          .id(`open_live_map_${event.id}`)\n"
        "      }\n"
        "      if (!event.supported) {\n"
        "        Text('Unsupported in this base')",
    )
    text = text.replace("        Text('Intentionally absent')", "        Text('Final migration checks')")
    path.write_text(text, encoding="utf-8", newline="\n")


def write_final_readme(path: Path, spec: dict[str, str]) -> None:
    path.write_text(
        f"""# {spec["label"]}

Source base directory: `{spec["base_dir"]}`
Connected final target: Android `{spec["version"].replace("-final", "")}`
SDK: 23

{spec["description"]}

This directory is a final-development node for benchmark validation. It is generated separately from the base so the base remains version-consistent with the original Android release point.

Build:
- `ohpm install`
- `hvigorw assembleHap --no-daemon`
""",
        encoding="utf-8",
        newline="\n",
    )


def patch_oh_package(path: Path, spec: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"description":\s*"[^"]*"', f'"description": {json.dumps(spec["description"], ensure_ascii=False)}', text)
    path.write_text(text, encoding="utf-8", newline="\n")


def final_parity(spec: dict[str, str]) -> str:
    rows_by_scenario = {
        "user_status_final": [
            ("PreferencesRootPresenter.present()", "UserStatusPresenterParity.present()", "presenter -> presenter", "loads editable own status when MatrixClient.isUserStatusSupported() is true"),
            ("PreferencesRootView UserStatusView insertion", "UserStatusPresenterParity.UserStatusView()", "intra-function slot -> connected view", "settings renders own-status row instead of reserved placeholder"),
            ("UserStatusPresenter.handleEvent(SetStatus)", "UserStatusPresenterParity.handleEvent(SetStatus)", "event branch -> event branch", "set status updates status state"),
            ("UserStatusPresenter.handleEvent(ClearStatus)", "UserStatusPresenterParity.handleEvent(ClearStatus)", "event branch -> event branch", "clear status removes text and emoji"),
            ("MatrixClient.enableAutomaticCallStatus(enabled)", "UserStatusPresenterParity.enableAutomaticCallStatus(enabled)", "client call -> adapter method", "automatic call status can be toggled by support state"),
            ("RoomSummaryRow(dmUserStatus)", "UserStatusPresenterParity.mapDisplayedStatus()", "model mapper -> mapper", "DM room summaries can consume displayed user status"),
        ],
        "gallery_messages_final": [
            ("TimelineItemContentMessageFactory.create(gallery)", "TimelineItemGalleryContentProviderParity.createGalleryContent()", "factory branch -> method", "multi-attachment gallery content maps to supported timeline content"),
            ("TimelineItemGalleryContent(items)", "TimelineItemGalleryContentProviderParity.TimelineItemGalleryContent()", "data class -> data object", "stores visual and non-visual gallery items"),
            ("TimelineItemGalleryView(content)", "TimelineItemGalleryContentProviderParity.TimelineItemGalleryView()", "composable -> view model", "renders gallery grid/list summary"),
            ("MessagesFlowNode.handleGalleryItemClick(...)", "TimelineItemGalleryContentProviderParity.handleGalleryItemClick()", "callback -> method", "opens gallery viewer for the selected item"),
            ("MediaViewerEntryPoint.Params.EventGallery", "TimelineItemGalleryContentProviderParity.toEventGalleryParams()", "navigation params -> method", "passes event id, selected index and item list"),
            ("DefaultMessageSummaryFormatter(gallery)", "TimelineItemGalleryContentProviderParity.formatSummary()", "formatter branch -> method", "summarizes gallery item count"),
        ],
        "active_call_timeline_final": [
            ("ActiveCallTimelineItemView(...)", "ActiveCallTimelineItemViewParity.ActiveCallTimelineItemView()", "composable -> view model", "renders active call timeline card"),
            ("ActiveCallTimelineItemView onJoinCall", "ActiveCallTimelineItemViewParity.joinCall()", "callback -> method", "exposes join-call action"),
            ("TimelineItemCallNotifyView + ActiveCallTimelineItemView", "ActiveCallTimelineItemViewParity.routeCallContent()", "content router -> method", "routes active calls to the active card and old notify events to notify row"),
            ("Call participants/state rendering", "ActiveCallTimelineItemViewParity.renderParticipants()", "sub-view -> method", "renders participant count and call state"),
        ],
        "live_location_final": [
            ("ActiveLiveLocationShareManager.startShare(roomId, duration)", "ActiveLiveLocationShareManagerParity.startShare()", "manager function -> method", "starts live location sharing with a duration and records active room"),
            ("ActiveLiveLocationShareManager.stopShare(roomId)", "ActiveLiveLocationShareManagerParity.stopShare()", "manager function -> method", "stops live location sharing and clears active room"),
            ("ActiveLiveLocationShareManager.isCurrentlySharing(roomId)", "ActiveLiveLocationShareManagerParity.isCurrentlySharing()", "StateFlow mapper -> method", "reports whether the room is currently sharing"),
            ("LiveLocationSharingCoordinator.tick/update", "ActiveLiveLocationShareManagerParity.updateLocation()", "background loop -> method", "pushes updated coordinates while active"),
            ("LiveLocationSharingService", "ActiveLiveLocationShareManagerParity.serviceState()", "service -> state adapter", "models foreground/background sharing state"),
            ("LiveLocationSharingBanner(...)", "ActiveLiveLocationShareManagerParity.bannerRows()", "composable -> view model", "exposes banner-like active sharing row"),
            ("TimelineItemLocationContent.Mode.Live", "ActiveLiveLocationShareManagerParity.toLiveTimelineContent()", "timeline model -> mapper", "renders live location as supported timeline content"),
        ],
        "link_new_device_final": [
            ("ShowQrCodePresenter.present(initialData)", "ShowQrCodePresenterParity.present()", "presenter -> presenter", "emits initial AsyncData.Success QR data"),
            ("LinkMobileStep.QrReady(data)", "ShowQrCodePresenterParity.onQrReady()", "step branch -> method", "replaces QR data and exits loading"),
            ("LinkMobileStep.QrRotating", "ShowQrCodePresenterParity.onQrRotating()", "step branch -> method", "rotates QR while remaining rotation budget is positive"),
            ("ShowQrCodePresenter loadingJob delay(1.seconds)", "ShowQrCodePresenterParity.showLoadingWhileRotating()", "delayed job -> state transition", "shows loading if rotated data is not ready after one second"),
            ("LinkMobileHandler.onTooManyRotation()", "ShowQrCodePresenterParity.onTooManyRotation()", "terminal branch -> method", "emits Expired error after max QR rotations"),
            ("ContinuationMessageSender.confirm/cancel", "ContinuationMessageSenderParity.confirm()/cancel()", "SDK adapter -> methods", "continues or refuses the verified linking flow"),
            ("LinkNewDesktopHandler.startTimer()", "LinkNewDesktopHandlerParity.startTimer()", "timer setup -> method", "starts the 2-minute desktop QR scan timeout"),
            ("LinkDesktopStep.Error(ErrorType.Expired)", "LinkNewDesktopHandlerParity.timeoutError()", "timeout branch -> method", "expires desktop QR scan after the configured timer"),
        ],
    }
    rows = rows_by_scenario[spec["scenario_final"]]
    row_literal = ",\n  ".join(
        f"new AndroidSymbolAlignmentRow({json.dumps(android, ensure_ascii=False)}, {json.dumps(arkts, ensure_ascii=False)}, {json.dumps(granularity, ensure_ascii=False)}, {json.dumps(semantics, ensure_ascii=False)})"
        for android, arkts, granularity, semantics in rows
    )
    return f"""export interface AndroidSymbolAlignment {{
  androidSymbol: string;
  arktsSymbol: string;
  granularity: string;
  finalSemantics: string;
}}

export class AndroidSymbolAlignmentRow implements AndroidSymbolAlignment {{
  androidSymbol: string;
  arktsSymbol: string;
  granularity: string;
  finalSemantics: string;

  constructor(androidSymbol: string, arktsSymbol: string, granularity: string, finalSemantics: string) {{
    this.androidSymbol = androidSymbol;
    this.arktsSymbol = arktsSymbol;
    this.granularity = granularity;
    this.finalSemantics = finalSemantics;
  }}
}}

export interface UserStatusStateParity {{
  emoji: string;
  text: string;
  editable: boolean;
  automaticCallStatusEnabled: boolean;
}}

export class UserStatusPresenterParity {{
  present(): UserStatusStateParity {{
    return {{ emoji: '🌴', text: 'Away', editable: true, automaticCallStatusEnabled: true }};
  }}

  UserStatusView(): string {{
    return 'settings own-status row connected';
  }}

  handleEvent(event: string, value: string = ''): UserStatusStateParity {{
    const state = this.present();
    if (event === 'SetStatus') {{
      state.text = value;
    }}
    if (event === 'ClearStatus') {{
      state.emoji = '';
      state.text = '';
    }}
    return state;
  }}

  enableAutomaticCallStatus(enabled: boolean): boolean {{
    return enabled;
  }}

  mapDisplayedStatus(emoji: string, text: string): string {{
    return `${{emoji}} ${{text}}`.trim();
  }}
}}

export interface GalleryItemDataParity {{
  id: string;
  mimeType: string;
  visual: boolean;
}}

export class TimelineItemGalleryContentProviderParity {{
  createGalleryContent(items: GalleryItemDataParity[]): string {{
    return `TimelineItemGalleryContent:${{items.length}}`;
  }}

  TimelineItemGalleryContent(items: GalleryItemDataParity[]): GalleryItemDataParity[] {{
    return items;
  }}

  TimelineItemGalleryView(items: GalleryItemDataParity[]): string {{
    return items.some((item: GalleryItemDataParity) => item.visual) ? 'gallery grid/list rendered' : 'gallery attachment list rendered';
  }}

  handleGalleryItemClick(eventId: string, galleryItemIndex: number): string {{
    return this.toEventGalleryParams(eventId, galleryItemIndex);
  }}

  toEventGalleryParams(eventId: string, galleryItemIndex: number): string {{
    return `EventGallery:${{eventId}}:${{galleryItemIndex}}`;
  }}

  formatSummary(items: GalleryItemDataParity[]): string {{
    return `${{items.length}} attachments`;
  }}
}}

export interface ActiveCallStateParity {{
  participants: number;
  joined: boolean;
}}

export class ActiveCallTimelineItemViewParity {{
  ActiveCallTimelineItemView(state: ActiveCallStateParity): string {{
    return `active call card:${{this.renderParticipants(state)}}`;
  }}

  joinCall(state: ActiveCallStateParity): ActiveCallStateParity {{
    state.joined = true;
    return state;
  }}

  routeCallContent(kind: string): string {{
    return kind === 'active_call' ? 'ActiveCallTimelineItemView' : 'TimelineItemCallNotifyView';
  }}

  renderParticipants(state: ActiveCallStateParity): string {{
    return `${{state.participants}} participants`;
  }}
}}

export interface LiveLocationSessionParity {{
  roomId: string;
  active: boolean;
  durationMs: number;
  latitude: number;
  longitude: number;
}}

export class ActiveLiveLocationShareManagerParity {{
  private sharingRoomIds: string[] = [];

  startShare(roomId: string, durationMs: number): LiveLocationSessionParity {{
    if (!this.sharingRoomIds.includes(roomId)) {{
      this.sharingRoomIds.push(roomId);
    }}
    return {{ roomId, active: true, durationMs, latitude: 0, longitude: 0 }};
  }}

  stopShare(session: LiveLocationSessionParity): LiveLocationSessionParity {{
    session.active = false;
    this.sharingRoomIds = this.sharingRoomIds.filter((id: string) => id !== session.roomId);
    return session;
  }}

  isCurrentlySharing(roomId: string): boolean {{
    return this.sharingRoomIds.includes(roomId);
  }}

  updateLocation(session: LiveLocationSessionParity, latitude: number, longitude: number): LiveLocationSessionParity {{
    if (session.active) {{
      session.latitude = latitude;
      session.longitude = longitude;
    }}
    return session;
  }}

  serviceState(session: LiveLocationSessionParity): string {{
    return session.active ? 'LiveLocationSharingService.Active' : 'LiveLocationSharingService.Idle';
  }}

  bannerRows(session: LiveLocationSessionParity): string[] {{
    return session.active ? [`Sharing live location in ${{session.roomId}}`] : [];
  }}

  toLiveTimelineContent(session: LiveLocationSessionParity): string {{
    return `TimelineItemLocationContent.Mode.Live:${{session.latitude}},${{session.longitude}}`;
  }}
}}

export interface ShowQrCodeStateParity {{
  data: string;
  loading: boolean;
}}

export class ShowQrCodePresenterParity {{
  remainingRotations: number = 3;
  loadingAfterRotationDelayMs: number = 1000;

  present(initialData: string): ShowQrCodeStateParity {{
    return {{ data: initialData, loading: false }};
  }}

  onQrReady(data: string): ShowQrCodeStateParity {{
    return {{ data, loading: false }};
  }}

  onQrRotating(): string {{
    if (this.remainingRotations-- > 0) {{
      return 'rotateQrCode';
    }}
    return this.onTooManyRotation();
  }}

  showLoadingWhileRotating(state: ShowQrCodeStateParity): ShowQrCodeStateParity {{
    return {{ data: state.data, loading: true }};
  }}

  onTooManyRotation(): string {{
    return 'LinkMobileStep.Error(ErrorType.Expired)';
  }}
}}

export interface LinkDesktopTimerStateParity {{
  startedAtMs: number;
  timeoutMs: number;
  expired: boolean;
}}

export class LinkNewDesktopHandlerParity {{
  startTimer(nowMs: number): LinkDesktopTimerStateParity {{
    return {{ startedAtMs: nowMs, timeoutMs: 120000, expired: false }};
  }}

  tick(state: LinkDesktopTimerStateParity, nowMs: number): LinkDesktopTimerStateParity {{
    state.expired = nowMs - state.startedAtMs >= state.timeoutMs;
    return state;
  }}

  timeoutError(state: LinkDesktopTimerStateParity): string {{
    return state.expired ? 'LinkDesktopStep.Error(ErrorType.Expired)' : 'LinkDesktopStep.Waiting';
  }}
}}

export class ContinuationMessageSenderParity {{
  confirm(): string {{
    return 'ContinuationMessageSender.confirm';
  }}

  cancel(): string {{
    return 'ContinuationMessageSender.cancel';
  }}
}}

const FINAL_ALIGNMENTS: AndroidSymbolAlignment[] = [
  {row_literal}
];

export function getFunctionLevelAlignments(scenarioId: string): AndroidSymbolAlignment[] {{
  if (scenarioId === '{spec["scenario_final"]}') {{
    return FINAL_ALIGNMENTS;
  }}
  return FINAL_ALIGNMENTS;
}}

export function createFunctionLevelAlignmentRows(scenarioId: string): string[] {{
  return getFunctionLevelAlignments(scenarioId).map((item: AndroidSymbolAlignment) => {{
    return `${{item.androidSymbol}} -> ${{item.arktsSymbol}}: ${{item.finalSemantics}}`;
  }});
}}
"""


def patch_contract(path: Path, spec: dict[str, str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["scenario_kind"] = "final_dev_node"
    data["equivalence_scope"] = "connected final-development node for benchmark target validation"
    data["connected_final_behavior"] = spec["description"]
    data["intentionally_absent_until_final"] = []
    if spec["scenario_final"] == "user_status_final":
        data["semantic_ids"].append("settings_user_status_connected")
    if spec["scenario_final"] == "gallery_messages_final":
        data["semantic_ids"].append("gallery_connected_evt-gallery-fixture")
    if spec["scenario_final"] == "active_call_timeline_final":
        data["semantic_ids"].append("join_call_evt-call-fixture")
    if spec["scenario_final"] == "live_location_final":
        data["semantic_ids"].append("open_live_map_evt-live-location-fixture")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_for": "connected ArkTS final development nodes", "sdk": 23, "finals": []}
    for spec in FINALS:
        src = ROOT / spec["base_dir"]
        dst = OUT / spec["final_dir"]
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=IGNORE)

        replacements = {
            spec["base_dir"]: spec["final_dir"],
            spec["bundle"].replace(".final", ".base"): spec["bundle"],
        }
        for rel in ("oh-package.json5", "AppScope/app.json5", "AppScope/resources/base/element/string.json", "entry/src/main/resources/base/element/string.json"):
            replace(dst / rel, replacements)

        write_final_readme(dst / "README.md", spec)
        patch_oh_package(dst / "oh-package.json5", spec)
        patch_app_json(dst / "AppScope" / "app.json5", spec)
        replace(dst / "AppScope" / "resources" / "base" / "element" / "string.json", {" Base": " Final"})
        replace(dst / "entry" / "src" / "main" / "resources" / "base" / "element" / "string.json", {" Base": " Final"})
        patch_service(dst / "entry" / "src" / "main" / "ets" / "services" / "MockMatrixService.ets", spec)
        patch_index(dst / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets")
        (dst / "entry" / "src" / "main" / "ets" / "androidparity" / "FunctionLevelParity.ets").write_text(
            final_parity(spec),
            encoding="utf-8",
            newline="\n",
        )
        patch_contract(dst / "verification" / "behavior_contract.json", spec)

        manifest["finals"].append(
            {
                "directory": str(dst),
                "from_base": spec["base_dir"],
                "scenario": spec["scenario_final"],
                "connected_behavior": spec["description"],
            }
        )

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
