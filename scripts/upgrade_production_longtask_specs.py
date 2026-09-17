#!/usr/bin/env python3
"""
Upgrade the five Element X benchmark specs and state tests to production-grade
long-horizon task descriptions.

The script is deterministic and evaluator-side. It does not infer requirements
from an agent output; it codifies the benchmark owner's acceptance contract.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
SPECS = ROOT / "specs"
STATE_TESTS = ROOT / "state_tests"


PRODUCTION_SPEC_BLOCKS = {
    "elementx-spec1-user-status.md": """## 生产级长程任务定义

### 任务定位
本任务不是在设置页添加一个静态入口，而是把 Matrix 用户状态能力作为一个端到端产品功能迁移到 ArkTS 客户端。实现需要贯通 homeserver capability 探测、当前用户资料、状态编辑器、状态更新 side effect、远端成员状态同步、房间列表摘要、用户资料页、时间线发送者区域和通话状态自动化。候选实现只有在这些状态源互相一致、失败路径可恢复、且不破坏现有设置/房间/时间线行为时，才算完成。

### 版本边界
- base: Android `v26.07.0`，用户状态不作为完整可用功能暴露；对应 ArkTS base 必须缺少 final 语义。
- final: Android `v26.08.4`，包含用户状态能力启用、feature flag 移除、`MatrixClient.isUserStatusSupported`、用户状态展示模型和时间线只展示 emoji 的行为。
- ArkTS 目标必须使用 SDK 23，并保持与 Android final 的功能边界一致；不得额外加入 Android final 没有的状态类型、设置项或社交功能。

### 生产级交付要求
- 能力探测必须是运行时状态，而不是编译期常量；失败、unsupported 和 supported-empty 三种状态要有不同 UI 收敛。
- 状态编辑器必须支持预设状态、自定义 emoji/text、取消、保存、清除、保存失败回滚和重复提交保护。
- 当前用户状态、DM 成员状态和时间线发送者状态必须使用同一语义模型，避免设置页、房间列表和资料页显示不一致。
- 时间线只允许显示状态 emoji，不允许泄露完整状态文本到消息正文或发送者行。
- 通话状态如果被映射为用户状态，必须能在通话结束后恢复或清除，不得覆盖用户手动设置的持久状态。

### 非目标与回归约束
- 不改动 Android production source；Android 只允许使用 debug/test harness 注入状态。
- 不改变账号、安全、隐私、通知、房间列表排序、未读数、时间线消息顺序和消息操作菜单。
- 不依赖 `state_test_result`、版本号、feature flag 字符串或单一 marker 判定通过。

### 验收口径
每个 testcase 必须能通过状态向量驱动到具体 UI：capability、状态 payload、编辑器模式、保存 action、目标 surface 和远端成员状态至少有一项参与断言。base/final 极性要求为 Android base fail、ArkTS base fail、Android final pass、ArkTS final pass；任何只让 `feature_available=true` 但没有渲染对应入口、badge、错误态或 transition 的实现应被判为失败。

""",
    "elementx-spec2-gallery-messages.md": """## 生产级长程任务定义

### 任务定位
本任务要求把 Matrix gallery message 从 unsupported timeline event 迁移为完整的一等消息类型。实现范围覆盖 SDK timeline item 映射、混合附件布局、缩略图与扫描状态、caption/edited caption、media viewer 数据源、回复预览、长按操作、分享/转发和 pinned event 入口。候选实现不能只显示第一张图，也不能把 gallery 当作普通单媒体消息绕过。

### 版本边界
- base: Android `v26.06.1`，gallery fixture 在关键路径中缺少完整支持，通常落入 unsupported 或单媒体分支。
- final: Android `v26.08.1`，包含 gallery messages 支持、reply preview item count、media gallery/viewer content scanner 支持和混合媒体修复。
- ArkTS 目标必须保留 Android final 的附件顺序、附件粒度错误处理和现有单媒体行为。

### 生产级交付要求
- timeline row 必须按附件粒度渲染图片、视频、音频、文件和未知 fallback，且保留 gallery 容器语义。
- caption、formatted caption、edited state 与附件列表共存，不能被 viewer 或 reply preview 丢弃。
- viewer 必须以被点击的附件 index 打开，支持边界按钮禁用、风险附件阻断和 per-item 错误状态。
- 操作菜单、回复预览、分享/转发和 pinned event 打开必须识别 gallery 语义，不得只传第一个附件。
- 内容扫描状态必须按 item 粒度传播，单个风险附件不能隐藏整条 gallery。

### 非目标与回归约束
- 不改变普通文本、单图、单视频、文件消息和现有媒体 viewer 的行为。
- 不以截图布局相似作为唯一依据；必须断言附件数量、顺序、类型、caption、安全状态和操作可用性。
- 不接受把所有 gallery 附件合并成一张静态占位图的实现。

### 验收口径
testcase 必须至少覆盖 timeline 渲染、viewer 导航、扫描阻断、reply/action/share/pinned 路径中的多个组合。base 应因缺少 gallery 一等语义而失败；final 只有在多附件结构、per-item 状态和跨入口一致性同时成立时才通过。

""",
    "elementx-spec3-active-call-timeline.md": """## 生产级长程任务定义

### 任务定位
本任务是一次时间线核心渲染升级，包含内容安全扫描保护层、媒体查看器一致性、异步媒体状态收敛和 active call rich timeline item。它横跨 timeline item factory、content validation cache、media/gallery/viewer、message shield、event action、accessibility 和 Element Call 入口。候选实现不能只新增一个 active call 卡片或一个风险占位；必须证明新增保护层不会破坏现有消息类型和时间线导航。

### 版本边界
- base: Android `v26.07.1`，缺少 final 的 timeline event content scanner 闭环和 active call timeline 富渲染。
- final: Android `v26.08.0`，包含 timeline event scanning、media gallery/viewer scanning、banned mime type 处理、AsyncImageStateHandler 修复和 active call timeline rendering。
- ArkTS 目标应把扫描状态、viewer 状态和 call 状态作为独立但可组合的 declarative state。

