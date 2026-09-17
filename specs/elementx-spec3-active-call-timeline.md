# 时间线安全扫描与富事件渲染升级（v26.07.1 -> v26.08.0）

## 生产级长程任务定义

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

## 场景一

### 场景概述

房间时间线需要接入内容安全扫描能力。base 版本已有普通文本、媒体、gallery 和部分通话通知基础能力，但缺少对 timeline event 的统一内容扫描、风险态展示和缓存处理；final 版本根据 release note 中 “Content scanner: scan timeline events for unsafe content”、后续 banned mime type 修复，以及媒体 gallery/viewer 的 content scanner 支持，需要在时间线模型、presenter、保护层和媒体 UI 中形成完整闭环。

### 场景逻辑步骤

- 1. 用户进入包含文本、图片、视频、文件、贴纸、语音和 gallery 消息的房间时间线。
- 2. 客户端为需要扫描的 timeline event 创建内容验证请求，并避免对不需要扫描的事件重复发起检查。
- 3. 扫描中时，受影响的消息展示扫描中或受保护状态，不直接暴露待验证内容。
- 4. 扫描通过后，消息恢复为原本的文本、图片、视频、文件、贴纸、语音或 gallery 渲染。
- 5. 扫描失败、内容缺失、风险内容或 banned mime type 命中时，消息展示对应的安全 fallback。
- 6. 内容扫描结果需要被缓存，用户滚动时间线、返回房间或重新进入媒体查看器时不应重复闪烁。
- 7. 扫描状态变化只刷新相关消息，不改变时间线中其它事件的顺序、分组和日期分隔。
- 8. 如果内容扫描服务不可用，客户端按 final 版本策略安全降级，不导致时间线崩溃。

## 场景二

### 场景概述

内容安全状态需要贯穿媒体消息、gallery 和媒体查看器。该需求覆盖 release note 和 commits 中的 “Add content scanner support to media gallery and viewer”、媒体查看器 invalid state 修复、`AsyncImageStateHandler` 等变更，要求用户从时间线进入详情页时看到一致的安全结果。

### 场景逻辑步骤

- 1. 用户点击时间线中的图片、视频、文件、语音或 gallery 条目。
- 2. 如果该媒体仍在扫描中，媒体查看器展示扫描中状态，并阻止直接展示原始内容。
- 3. 如果扫描结果为安全，媒体查看器按对应媒体类型展示内容。
- 4. 如果扫描结果为风险、缺失、加载失败或 banned mime type，媒体查看器展示与时间线一致的安全错误状态。
- 5. 对 gallery 消息，客户端按附件粒度处理扫描结果，不因为某一个附件失败而隐藏整个 gallery。
- 6. 对不是由 timeline event 打开的媒体，媒体查看器不能错误地显示 timeline event 专属的 invalid state。
- 7. 缩略图和原图加载状态由统一的异步图片状态处理逻辑收敛，避免出现加载完成后仍停留在占位态。
- 8. 用户从媒体查看器返回后，时间线仍停留在原消息附近，并保留对应扫描状态。

## 场景三

### 场景概述

时间线需要新增活跃通话事件的富渲染。base 版本中 call event fixture 存在但显示为 unsupported；final 版本根据 release note 中 “feat(call): Active call timeline rendering” 及对应截图、预览和 timeline item 变更，需要渲染专门的活跃通话卡片，并接入通话入口。

### 场景逻辑步骤

- 1. 用户进入包含活跃通话事件的房间时间线。
- 2. 客户端将 SDK 返回的 active call timeline item 映射为受支持的 UI 类型。
- 3. 时间线展示活跃通话卡片，而不是 unsupported 消息。
- 4. 卡片展示通话标题、通话状态、参与者头像或人数等关键信息。
- 5. 当通话仍处于可加入状态时，卡片展示加入通话操作。
- 6. 用户点击加入操作后，客户端调用既有 Element Call 入口打开对应通话。
- 7. 当通话被拒绝、结束或不可加入时，卡片更新为对应状态，并隐藏或禁用加入操作。
- 8. 通话卡片与普通消息共处时，时间顺序、分组、头像和发送者上下文保持一致。

## 场景四

### 场景概述

本次时间线升级还需要保持已有消息交互和可访问性质量。final 版本窗口内包含 timeline row、event content factory、message bubble、group header、content padding 和 TalkBack/展开折叠提示相关变更；因此实现不能只让新增内容“能显示”，还要与原时间线行为协同。

### 场景逻辑步骤

- 1. 用户在同一房间内浏览普通文本、回复、反应、媒体、gallery、扫描受保护消息和活跃通话卡片。
- 2. 时间线 row factory 根据事件类型选择正确 content renderer，不应把已支持类型降级为 unsupported。
- 3. 消息气泡、内容 padding、发送者区域和分组布局在连续消息、回复消息和状态事件之间保持稳定。
- 4. 用户长按任意支持的消息时，操作菜单仍能打开，并根据消息类型展示可用操作。
- 5. 展开或折叠时间线分组时，辅助功能读出正确的 expanded/collapsed 状态。
- 6. 屏幕阅读器开启时，消息阅读顺序不应被新增扫描层、保护层或通话卡片打乱。
- 7. 浅色、深色和不同屏幕宽度下，扫描 fallback、媒体项和活跃通话卡片均不出现文字重叠或按钮溢出。
- 8. 新增安全扫描和活跃通话渲染不得改变“跳转未读”“标记已读”“返回房间”等已有时间线导航行为。
