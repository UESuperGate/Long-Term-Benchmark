from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
DEVECO_PREVIEW_ICON = Path(
    r"C:\Users\xiexi\AppData\Local\Huawei\DevEcoStudio26.0\tmp\previewProject\AppScope\resources\base\media\app_icon.png"
)


BASES = [
    {
        "dir": "01_user_status_base_26_07_0",
        "name": "ElementXUserStatusBase",
        "label": "Element X User Status Base",
        "bundle": "com.qingyu.elementx.userstatus.base",
        "scenario": "user_status_base",
        "base": "26.07.0",
        "final": "26.08.4",
        "task": "User Status",
        "description": "Base before user status is enabled. Settings, room list, timeline and emoji primitives exist, but the user cannot set or clear a custom status and room heroes do not expose status.",
        "absent": [
            "No own-status row in Settings.",
            "No custom user status composer.",
            "No user status badge on the settings avatar or room heroes.",
            "No automatic call status integration.",
        ],
        "checkpoints": [
            "Room list renders direct and group rooms from mock Matrix data.",
            "Timeline renders text and single-media messages.",
            "Settings screen renders account identity and privacy rows.",
            "Emoji data exists as generic reaction data only.",
            "Searching for a status action returns no actionable UI.",
        ],
    },
    {
        "dir": "02_gallery_messages_base_26_06_1",
        "name": "ElementXGalleryBase",
        "label": "Element X Gallery Messages Base",
        "bundle": "com.qingyu.elementx.gallery.base",
        "scenario": "gallery_messages_base",
        "base": "26.06.1",
        "final": "26.08.1",
        "task": "Gallery Messages",
        "description": "Base before gallery messages. Single image/video media works; multi-attachment gallery timeline items are deliberately unsupported.",
        "absent": [
            "No gallery grid renderer.",
            "No gallery list renderer for non-visual attachments.",
            "No full-screen gallery item preview.",
            "No gallery replies or gallery media browser support.",
        ],
        "checkpoints": [
            "Timeline renders text messages.",
            "Timeline renders a single image media event.",
            "Media browser opens a single media preview.",
            "Gallery event fixture is shown as unsupported content.",
            "Reply preview ignores gallery item count.",
        ],
    },
    {
        "dir": "03_active_call_timeline_base_26_07_1",
        "name": "ElementXActiveCallBase",
        "label": "Element X Active Call Timeline Base",
        "bundle": "com.qingyu.elementx.activecall.base",
        "scenario": "active_call_timeline_base",
        "base": "26.07.1",
        "final": "26.08.0",
        "task": "Active Call Timeline Rendering",
        "description": "Base before active call timeline rendering. Rooms and ordinary events render; active call events remain an unsupported timeline state.",
        "absent": [
            "No active call timeline card.",
            "No join-call action from timeline.",
            "No participant/call-state rendering in the timeline.",
            "No active-call snapshot coverage.",
        ],
        "checkpoints": [
            "Room timeline opens from the room list.",
            "Text/media events render in chronological order.",
            "A call event fixture is present in the data layer.",
            "The call event renders as unsupported content.",
            "No call-specific primary action is exposed.",
        ],
    },
    {
        "dir": "04_live_location_base_26_04_0",
        "name": "ElementXLiveLocationBase",
        "label": "Element X Live Location Base",
        "bundle": "com.qingyu.elementx.livelocation.base",
        "scenario": "live_location_base",
        "base": "26.04.0",
        "final": "26.05.1",
        "task": "Live Location Sharing",
        "description": "Base before live location sharing. Basic timeline and permission settings exist, but there is no live map banner, live session lifecycle or background location flow.",
        "absent": [
            "No start-live-location composer action.",
            "No live location timeline renderer.",
            "No background location update loop.",
            "No thread restriction for live location sharing.",
        ],
        "checkpoints": [
            "Timeline renders ordinary messages.",
            "Settings exposes generic permissions information.",
            "Location permission state can be displayed from mock data.",
            "Live location fixture is present as unsupported content.",
            "No live-sharing action can be started.",
        ],
    },
    {
        "dir": "05_link_new_device_base_26_05_0",
        "name": "ElementXLinkDeviceBase",
        "label": "Element X Link New Device Base",
        "bundle": "com.qingyu.elementx.linkdevice.base",
        "scenario": "link_new_device_base",
        "base": "26.05.0",
        "final": "26.08.2",
        "task": "Link New Device Flow",
        "description": "Base before the richer link-new-device QR iterations. Security settings and manual session verification exist; QR rotation, owner verification, warnings and timeouts are absent.",
        "absent": [
            "No QR-code rotation loop.",
            "No device-owner verification gate.",
            "No scan-screen warning.",
            "No post-owner-verification timeout.",
        ],
        "checkpoints": [
            "Security settings can be opened from Settings.",
            "Existing session verification state is visible.",
            "Manual recovery-key flow is available.",
            "A QR login placeholder is visible but non-rotating.",
            "No timeout or owner verification state transition occurs.",
        ],
    },
]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def project_files(base: dict) -> dict[str, str]:
    app_name = base["name"]
    label = base["label"]
    bundle = base["bundle"]
    version_name = f"{base['base']}-base"
    scenario = base["scenario"]
    description = base["description"]
    absent_items = base["absent"]
    checkpoints = base["checkpoints"]

    readme = f"""# {label}

Element X source base: Android `v{base['base']}` / iOS `release/{base['base']}`
Corresponding final development point: Android `v{base['final']}` / iOS `release/{base['final']}`
Task family: {base['task']}

This is a behavior-equivalent ArkTS/OpenHarmony base for SDK 23. It preserves the relevant base behavior needed by the benchmark and intentionally omits the target feature that appears by the final release point.

Base behavior:
{chr(10).join(f"- {item}" for item in checkpoints)}

Intentionally absent at this base:
{chr(10).join(f"- {item}" for item in absent_items)}
"""

    oh_package = f"""{{
  "modelVersion": "5.0.0",
  "name": "{base['dir']}",
  "version": "1.0.0",
  "description": {q(description)},
  "main": "",
  "author": "qingyu",
  "license": "Apache-2.0",
  "dependencies": {{}},
  "devDependencies": {{}}
}}
"""

    entry_oh_package = f"""{{
  "name": "entry",
  "version": "1.0.0",
  "description": "{label} entry module",
  "main": "",
  "author": "qingyu",
  "license": "Apache-2.0",
  "dependencies": {{}}
}}
"""

    build_profile = """{
  "app": {
    "products": [
      {
        "name": "default",
        "compileSdkVersion": 23,
        "compatibleSdkVersion": 23,
        "targetSdkVersion": 23,
        "runtimeOS": "OpenHarmony"
      }
    ],
    "signingConfigs": [],
    "buildModeSet": [
      {
        "name": "debug"
      },
      {
        "name": "release"
      }
    ]
  },
  "modules": [
    {
      "name": "entry",
      "srcPath": "./entry",
      "targets": [
        {
          "name": "default",
          "applyToProducts": [
            "default"
          ]
        }
      ]
    }
  ]
}
"""

    hvigor = """import { appTasks } from '@ohos/hvigor-ohos-plugin';

export default {
  system: appTasks,
  plugins: []
};
"""

    entry_hvigor = """import { hapTasks } from '@ohos/hvigor-ohos-plugin';

export default {
  system: hapTasks,
  plugins: []
};
"""

    hvigor_config = """{
  "modelVersion": "5.0.0",
  "dependencies": {},
  "execution": {
    "typeCheck": true
  },
  "logging": {},
  "debugging": {},
  "nodeOptions": {}
}
"""

    local_properties = """sdk.dir=C:/Users/xiexi/AppData/Local/OpenHarmony/Sdk
"""

    app_json = f"""{{
  "app": {{
    "bundleName": "{bundle}",
    "vendor": "qingyu",
    "versionCode": 1,
    "versionName": "{version_name}",
    "icon": "$media:app_icon",
    "minAPIVersion": 23,
    "targetAPIVersion": 23,
    "label": "$string:app_name"
  }}
}}
"""

    module_json = f"""{{
  "module": {{
    "name": "entry",
    "type": "entry",
    "srcEntry": "./ets/Application/AbilityStage.ets",
    "description": "$string:module_desc",
    "mainElement": "EntryAbility",
    "deviceTypes": [
      "default"
    ],
    "deliveryWithInstall": true,
    "installationFree": false,
    "pages": "$profile:main_pages",
    "abilities": [
      {{
        "name": "EntryAbility",
        "srcEntry": "./ets/entryability/EntryAbility.ets",
        "description": "$string:entry_desc",
        "exported": true,
        "label": "$string:entry_app_name",
        "startWindowIcon": "$media:startIcon",
        "startWindowBackground": "$color:start_window_background",
        "skills": [
          {{
            "entities": [
              "entity.system.home"
            ],
            "actions": [
              "action.system.home"
            ]
          }}
        ]
      }}
    ]
  }}
}}
"""

    ability_stage = """import AbilityStage from '@ohos.app.ability.AbilityStage';

export default class EntryAbilityStage extends AbilityStage {
  onCreate(): void {
  }
}
"""

    entry_ability = """import UIAbility from '@ohos.app.ability.UIAbility';
import window from '@ohos.window';

export default class EntryAbility extends UIAbility {
  onWindowStageCreate(windowStage: window.WindowStage): void {
    try {
      windowStage.loadContent('pages/Index');
    } catch (error) {
      console.error(`Failed to load content: ${JSON.stringify(error)}`);
    }
  }
}
"""

    main_pages = """{
  "src": [
    "pages/Index"
  ]
}
"""

    app_scope_strings = f"""{{
  "string": [
    {{
      "name": "app_name",
      "value": "{label}"
    }}
  ]
}}
"""

    strings = f"""{{
  "string": [
    {{
      "name": "entry_app_name",
      "value": "{label}"
    }},
    {{
      "name": "module_desc",
      "value": "Element X ArkTS base module"
    }},
    {{
      "name": "entry_desc",
      "value": "Main entry"
    }}
  ]
}}
"""

    colors = """{
  "color": [
    {
      "name": "start_window_background",
      "value": "#F7F8FA"
    }
  ]
}
"""

    models = """export enum TimelineEventKind {
  Text = 'text',
  Image = 'image',
  Video = 'video',
  Gallery = 'gallery',
  ActiveCall = 'active_call',
  LiveLocation = 'live_location',
  Unsupported = 'unsupported'
}

export interface RoomSummary {
  id: string;
  name: string;
  topic: string;
  unreadCount: number;
  isDirect: boolean;
}

export interface TimelineEvent {
  id: string;
  sender: string;
  timestamp: string;
  kind: TimelineEventKind;
  body: string;
  mediaCount?: number;
  supported: boolean;
}

export interface AccountProfile {
  userId: string;
  displayName: string;
  avatarInitials: string;
  canSetUserStatus: boolean;
}

export interface BaseFeatureFlags {
  userStatus: boolean;
  galleryMessages: boolean;
  activeCallTimeline: boolean;
  liveLocationSharing: boolean;
  richLinkNewDevice: boolean;
}

export interface ScenarioInfo {
  scenarioId: string;
  taskFamily: string;
  baseVersion: string;
  finalVersion: string;
  description: string;
  intentionallyAbsent: string[];
  flags: BaseFeatureFlags;
}
"""

    service = f"""import {{ AccountProfile, BaseFeatureFlags, RoomSummary, ScenarioInfo, TimelineEvent, TimelineEventKind }} from '../model/ElementModels';

const SCENARIO_ID: string = {q(scenario)};
const TASK_FAMILY: string = {q(base['task'])};
const BASE_VERSION: string = {q(base['base'])};
const FINAL_VERSION: string = {q(base['final'])};
const DESCRIPTION: string = {q(description)};
const INTENTIONALLY_ABSENT: string[] = {json.dumps(absent_items, ensure_ascii=False, indent=2)};

export class MockMatrixService {{
  getScenarioInfo(): ScenarioInfo {{
    return {{
      scenarioId: SCENARIO_ID,
      taskFamily: TASK_FAMILY,
      baseVersion: BASE_VERSION,
      finalVersion: FINAL_VERSION,
      description: DESCRIPTION,
      intentionallyAbsent: INTENTIONALLY_ABSENT,
      flags: this.getFeatureFlags()
    }};
  }}

  getFeatureFlags(): BaseFeatureFlags {{
    return {{
      userStatus: false,
      galleryMessages: false,
      activeCallTimeline: false,
      liveLocationSharing: false,
      richLinkNewDevice: false
    }};
  }}

  getAccountProfile(): AccountProfile {{
    return {{
      userId: '@alice:matrix.org',
      displayName: 'Alice',
      avatarInitials: 'AL',
      canSetUserStatus: false
    }};
  }}

  getRooms(): RoomSummary[] {{
    return [
      {{
        id: 'room-general',
        name: 'Element X General',
        topic: 'Cross-platform product discussion',
        unreadCount: 3,
        isDirect: false
      }},
      {{
        id: 'room-design',
        name: 'Design Review',
        topic: 'Mobile UI and accessibility',
        unreadCount: 0,
        isDirect: false
      }},
      {{
        id: 'dm-bob',
        name: 'Bob',
        topic: 'Direct message',
        unreadCount: 1,
        isDirect: true
      }}
    ];
  }}

  getTimelineEvents(): TimelineEvent[] {{
    const baseEvents: TimelineEvent[] = [
      {{
        id: 'evt-001',
        sender: 'Alice',
        timestamp: '09:20',
        kind: TimelineEventKind.Text,
        body: 'Morning! The Android and iOS base snapshots are aligned.',
        supported: true
      }},
      {{
        id: 'evt-002',
        sender: 'Bob',
        timestamp: '09:23',
        kind: TimelineEventKind.Image,
        body: 'Single image attachment',
        mediaCount: 1,
        supported: true
      }},
      {{
        id: 'evt-003',
        sender: 'Chen',
        timestamp: '09:25',
        kind: TimelineEventKind.Text,
        body: 'Please keep existing room and timeline behavior stable.',
        supported: true
      }}
    ];

    if (SCENARIO_ID === 'gallery_messages_base') {{
      baseEvents.push({{
        id: 'evt-gallery-fixture',
        sender: 'Dana',
        timestamp: '09:31',
        kind: TimelineEventKind.Gallery,
        body: 'Gallery message fixture: unsupported in this base',
        mediaCount: 4,
        supported: false
      }});
    }}

    if (SCENARIO_ID === 'active_call_timeline_base') {{
      baseEvents.push({{
        id: 'evt-call-fixture',
        sender: 'Element Call',
        timestamp: '09:35',
        kind: TimelineEventKind.ActiveCall,
        body: 'Active call fixture: unsupported timeline item in this base',
        supported: false
      }});
    }}

    if (SCENARIO_ID === 'live_location_base') {{
      baseEvents.push({{
        id: 'evt-live-location-fixture',
        sender: 'Bob',
        timestamp: '09:41',
        kind: TimelineEventKind.LiveLocation,
        body: 'Live location fixture: unsupported in this base',
        supported: false
      }});
    }}

    return baseEvents;
  }}

  getSecurityRows(): string[] {{
    if (SCENARIO_ID === 'link_new_device_base') {{
      return [
        'Session verification: available',
        'Manual recovery key: available',
        'QR link placeholder: visible but non-rotating',
        'Owner verification: not available',
        'Timeout handling: not available'
      ];
    }}

    return [
      'Session verification: available',
      'Recovery: available',
      'Device list: available'
    ];
  }}
}}
"""

    viewmodel = """import { AccountProfile, RoomSummary, ScenarioInfo, TimelineEvent } from '../model/ElementModels';
import { MockMatrixService } from '../services/MockMatrixService';

export class ElementBaseViewModel {
  private readonly service: MockMatrixService = new MockMatrixService();

  getScenarioInfo(): ScenarioInfo {
    return this.service.getScenarioInfo();
  }

  getAccountProfile(): AccountProfile {
    return this.service.getAccountProfile();
  }

  getRooms(): RoomSummary[] {
    return this.service.getRooms();
  }

  getTimelineEvents(): TimelineEvent[] {
    return this.service.getTimelineEvents();
  }

  getSecurityRows(): string[] {
    return this.service.getSecurityRows();
  }
}
"""

    index = """import { AccountProfile, RoomSummary, ScenarioInfo, TimelineEvent, TimelineEventKind } from '../model/ElementModels';
import { ElementBaseViewModel } from '../viewmodel/ElementBaseViewModel';

@Entry
@Component
struct Index {
  private viewModel: ElementBaseViewModel = new ElementBaseViewModel();
  private scenario: ScenarioInfo = this.viewModel.getScenarioInfo();
  private account: AccountProfile = this.viewModel.getAccountProfile();
  private rooms: RoomSummary[] = this.viewModel.getRooms();
  private events: TimelineEvent[] = this.viewModel.getTimelineEvents();
  private securityRows: string[] = this.viewModel.getSecurityRows();
  @State private selectedTab: number = 0;

  build() {
    Column() {
      this.Header()
      Tabs({ index: this.selectedTab }) {
        TabContent() {
          this.TimelinePanel()
        }
        .tabBar('Timeline')

        TabContent() {
          this.SettingsPanel()
        }
        .tabBar('Settings')

        TabContent() {
          this.SecurityPanel()
        }
        .tabBar('Security')

        TabContent() {
          this.ContractPanel()
        }
        .tabBar('Contract')
      }
      .barPosition(BarPosition.Start)
      .onChange((index: number) => {
        this.selectedTab = index;
      })
      .layoutWeight(1)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F7F8FA')
  }

  @Builder
  Header() {
    Column({ space: 6 }) {
      Text(this.scenario.taskFamily)
        .fontSize(22)
        .fontWeight(FontWeight.Bold)
        .fontColor('#18202A')
        .id('base_title')
      Text(`base ${this.scenario.baseVersion} -> final ${this.scenario.finalVersion}`)
        .fontSize(13)
        .fontColor('#647083')
        .id('base_release_pair')
      Text(this.scenario.description)
        .fontSize(14)
        .fontColor('#334155')
        .lineHeight(20)
        .id('base_description')
    }
    .alignItems(HorizontalAlign.Start)
    .padding({ left: 18, right: 18, top: 20, bottom: 12 })
    .width('100%')
    .backgroundColor('#FFFFFF')
  }

  @Builder
  TimelinePanel() {
    Scroll() {
      Column({ space: 12 }) {
        ForEach(this.rooms, (room: RoomSummary) => {
          Row() {
            Column() {
              Text(room.name)
                .fontSize(16)
                .fontWeight(FontWeight.Medium)
                .fontColor('#1E293B')
              Text(room.topic)
                .fontSize(12)
                .fontColor('#64748B')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            if (room.unreadCount > 0) {
              Text(room.unreadCount.toString())
                .fontSize(12)
                .fontColor('#FFFFFF')
                .textAlign(TextAlign.Center)
                .width(24)
                .height(24)
                .borderRadius(12)
                .backgroundColor('#2563EB')
            }
          }
          .padding(12)
          .borderRadius(8)
          .backgroundColor('#FFFFFF')
          .id(`room_${room.id}`)
        })

        Text('Selected room timeline')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
          .margin({ top: 8 })

        ForEach(this.events, (event: TimelineEvent) => {
          this.EventRow(event)
        })
      }
      .padding(16)
    }
    .id('timeline_panel')
  }

  @Builder
  EventRow(event: TimelineEvent) {
    Column({ space: 6 }) {
      Row() {
        Text(event.sender)
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#0F172A')
        Blank()
        Text(event.timestamp)
          .fontSize(12)
          .fontColor('#94A3B8')
      }
      .width('100%')
      Text(this.eventLabel(event))
        .fontSize(14)
        .fontColor(event.supported ? '#334155' : '#9A3412')
        .lineHeight(20)
      if (!event.supported) {
        Text('Unsupported in this base')
          .fontSize(12)
          .fontColor('#9A3412')
          .padding({ left: 8, right: 8, top: 4, bottom: 4 })
          .backgroundColor('#FFEDD5')
          .borderRadius(6)
          .id(`unsupported_${event.id}`)
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id(`timeline_event_${event.id}`)
  }

  private eventLabel(event: TimelineEvent): string {
    if (event.kind === TimelineEventKind.Image) {
      return `${event.body}: one attachment`;
    }
    if (event.kind === TimelineEventKind.Gallery) {
      return `${event.body}: ${event.mediaCount ?? 0} attachments`;
    }
    return event.body;
  }

  @Builder
  SettingsPanel() {
    Scroll() {
      Column({ space: 12 }) {
        Row() {
          Text(this.account.avatarInitials)
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#FFFFFF')
            .textAlign(TextAlign.Center)
            .width(48)
            .height(48)
            .borderRadius(24)
            .backgroundColor('#0F766E')
          Column({ space: 2 }) {
            Text(this.account.displayName)
              .fontSize(17)
              .fontWeight(FontWeight.Medium)
              .fontColor('#18202A')
            Text(this.account.userId)
              .fontSize(12)
              .fontColor('#64748B')
          }
          .alignItems(HorizontalAlign.Start)
          .margin({ left: 12 })
        }
        .padding(14)
        .borderRadius(8)
        .backgroundColor('#FFFFFF')
        .id('settings_account_card')

        this.SettingsRow('Notifications', 'Mentions, keywords and quiet hours', 'settings_notifications')
        this.SettingsRow('Privacy', 'Read receipts and typing notifications', 'settings_privacy')
        this.SettingsRow('Appearance', 'Theme follows the system setting', 'settings_appearance')

        if (!this.account.canSetUserStatus) {
          this.SettingsRow('User status', 'Not available in this base', 'settings_user_status_absent')
        }
      }
      .padding(16)
    }
    .id('settings_panel')
  }

  @Builder
  SettingsRow(title: string, subtitle: string, semanticId: string) {
    Column({ space: 4 }) {
      Text(title)
        .fontSize(15)
        .fontWeight(FontWeight.Medium)
        .fontColor('#0F172A')
      Text(subtitle)
        .fontSize(12)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id(semanticId)
  }

  @Builder
  SecurityPanel() {
    Scroll() {
      Column({ space: 12 }) {
        ForEach(this.securityRows, (row: string, index: number) => {
          Text(row)
            .fontSize(14)
            .fontColor(row.includes('not available') ? '#9A3412' : '#334155')
            .padding(12)
            .borderRadius(8)
            .backgroundColor('#FFFFFF')
            .id(`security_row_${index}`)
        })
      }
      .padding(16)
    }
    .id('security_panel')
  }

  @Builder
  ContractPanel() {
    Scroll() {
      Column({ space: 10 }) {
        Text('Intentionally absent')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
        ForEach(this.scenario.intentionallyAbsent, (item: string, index: number) => {
          Text(item)
            .fontSize(13)
            .fontColor('#475569')
            .lineHeight(19)
            .padding(10)
            .borderRadius(8)
            .backgroundColor('#FFFFFF')
            .id(`absent_${index}`)
        })
      }
      .alignItems(HorizontalAlign.Start)
      .padding(16)
    }
    .id('contract_panel')
  }
}
"""

    contract = json.dumps(
        {
            "task_family": base["task"],
            "android_base_tag": f"v{base['base']}",
            "ios_base_tag": f"release/{base['base']}",
            "android_final_tag": f"v{base['final']}",
            "ios_final_tag": f"release/{base['final']}",
            "arkts_sdk": 23,
            "equivalence_scope": "behavioral base equivalence for benchmark construction, not full Matrix SDK parity",
            "base_behavior_checkpoints": checkpoints,
            "intentionally_absent_until_final": absent_items,
            "semantic_ids": [
                "base_title",
                "base_release_pair",
                "timeline_panel",
                "settings_panel",
                "security_panel",
                "contract_panel",
                "settings_account_card",
                "settings_user_status_absent",
                "timeline_event_evt-001",
                "timeline_event_evt-002",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )

    return {
        "README.md": readme,
        "oh-package.json5": oh_package,
        "local.properties": local_properties,
        "build-profile.json5": build_profile,
        "hvigorfile.ts": hvigor,
        "hvigor/hvigor-config.json5": hvigor_config,
        "AppScope/app.json5": app_json,
        "AppScope/resources/base/element/string.json": app_scope_strings,
        "entry/build-profile.json5": """{
  "apiType": "stageMode",
  "buildOption": {},
  "targets": [
    {
      "name": "default"
    }
  ]
}
""",
        "entry/oh-package.json5": entry_oh_package,
        "entry/hvigorfile.ts": entry_hvigor,
        "entry/src/main/module.json5": module_json,
        "entry/src/main/ets/Application/AbilityStage.ets": ability_stage,
        "entry/src/main/ets/entryability/EntryAbility.ets": entry_ability,
        "entry/src/main/ets/model/ElementModels.ets": models,
        "entry/src/main/ets/services/MockMatrixService.ets": service,
        "entry/src/main/ets/viewmodel/ElementBaseViewModel.ets": viewmodel,
        "entry/src/main/ets/pages/Index.ets": index,
        "entry/src/main/resources/base/profile/main_pages.json": main_pages,
        "entry/src/main/resources/base/element/string.json": strings,
        "entry/src/main/resources/base/element/color.json": colors,
        "verification/behavior_contract.json": contract + "\n",
    }


def main() -> None:
    for base in BASES:
        target = ROOT / base["dir"]
        for rel, content in project_files(base).items():
            write(target / rel, content)
        icon_target = target / "AppScope/resources/base/media/app_icon.png"
        icon_target.parent.mkdir(parents=True, exist_ok=True)
        if DEVECO_PREVIEW_ICON.exists():
            shutil.copyfile(DEVECO_PREVIEW_ICON, icon_target)
            entry_icon_target = target / "entry/src/main/resources/base/media/startIcon.png"
            entry_icon_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DEVECO_PREVIEW_ICON, entry_icon_target)

    manifest = {
        "generated_for": "Element X Android/iOS base to ArkTS benchmark bases",
        "sdk": 23,
        "bases": [
            {
                "directory": base["dir"],
                "task_family": base["task"],
                "android_base_tag": f"v{base['base']}",
                "ios_base_tag": f"release/{base['base']}",
                "android_final_tag": f"v{base['final']}",
                "ios_final_tag": f"release/{base['final']}",
            }
            for base in BASES
        ],
    }
    write(ROOT / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