### 生产级交付要求
- `unknown/loading/valid/invalid/unrecoverable_error` 必须分别驱动可见 UI、可操作性和 viewer 入口。
- validation 结果要按 event/media url 缓存，滚动、重进房间、打开 viewer 后不能回退到 loading 或暴露原内容。
- gallery、voice、sticker、image、video、file 都要走同一保护策略，同时文本事件不应被错误扫描。
- active call 卡片必须展示可加入/已加入/已结束/已拒绝/缺参与者数据等状态，并调用既有通话入口。
- 新增保护层必须保留长按菜单、跳转未读、分组展开/折叠、TalkBack 语义和不同屏幕宽度下的布局稳定性。

### 非目标与回归约束
- 不改变 Matrix 事件顺序、分组策略、日期分隔符、已读/未读导航和普通消息操作。
- 不允许以隐藏整个 timeline 或禁用所有媒体交互来规避风险内容断言。
- 不接受只对 screenshot 中出现的 fixture 特判；状态必须按事件 id、media url、call id 驱动。

### 验收口径
每个 testcase 应能区分至少一种生产故障：错误展示原始风险内容、扫描结果不缓存、gallery 聚合优先级错误、viewer 状态漂移、active call 操作重复、或新增层破坏导航/可访问性。base 必须在 final 需求上失败，final 必须在安全、媒体和通话三个功能域同时通过。

""",
    "elementx-spec4-live-location.md": """## 生产级长程任务定义

### 任务定位
本任务要求把实时位置分享实现为完整客户端功能，而不是静态位置消息卡片。范围覆盖 composer 入口、thread 限制、权限/免责声明/时长选择、active share manager、定位更新、timeline live-location item、地图视图、全局/房间 banner、停止/超时、通知渲染和失败恢复。候选实现必须能处理多个房间、自己的分享与他人的分享、以及定位/发送/停止失败。

### 版本边界
- base: Android `v26.04.0`，实时位置相关基础不构成完整可用闭环，fixture 在 timeline 和启动流程上缺少 final 行为。
- final: Android `v26.05.1`，包含 share live location、thread 中禁止启动、active share 管理和 live location timeline/notification 行为。
- ArkTS 目标必须使用 Android final 的状态边界，不新增后台定位策略或地图供应商特性。

### 生产级交付要求
- composer 必须按普通房间/thread、capability、权限、免责声明和定位约束控制入口。
- 开始分享要创建 active session，并让 manager、timeline、map、banner 和通知使用同一个 session 状态。
- lastLocation 更新、暂无位置、位置过期、超时和用户停止必须分别驱动可见 UI。
- 多房间 active shares 应能区分停止一个房间和清理全部错误状态。
- 权限拒绝、权限中途撤回、定位失败、发送失败、停止失败都不能留下错误 active 状态。

### 非目标与回归约束
- 不改变静态位置分享、普通消息发送、房间 composer 其它附件入口和 thread 导航。
- 不用固定经纬度文案替代实时 state；地图和 timeline 必须响应 state transition。
- 不接受只显示 live location 字样但没有权限、时长、active manager 或 stop/timeout 逻辑的实现。

### 验收口径
testcase 必须覆盖启动前 gate、启动 side effect、timeline/map/banner 三面展示、位置更新、停止/超时、跨房间状态和异常恢复。base 应因缺失 live-location final 闭环失败；final 必须在启动、展示、更新和结束四个阶段都通过。

""",
    "elementx-spec5-link-new-device.md": """## 生产级长程任务定义

### 任务定位
本任务要求把“连接新设备”实现为受保护的生产登录流程。范围覆盖设置入口 capability、设备所有者验证、移动扫码、桌面/二维码展示、digits/确认 split steps、SDK 错误映射、超时、重试、取消、成功清理和会话列表返回。候选实现不能只展示二维码；必须保证未通过 owner gate 时永远不能暴露 QR 或继续 SDK handler。

### 版本边界
- base: Android `v26.05.0`，已有 QR/login 雏形但缺少 final 的 owner gate、timeout、split-step 完成检测和错误映射完整性。
- final: Android `v26.08.2`，包含 Protect link new device、QR login iteration、Add timeout、Disable QrCode rotation 和 timeout management 移到 flow node 等行为。
- ArkTS 目标必须与 Android final 的安全顺序一致：capability -> owner verification -> handler/QR/digits -> done/error/cleanup。

### 生产级交付要求
- capability loading/supported/unsupported/failure 四态要可见且可恢复。
- owner verification 必须支持成功、失败重试、取消、二次失败和替代认证方式；未通过前不得创建可用 QR。
- 移动扫码、桌面 notice、show QR、digits、等待确认和 done/error 必须按 SDK split step 推进。
- timeout 必须是 flow-level 状态，超时后停止无界 QR rotation，提供 retry/exit，并忽略旧 attempt 的迟到 timer 或 SDK 事件。
- already signed in、other device signed out、invalid QR、digits mismatch、continuation failure、cancellation failure 等错误要映射到安全 UI，并清理临时状态。

### 非目标与回归约束
- 不改变登录后设置页、安全页、会话列表和其它验证/加密流程。
- 不把 owner gate 降级为普通确认弹窗；它必须阻止 QR/digits/handler 可见和可操作。
- 不接受通过始终隐藏二维码来通过安全断言；supported + owner passed + QR ready 时必须展示可用路径。

### 验收口径
testcase 必须覆盖安全顺序、移动/桌面两条路径、timeout/retry、SDK 错误、stale event 忽略和完成清理。base 应因缺少 owner gate/timeout/split-step 组合失败；final 只有在安全、功能和恢复路径都满足时才通过。

""",
}


QUALITY_GATES = {
    "elementx-state-test1-user-status.yaml": """quality_gates:
  minimum_cases: 26
  required_functional_areas: [capability, editor, persistence, propagation, timeline, profile, failure_recovery]
  discrimination_rules:
    - every case is a final-positive requirement; base mirrors must fail because the semantic state or transition is absent
    - a final pass requires UI tokens from expect_ui plus transition/property checks when present
    - feature_available alone is never sufficient evidence
    - at least one mutation guard must reject a feature-flag-only implementation
""",
    "elementx-state-test2-gallery-messages.yaml": """quality_gates:
  minimum_cases: 28
  required_functional_areas: [timeline_rendering, media_viewer, content_scanning, reply_preview, action_menu, share_forward, pinned_event]
  discrimination_rules:
    - every case is a final-positive gallery requirement; base mirrors must fail because gallery remains unsupported or incomplete
    - a final pass requires preserving attachment count, order, per-item type, caption and safety state
    - single-media behavior is only a regression constraint when tied to gallery coexistence
    - feature_available alone is never sufficient evidence
""",
    "elementx-state-test3-timeline-protection-rich-events.yaml": """quality_gates:
  minimum_cases: 32
  required_functional_areas: [timeline_scanner, media_viewer, validation_cache, gallery_aggregation, active_call, action_menu, accessibility_navigation]
  discrimination_rules:
    - every case is a final-positive requirement for scanner, rich call rendering, or their coexistence
    - a final pass requires proving unsafe content is blocked without disabling safe media or text events
    - validation state must be keyed by event/media/call identity, not a global flag
    - feature_available alone is never sufficient evidence
""",
    "elementx-state-test4-live-location.yaml": """quality_gates:
  minimum_cases: 30
  required_functional_areas: [composer_gate, permission_flow, active_manager, timeline_item, map_view, banner, stop_timeout, notification, failure_recovery]
  discrimination_rules:
    - every case is a final-positive live-location requirement; base mirrors must fail because the full active-share loop is absent
    - a final pass requires state propagation between manager, timeline, map and banner
    - static location behavior is only a regression constraint when live and static items coexist
    - feature_available alone is never sufficient evidence
""",
    "elementx-state-test5-link-new-device.yaml": """quality_gates:
  minimum_cases: 34
  required_functional_areas: [capability, owner_gate, mobile_scan, desktop_qr, digits, timeout_retry, sdk_error_mapping, cleanup, stale_event_protection]
  discrimination_rules:
    - every case is a final-positive security requirement; base mirrors must fail on owner gate, timeout, split steps or cleanup
    - a final pass requires proving QR is both protected before verification and available after successful verification
    - stale timer/SDK events must be tied to attempt identity
    - feature_available alone is never sufficient evidence
""",
}


NEW_CASES = {
    "elementx-state-test1-user-status.yaml": """  - id: us_state_023_remote_status_refresh_does_not_override_own_status
    title: 远端 DM 状态刷新不覆盖自己的用户状态
    functional_area: propagation
    fixture_kind: sdk_callback_cross_surface
    base_failure_signal: base lacks independent own and remote displayed status streams
    given_state:
      support: supported
      own_status: user_set
      surface: dm_room_row
      previous_payload:
        emoji: "☕"
        text: Be right back
      remote_status:
        emoji: "🌙"
        text: Quiet hours
    expect_ui:
      visible: [home_status_badge, dm_user_status_badge]
      properties:
        home_status_badge: "☕"
        dm_user_status_badge: "🌙"
    transitions:
      - event: remote_status_refreshed(emoji=🧭, text=Travelling)
        to_state:
          remote_status:
            emoji: "🧭"
            text: Travelling
        expect_ui:
          visible: [home_status_badge, dm_user_status_badge]
          properties:
            home_status_badge: "☕"
            dm_user_status_badge: "🧭"
    parity_assertions:
      - Own status and DM member status are separate state holders on both platforms.
    mutation_guards:
      - rejects_single_global_status_bucket

  - id: us_state_024_status_text_never_leaks_to_timeline
    title: 时间线状态更新后仍只显示 emoji 不泄露文本
    functional_area: timeline
    fixture_kind: declarative_render_plus_sdk_callback
    base_failure_signal: base lacks final timeline displayed-status rendering
    given_state:
      support: supported
      own_status: user_set
      surface: timeline_sender
      sender_status:
        emoji: "🛠"
        text: Fixing an incident
    expect_ui:
      visible: [timeline_sender_name, timeline_sender_status_emoji]
      hidden: [timeline_sender_status_text, user_status_full_text_in_message_body]
      properties:
        timeline_sender_status_emoji: "🛠"
    transitions:
      - event: sender_status_refreshed(emoji=✅, text=Back online)
        to_state:
          sender_status:
            emoji: "✅"
            text: Back online
        expect_ui:
          visible: [timeline_sender_status_emoji]
          hidden: [timeline_sender_status_text, user_status_full_text_in_message_body]
          properties:
            timeline_sender_status_emoji: "✅"
    parity_assertions:
      - Status text may appear in editor/profile contexts but not in timeline sender rows.
    mutation_guards:
      - rejects_text_rendered_in_timeline

  - id: us_state_025_save_retry_after_failure_uses_latest_draft
    title: 保存失败后的重试使用最新草稿而不是失败时的旧 payload
    functional_area: failure_recovery
    fixture_kind: sdk_failure_then_user_edit
    base_failure_signal: base lacks final save/retry state machine
    given_state:
      support: supported
      own_status: user_set
      picker: custom_input
      update_action: failure
      previous_payload:
        emoji: "☕"
        text: Be right back
      status_payload:
        emoji: "🧪"
        text: Testing
    expect_ui:
      visible: [user_status_error, custom_status_text_field, save_status_button]
      enabled: [custom_status_text_field, save_status_button]
    transitions:
      - event: edit_custom_status(emoji=🚀, text=Shipping)
        to_state:
          status_payload:
            emoji: "🚀"
            text: Shipping
          update_action: idle
        expect_ui:
          visible: [save_status_button]
          properties:
            custom_status_text_field: Shipping
      - event: sdk_set_user_status_success
        to_state:
          own_status: user_set
          picker: hidden
          update_action: success
        expect_ui:
          visible: [user_status_settings_value]
          properties:
            user_status_settings_value: "🚀"
    parity_assertions:
      - Retry submits the post-edit draft, not the failed request payload.
    mutation_guards:
      - rejects_stale_retry_payload

  - id: us_state_026_call_status_restore_manual_status
    title: 通话临时状态结束后恢复进入通话前的手动状态
    functional_area: persistence
    fixture_kind: call_state_side_effect
    base_failure_signal: base lacks final in-call displayed status lifecycle
    given_state:
      support: supported
      own_status: in_call
      previous_payload:
        emoji: "📚"
        text: Reading
      surface: home_top_bar
    expect_ui:
      visible: [home_status_badge, in_call_status_badge]
      properties:
        home_status_badge: "📞"
    transitions:
      - event: call_ended_restore_previous_status
        to_state:
          own_status: user_set
          update_action: success
        expect_ui:
          visible: [home_status_badge]
          hidden: [in_call_status_badge]
          properties:
            home_status_badge: "📚"
    parity_assertions:
      - Automatic in-call status is transient and does not erase the user's persisted status.
    mutation_guards:
      - rejects_call_status_permanently_overwrites_manual_status
""",
    "elementx-state-test2-gallery-messages.yaml": """  - id: gm_state_025_gallery_order_preserved_after_validation_updates
    title: 扫描状态异步更新后 gallery 附件顺序保持不变
    functional_area: content_scanning
    fixture_kind: per_item_sdk_callback
    base_failure_signal: base lacks per-item gallery validation state
    given_state:
      gallery_support: supported
      item_count: 4
      item_mix: mixed_media
      validation: loading
      viewer: closed
      item_order: [image_a, video_b, file_c, image_d]
    expect_ui:
      visible: [gallery_container, gallery_item_0, gallery_item_1, gallery_item_2, gallery_item_3]
      properties:
        gallery_item_0: image_a
        gallery_item_1: video_b
        gallery_item_2: file_c
        gallery_item_3: image_d
    transitions:
      - event: content_validation_update(item_2=valid)
        to_state:
          validation: valid
        expect_ui:
          visible: [gallery_item_0, gallery_item_1, gallery_item_2, gallery_item_3]
          properties:
            gallery_item_0: image_a
            gallery_item_1: video_b
            gallery_item_2: file_c
            gallery_item_3: image_d
    parity_assertions:
      - Validation completion must not sort, drop, or regroup gallery items.
    mutation_guards:
      - rejects_validation_reorders_gallery_items

  - id: gm_state_026_viewer_reuses_timeline_caption_and_edited_state
    title: viewer 中保留 timeline gallery caption 与 edited 状态
    functional_area: media_viewer
    fixture_kind: navigation_state_projection
    base_failure_signal: base lacks gallery-aware viewer data source
    given_state:
      gallery_support: supported
      item_count: 2
      item_mix: visual_only
      caption: formatted
      edited: true
      validation: valid
      viewer: closed
    expect_ui:
      visible: [gallery_container, gallery_caption, edited_indicator]
    transitions:
      - event: gallery_item_click(index=0)
        to_state:
          viewer: opened_selected_item
        expect_ui:
          visible: [media_viewer, media_viewer_caption, media_viewer_edited_indicator]
          properties:
            media_viewer_caption: formatted_caption
    parity_assertions:
      - Viewer data source inherits the same caption model as the timeline row.
    mutation_guards:
      - rejects_viewer_drops_gallery_caption

  - id: gm_state_027_redacted_gallery_hides_media_but_keeps_event_shell
    title: gallery 被撤回后隐藏媒体内容但保留事件壳层
    functional_area: timeline_rendering
    fixture_kind: event_replacement_state
    base_failure_signal: base lacks gallery event replacement handling
    given_state:
      gallery_support: supported
      item_count: 4
      item_mix: mixed_media
      event_replacement: redacted
      viewer: closed
    expect_ui:
      visible: [redacted_event_placeholder]
      hidden: [gallery_item_0, gallery_item_1, gallery_item_2, gallery_item_3, media_viewer]
      disabled: [gallery_container]
    parity_assertions:
      - Redaction applies to the gallery event, not to an arbitrary first item only.
    mutation_guards:
      - rejects_redacted_gallery_still_opens_media

  - id: gm_state_028_share_skips_blocked_items_but_reports_omissions
    title: 分享 gallery 时跳过被阻断附件并提示部分附件不可分享
    functional_area: share_forward
    fixture_kind: action_sheet_with_per_item_validation
    base_failure_signal: base lacks gallery-aware share payload assembly
    given_state:
      gallery_support: supported
      item_count: 4
      item_mix: mixed_media
      validation_by_item:
        item_0: valid
        item_1: invalid
        item_2: valid
        item_3: unrecoverable_error
      viewer: closed
    expect_ui:
      visible: [gallery_container]
    transitions:
      - event: share_gallery_event
        to_state:
          share_payload_count: 2
          blocked_share_count: 2
        expect_ui:
          visible: [share_sheet, gallery_share_partial_warning]
          hidden: [unsafe_media_in_share_sheet]
          properties:
            share_payload_count: 2
    parity_assertions:
      - Share payload preserves safe attachments and explains omitted unsafe attachments.
    mutation_guards:
      - rejects_sharing_all_items_without_validation
""",
    "elementx-state-test3-timeline-protection-rich-events.yaml": """  - id: tp_state_029_validation_cache_survives_scroll_rebind
    title: 已验证媒体滚动重绑后不回退到扫描中
    functional_area: validation_cache
    fixture_kind: timeline_rebind
    base_failure_signal: base lacks final content validation cache
    given_state:
      protection: render_all
      validation: valid
      event_content: image
      viewer: closed
      event_id: evt_media_cached
    expect_ui:
      visible: [image_thumbnail]
      hidden: [content_scanning_placeholder, unsafe_content_warning]
    transitions:
      - event: timeline_row_rebound(event_id=evt_media_cached)
        to_state:
          validation: valid
        expect_ui:
          visible: [image_thumbnail]
          hidden: [content_scanning_placeholder, unsafe_content_warning]
    parity_assertions:
      - Validation state is keyed by event/media identity and reused after row rebind.
    mutation_guards:
      - rejects_global_loading_reset_on_scroll

  - id: tp_state_030_mixed_timeline_scanner_does_not_block_text
    title: 同屏风险媒体不会阻断普通文本事件
    functional_area: timeline_scanner
    fixture_kind: mixed_timeline_fixture
    base_failure_signal: base lacks final mixed scanner rendering
    given_state:
      protection: render_all
      validation: invalid
      event_content: mixed_text_and_image
      viewer: closed
    expect_ui:
      visible: [text_event_body, unsafe_content_warning, blocked_media_placeholder]
      hidden: [raw_media_content]
      enabled: [text_event_action_menu]
    parity_assertions:
      - Scanner protection is scoped to media events and keeps text interactions intact.
    mutation_guards:
      - rejects_hiding_entire_timeline_for_invalid_media

  - id: tp_state_031_active_call_end_update_removes_join_action
    title: 活跃通话结束事件到达后卡片移除加入入口
    functional_area: active_call
    fixture_kind: call_state_sdk_callback
    base_failure_signal: base lacks active call rich timeline state updates
    given_state:
      protection: render_all
      validation: valid
      event_content: active_call
      call_state: active_joinable
      viewer: closed
    expect_ui:
      visible: [active_call_card, active_call_join_button]
      enabled: [active_call_join_button]
    transitions:
      - event: active_call_state_update(ended)
        to_state:
          call_state: started_tombstoned
        expect_ui:
          visible: [active_call_card, active_call_ended_label]
          hidden: [active_call_join_button]
    parity_assertions:
      - Active call state updates replace card affordances without replacing the timeline event.
    mutation_guards:
      - rejects_stale_join_button_after_call_end

  - id: tp_state_032_blocked_media_details_action_without_download
    title: 被阻断媒体可查看详情但不能下载或播放
    functional_area: action_menu
    fixture_kind: protected_action_sheet
    base_failure_signal: base lacks protected media action filtering
    given_state:
      protection: render_all
      validation: invalid
      event_content: video
      viewer: blocked
    expect_ui:
      visible: [unsafe_content_warning, blocked_media_placeholder]
      hidden: [video_play_affordance]
    transitions:
      - event: long_press_blocked_media
        to_state:
          action_sheet: opened
        expect_ui:
          visible: [message_details_action, report_content_action]
          hidden: [download_media_action, play_media_action, share_media_action]
    parity_assertions:
      - Protected media retains safe event actions while removing content-exposing actions.
    mutation_guards:
      - rejects_action_menu_exposes_blocked_media
""",
    "elementx-state-test4-live-location.yaml": """  - id: ll_state_027_permission_revoked_mid_share_stops_manager
    title: 分享中途定位权限被撤回会停止 manager 并提示用户
    functional_area: failure_recovery
    fixture_kind: runtime_permission_change
    base_failure_signal: base lacks active share permission revocation handling
    given_state:
      room_context: room
      permission: granted
      active_share: own_active
      map: open
      timeline_item: live_active
    expect_ui:
      visible: [live_location_banner, live_location_map, stop_live_location_button]
    transitions:
      - event: permission_revoked_while_sharing
        to_state:
          permission: denied
          active_share: none
          timeline_item: live_ended
        expect_ui:
          visible: [live_location_permission_error, live_location_ended_label]
          hidden: [live_location_banner, stop_live_location_button]
    parity_assertions:
      - Permission revocation cleans local active state and updates timeline/map surfaces.
    mutation_guards:
      - rejects_active_share_left_running_without_permission

  - id: ll_state_028_background_resume_uses_latest_location
    title: 后台恢复后 timeline 和地图使用最新 lastLocation
    functional_area: active_manager
    fixture_kind: lifecycle_resume_with_manager_snapshot
    base_failure_signal: base lacks active manager state resumption
    given_state:
      room_context: room
      permission: granted
      active_share: own_active
      map: closed
      last_location:
        lat: 48.8566
        lon: 2.3522
        age: fresh
    expect_ui:
      visible: [live_location_banner, live_location_timeline_card]
      properties:
        live_location_timeline_coordinates: "48.8566,2.3522"
    transitions:
      - event: app_resumed_with_last_location(lat=52.52, lon=13.405)
        to_state:
          last_location:
            lat: 52.52
            lon: 13.405
            age: fresh
        expect_ui:
          visible: [live_location_banner, live_location_timeline_card]
          properties:
            live_location_timeline_coordinates: "52.52,13.405"
    parity_assertions:
      - Resumed UI uses manager snapshot instead of stale timeline fixture data.
    mutation_guards:
      - rejects_stale_location_after_resume

  - id: ll_state_029_notification_tap_routes_to_live_location_room
    title: 实时位置通知点击返回对应房间和地图入口
    functional_area: notification
    fixture_kind: notification_intent_routing
    base_failure_signal: base lacks live-location notification semantics
    given_state:
      active_share: remote_active
      notification: live_location_started
      room_id: room_b
      map: closed
    expect_ui:
      visible: [live_location_notification_label]
    transitions:
      - event: tap_live_location_notification(room_b)
        to_state:
          surface: room_timeline
          room_id: room_b
        expect_ui:
          visible: [room_timeline, live_location_timeline_card, open_live_location_map]
    parity_assertions:
      - Notification routing carries the room id and lands on the live-location event context.
    mutation_guards:
      - rejects_notification_opens_generic_home_only

  - id: ll_state_030_location_staleness_changes_map_affordance
    title: 位置过期后地图显示 stale 状态且不误报实时
    functional_area: map_view
    fixture_kind: timer_tick_with_location_age
    base_failure_signal: base lacks live-location freshness state
    given_state:
      active_share: remote_active
      map: open
      timeline_item: live_active
      last_location:
        lat: 37.7749
        lon: -122.4194
        age: fresh
    expect_ui:
      visible: [live_location_map, live_location_fresh_indicator]
      hidden: [live_location_stale_indicator]
    transitions:
      - event: time_tick(location_age=stale)
        to_state:
          last_location:
            lat: 37.7749
            lon: -122.4194
            age: stale
        expect_ui:
          visible: [live_location_map, live_location_stale_indicator]
          hidden: [live_location_fresh_indicator]
    parity_assertions:
      - Location freshness is rendered from state and not hardcoded as always live.
    mutation_guards:
      - rejects_always_fresh_live_location_label
""",
    "elementx-state-test5-link-new-device.yaml": """  - id: lnd_state_031_biometric_lockout_falls_back_to_device_pin
    title: 生物识别锁定后可切换系统凭据或应用 PIN 继续验证
    functional_area: owner_gate
    fixture_kind: owner_verification_error_recovery
    base_failure_signal: base lacks protected owner verification fallback flow
    given_state:
      support: supported
      owner_verification: failed
      flow_mode: none
      auth_error: biometric_lockout
      qr_data: none
    expect_ui:
      visible: [owner_verification_gate, owner_verification_error, use_device_credential_action]
      hidden: [qr_code_view, digits_view]
      enabled: [use_device_credential_action, cancel_owner_verification]
    transitions:
      - event: device_credential_success
        to_state:
          owner_verification: passed
          flow_mode: mobile_scan
        expect_ui:
          visible: [scan_qr_code_view, scan_security_warning]
          hidden: [owner_verification_gate]
    parity_assertions:
      - Lockout recovery still enforces owner gate before any QR surface.
    mutation_guards:
      - rejects_biometric_failure_skips_owner_gate

  - id: lnd_state_032_stale_sdk_done_ignored_after_timeout_retry
    title: 超时重试后旧 attempt 的 SDK 完成事件被忽略
    functional_area: stale_event_protection
    fixture_kind: attempt_scoped_sdk_callback
    base_failure_signal: base lacks flow-level attempt identity
    given_state:
      support: supported
      owner_verification: passed
      flow_mode: show_qr
      qr_data: available
      timeout: expired
      attempt_id: old_attempt
    expect_ui:
      visible: [timeout_notice, retry_link_new_device]
      hidden: [success_view]
    transitions:
      - event: retry_link_new_device
        to_state:
          flow_mode: show_qr
          qr_data: loading
          timeout: running
          attempt_id: new_attempt
        expect_ui:
          visible: [qr_code_loading]
          hidden: [timeout_notice, success_view]
      - event: sdk_step_done(attempt_id=old_attempt)
        to_state:
          flow_mode: show_qr
          qr_data: loading
          timeout: running
          attempt_id: new_attempt
        expect_ui:
          visible: [qr_code_loading]
          hidden: [success_view, timeout_notice]
    parity_assertions:
      - SDK callbacks are ignored when their attempt id no longer matches the active flow.
    mutation_guards:
      - rejects_stale_done_completes_new_attempt

  - id: lnd_state_033_desktop_digits_mismatch_keeps_timeout_and_allows_retry
    title: 桌面验证码不匹配保留安全超时并允许重试
    functional_area: digits
    fixture_kind: sdk_error_mapping_with_timer
    base_failure_signal: base lacks split-step digits and timeout composition
    given_state:
      support: supported
      owner_verification: passed
      flow_mode: digits
      qr_data: available
      timeout: running
      digits_match: pending
    expect_ui:
      visible: [digits_view, cancel_link_new_device]
      hidden: [success_view]
    transitions:
      - event: sdk_digits_mismatch
        to_state:
          flow_mode: error
          timeout: running
          digits_match: mismatch
        expect_ui:
          visible: [digits_mismatch_error, try_again]
          hidden: [success_view, qr_code_view]
      - event: try_again
        to_state:
          flow_mode: desktop_notice
          qr_data: loading
          timeout: running
        expect_ui:
          visible: [desktop_notice_view, qr_code_loading]
          hidden: [digits_mismatch_error]
    parity_assertions:
      - Digits errors map to recoverable UI without dropping the active timeout policy.
    mutation_guards:
      - rejects_digits_error_without_recoverable_retry

  - id: lnd_state_034_cancel_during_qr_generation_cleans_handler
    title: 二维码生成中取消会清理 handler、timer 和临时 QR 数据
    functional_area: cleanup
    fixture_kind: cancellation_during_async_qr_loading
    base_failure_signal: base lacks final cancellation cleanup in QR flow
    given_state:
      support: supported
      owner_verification: passed
      flow_mode: show_qr
      qr_data: loading
      timeout: running
      handler_state: active
    expect_ui:
      visible: [qr_code_loading, cancel_link_new_device]
      hidden: [success_view]
    transitions:
      - event: cancel_link_new_device
        to_state:
          flow_mode: none
          qr_data: none
          timeout: not_started
          handler_state: cleaned
        expect_ui:
          visible: [security_settings_entry]
          hidden: [qr_code_loading, qr_code_view, timeout_notice, success_view]
    parity_assertions:
      - Cancellation before QR success cleans the same resources as cancellation after QR success.
    mutation_guards:
      - rejects_cancel_leaves_active_qr_handler
""",
}


EXTRA_STATE_DIMENSIONS = {
    "elementx-state-test1-user-status.yaml": [
        ("remote_status", "[none, user_set, refreshed, removed]"),
        ("status_payload_source", "[none, draft, persisted, transient_call]"),
    ],
    "elementx-state-test2-gallery-messages.yaml": [
        ("item_order", "[stable, reordered_bug]"),
        ("event_replacement", "[none, edited, redacted]"),
        ("validation_by_item", "[all_valid, mixed_valid_invalid, partial_error]"),
        ("share_payload_count", "[0, 1, 2, 4]"),
    ],
    "elementx-state-test3-timeline-protection-rich-events.yaml": [
        ("validation_cache", "[empty, cached_valid, cached_invalid]"),
        ("action_sheet", "[closed, opened]"),
        ("event_identity", "[single_event, mixed_text_and_media, cached_media, active_call]"),
    ],
    "elementx-state-test4-live-location.yaml": [
        ("active_share", "[none, own_active, remote_active, multiple_active]"),
        ("timeline_item", "[none, live_active, live_ended, static_location]"),
        ("last_location", "[none, fresh, stale]"),
        ("notification", "[none, live_location_started]"),
        ("surface", "[composer, room_timeline, map, banner, notification]"),
    ],
    "elementx-state-test5-link-new-device.yaml": [
        ("attempt_id", "[none, old_attempt, new_attempt]"),
        ("auth_error", "[none, biometric_failure, biometric_lockout]"),
        ("digits_match", "[pending, match, mismatch]"),
        ("handler_state", "[none, active, cleaned]"),
    ],
}


RUNTIME_ORACLE_BLOCK = [
    "    runtime_oracle:",
    "      state_vector: true",
    "      ui_tree_tokens: true",
    "      transition_steps: auto",
    "      cross_platform_parity: true",
]

EXACT_AREAS = {
    "us_state_023_remote_status_refresh_does_not_override_own_status": "propagation",
    "us_state_024_status_text_never_leaks_to_timeline": "timeline",
    "us_state_025_save_retry_after_failure_uses_latest_draft": "failure_recovery",
    "us_state_026_call_status_restore_manual_status": "persistence",
    "gm_state_025_gallery_order_preserved_after_validation_updates": "content_scanning",
    "gm_state_026_viewer_reuses_timeline_caption_and_edited_state": "media_viewer",
    "gm_state_027_redacted_gallery_hides_media_but_keeps_event_shell": "timeline_rendering",
    "gm_state_028_share_skips_blocked_items_but_reports_omissions": "share_forward",
    "tp_state_029_validation_cache_survives_scroll_rebind": "validation_cache",
    "tp_state_030_mixed_timeline_scanner_does_not_block_text": "timeline_scanner",
    "tp_state_031_active_call_end_update_removes_join_action": "active_call",
    "tp_state_032_blocked_media_details_action_without_download": "action_menu",
    "ll_state_027_permission_revoked_mid_share_stops_manager": "failure_recovery",
    "ll_state_028_background_resume_uses_latest_location": "active_manager",
    "ll_state_029_notification_tap_routes_to_live_location_room": "notification",
    "ll_state_030_location_staleness_changes_map_affordance": "map_view",
    "lnd_state_031_biometric_lockout_falls_back_to_device_pin": "owner_gate",
    "lnd_state_032_stale_sdk_done_ignored_after_timeout_retry": "stale_event_protection",
    "lnd_state_033_desktop_digits_mismatch_keeps_timeout_and_allows_retry": "digits",
    "lnd_state_034_cancel_during_qr_generation_cleans_handler": "cleanup",
}


def insert_after_title(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if "## 生产级长程任务定义" in text:
        return
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"Empty spec: {path}")
    new_text = "\n".join([lines[0], "", block.rstrip(), *lines[1:]]) + "\n"
    path.write_text(new_text, encoding="utf-8")


def ensure_quality_gates(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if "\nquality_gates:\n" in f"\n{text}":
        return
    marker = "\ncases:\n"
    if marker not in text:
        raise ValueError(f"cases marker missing in {path}")
    text = text.replace(marker, "\n" + block.rstrip() + "\n" + marker.lstrip(), 1)
    path.write_text(text, encoding="utf-8")


def ensure_extra_dimensions(path: Path, dimensions: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    additions = []
    for name, values in dimensions:
        if f"  - name: {name}\n" not in text:
            additions.extend([f"  - name: {name}", f"    values: {values}"])
    if not additions:
        return
    marker = "\nquality_gates:\n"
    if marker not in text:
        raise ValueError(f"quality_gates marker missing in {path}")
    text = text.replace(marker, "\n" + "\n".join(additions) + marker, 1)
    path.write_text(text, encoding="utf-8")


def append_cases(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    first_case_id = block.splitlines()[0].split(":", 1)[1].strip()
    if first_case_id in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + block.rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def add_case_metadata(path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")

    lines = text.splitlines()
    out: list[str] = []
    in_cases = False
    current_case = ""
    current_case_has_runtime = False
    for raw in lines:
        if in_cases and raw.startswith("  - id:"):
            if current_case and not current_case_has_runtime:
                out.extend(RUNTIME_ORACLE_BLOCK)
            current_case = raw.strip().split(":", 1)[1].strip()
            current_case_has_runtime = False
        out.append(raw)
        stripped = raw.strip()
        if stripped == "cases:":
            in_cases = True
            continue
        if in_cases and current_case and stripped == "runtime_oracle:":
            current_case_has_runtime = True
            continue
        if in_cases and current_case and raw.startswith("    title:"):
            next_has_area = False
            # Existing cases from an earlier run already have the metadata block.
            # New appended cases can define a hand-authored functional_area, so do
            # not duplicate it here.
            index = len(out)
            if index < len(lines) and lines[index].startswith("    functional_area:"):
                next_has_area = True
            if next_has_area:
                continue
            area = infer_area(current_case)
            fixture = infer_fixture(current_case)
            out.extend([
                f"    functional_area: {area}",
                f"    fixture_kind: {fixture}",
                "    base_failure_signal: base target lacks the final semantic state, transition, or UI binding required by this case",
                *RUNTIME_ORACLE_BLOCK,
                "    mutation_guards:",
                "      - rejects_feature_flag_only_completion",
                f"      - rejects_missing_{area}_binding",
            ])
    if current_case and not current_case_has_runtime:
        out.extend(RUNTIME_ORACLE_BLOCK)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def normalize_case_metadata(path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    marker = "\ncases:\n"
    if marker not in text:
      raise ValueError(f"cases marker missing in {path}")
    prefix, cases_text = text.split(marker, 1)
    lines = cases_text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("  - id:")]
    normalized_blocks: list[str] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        block = lines[start:end]
        case_id = block[0].strip().split(":", 1)[1].strip()
        fixtures = [line.strip().split(":", 1)[1].strip() for line in block if line.startswith("    fixture_kind:")]
        failures = [line.strip().split(":", 1)[1].strip() for line in block if line.startswith("    base_failure_signal:")]
        area = infer_area(case_id)
        fixture = fixtures[-1] if fixtures else infer_fixture(case_id)
        failure = failures[-1] if failures else "base target lacks the final semantic state, transition, or UI binding required by this case"
        guards = [
            guard for guard in collect_mutation_guards(block)
            if not guard.startswith("rejects_missing_") or guard == f"rejects_missing_{area}_binding"
        ]
        for required_guard in ("rejects_feature_flag_only_completion", f"rejects_missing_{area}_binding"):
            if required_guard not in guards:
                guards.insert(0 if required_guard == "rejects_feature_flag_only_completion" else len(guards), required_guard)

        cleaned: list[str] = []
        skip_child_of: str | None = None
        for line in block:
            if skip_child_of:
                if line.startswith("      ") or not line.strip():
                    continue
                skip_child_of = None
            if line.startswith("    functional_area:") or line.startswith("    fixture_kind:") or line.startswith("    base_failure_signal:"):
                continue
            if line.startswith("    runtime_oracle:"):
                skip_child_of = "runtime_oracle"
                continue
            if line.startswith("    mutation_guards:"):
                skip_child_of = "mutation_guards"
                continue
            cleaned.append(line)

        rebuilt: list[str] = []
        inserted = False
        for line in cleaned:
            rebuilt.append(line)
            if not inserted and line.startswith("    title:"):
                rebuilt.extend([
                    f"    functional_area: {area}",
                    f"    fixture_kind: {fixture}",
                    f"    base_failure_signal: {failure}",
                    *RUNTIME_ORACLE_BLOCK,
                    "    mutation_guards:",
                ])
                rebuilt.extend(f"      - {guard}" for guard in guards)
                inserted = True
        normalized_blocks.append("\n".join(rebuilt).rstrip())
    path.write_text(prefix.rstrip() + marker + "\n\n".join(normalized_blocks) + "\n", encoding="utf-8")


def collect_mutation_guards(block: list[str]) -> list[str]:
    guards: list[str] = []
    in_guards = False
    for line in block:
        if line.startswith("    mutation_guards:"):
            in_guards = True
            continue
        if in_guards:
            if line.startswith("      - "):
                guard = line.strip().removeprefix("- ").strip()
                if guard not in guards:
                    guards.append(guard)
                continue
            if line.startswith("      ") or not line.strip():
                continue
            in_guards = False
    return guards


def infer_area(case_id: str) -> str:
    if case_id in EXACT_AREAS:
        return EXACT_AREAS[case_id]
    if case_id.startswith("gm_state_"):
        mappings = [
            ("viewer", "media_viewer"),
            ("validation", "content_scanning"),
            ("invalid", "content_scanning"),
            ("thumbnail", "content_scanning"),
            ("error", "content_scanning"),
            ("reply", "reply_preview"),
            ("action", "action_menu"),
            ("share", "share_forward"),
            ("pinned", "pinned_event"),
        ]
        for needle, area in mappings:
            if needle in case_id:
                return area
        return "timeline_rendering"
    if case_id.startswith("tp_state_"):
        mappings = [
            ("active_call", "active_call"),
            ("call", "active_call"),
            ("accessibility", "accessibility_navigation"),
            ("navigation", "accessibility_navigation"),
            ("action", "action_menu"),
            ("viewer", "media_viewer"),
            ("cache", "validation_cache"),
            ("gallery", "gallery_aggregation"),
            ("scanner", "timeline_scanner"),
            ("validation", "timeline_scanner"),
            ("media", "timeline_scanner"),
            ("invalid", "timeline_scanner"),
            ("banned", "timeline_scanner"),
            ("voice", "timeline_scanner"),
            ("sticker", "timeline_scanner"),
        ]
        for needle, area in mappings:
            if needle in case_id:
                return area
        return "timeline_scanner"
    if case_id.startswith("ll_state_"):
        mappings = [
            ("permission", "permission_flow"),
            ("thread", "composer_gate"),
            ("room_entry", "composer_gate"),
            ("capability", "composer_gate"),
            ("disclaimer", "composer_gate"),
            ("constraints", "composer_gate"),
            ("manager", "active_manager"),
            ("map", "map_view"),
            ("banner", "banner"),
            ("notification", "notification"),
            ("timeout", "stop_timeout"),
            ("stop", "stop_timeout"),
            ("failure", "failure_recovery"),
            ("error", "failure_recovery"),
        ]
        for needle, area in mappings:
            if needle in case_id:
                return area
        return "timeline_item"
    if case_id.startswith("lnd_state_"):
        mappings = [
            ("support", "capability"),
            ("owner", "owner_gate"),
            ("biometric", "owner_gate"),
            ("mobile", "mobile_scan"),
            ("scan", "mobile_scan"),
            ("desktop", "desktop_qr"),
            ("qr", "desktop_qr"),
            ("digits", "digits"),
            ("stale", "stale_event_protection"),
            ("timeout", "timeout_retry"),
            ("retry", "timeout_retry"),
            ("sdk", "sdk_error_mapping"),
            ("error", "sdk_error_mapping"),
            ("complete", "cleanup"),
            ("cancel", "cleanup"),
            ("cleanup", "cleanup"),
        ]
        for needle, area in mappings:
            if needle in case_id:
                return area
        return "capability"
    mappings = [
        ("unsupported", "capability"),
        ("support", "capability"),
        ("entry", "capability"),
        ("custom", "editor"),
        ("picker", "editor"),
        ("save", "persistence"),
        ("clear", "persistence"),
        ("timeline", "timeline"),
        ("profile", "profile"),
        ("dm_", "propagation"),
        ("remote", "propagation"),
        ("gallery", "timeline_rendering"),
        ("viewer", "media_viewer"),
        ("validation", "content_scanning"),
        ("scan", "content_scanning"),
        ("reply", "reply_preview"),
        ("action", "action_menu"),
        ("share", "share_forward"),
        ("pinned", "pinned_event"),
        ("cache", "validation_cache"),
        ("call", "active_call"),
        ("accessibility", "accessibility_navigation"),
        ("permission", "permission_flow"),
        ("manager", "active_manager"),
        ("map", "map_view"),
        ("banner", "banner"),
        ("timeout", "timeout_retry"),
        ("notification", "notification"),
        ("owner", "owner_gate"),
        ("qr", "desktop_qr"),
        ("digits", "digits"),
        ("cleanup", "cleanup"),
        ("stale", "stale_event_protection"),
    ]
    for needle, area in mappings:
        if needle in case_id:
            return area
    return "cross_surface"


def infer_fixture(case_id: str) -> str:
    if any(item in case_id for item in ("failure", "error", "invalid", "unrecoverable")):
        return "sdk_failure_fixture"
    if any(item in case_id for item in ("timeout", "timer", "stale", "expiry")):
        return "timer_fixture"
    if any(item in case_id for item in ("click", "tap", "open", "long_press", "action", "share", "reply", "retry", "cancel")):
        return "event_transition_fixture"
    if any(item in case_id for item in ("refresh", "update", "manager", "call", "permission")):
        return "sdk_callback_fixture"
    return "declarative_state_fixture"


def main() -> int:
    for filename, block in PRODUCTION_SPEC_BLOCKS.items():
        insert_after_title(SPECS / filename, block)
    for filename, block in QUALITY_GATES.items():
        path = STATE_TESTS / filename
        ensure_quality_gates(path, block)
        ensure_extra_dimensions(path, EXTRA_STATE_DIMENSIONS[filename])
        add_case_metadata(path)
    for filename, block in NEW_CASES.items():
        append_cases(STATE_TESTS / filename, block)
    for path in sorted(STATE_TESTS.glob("elementx-state-test*.yaml")):
        normalize_case_metadata(path)
    print("Production long-task specs and state tests upgraded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
