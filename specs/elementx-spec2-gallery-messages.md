# 图库消息渲染与操作（v26.06.1 -> v26.08.1）

## 生产级长程任务定义

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

## 场景一

### 场景概述

时间线需要支持 Matrix gallery messages。base 版本中 gallery fixture 会落入 unsupported 内容；final 版本根据 release note 中 “Support gallery messages”、gallery message 合并、混合媒体修复和内容扫描集成等变更，需要将多附件消息作为一类受支持的时间线内容渲染。

### 场景逻辑步骤

- 1. 用户进入包含 gallery message 的房间时间线。
- 2. 客户端识别 gallery 消息中的多个附件条目，不再显示 unsupported 占位。
- 3. 多个图片、视频或文件附件按照 Android final 版本的顺序组成 gallery 布局。
- 4. 当 gallery 中存在混合类型附件时，所有可支持条目都应被渲染，不应只显示第一项或过滤掉非图片项。
- 5. 每个条目的缩略图、媒体类型、加载状态和必要的元信息保持可见。
- 6. gallery 消息存在 caption 或关联正文时，正文与媒体布局按 final 版本规则展示。
- 7. gallery 消息与普通文本、单图、单视频消息共同出现时，时间线顺序和间距保持一致。
- 8. 当媒体缩略图加载失败时，只影响对应条目，不应导致整条 gallery 消息消失。

## 场景二

### 场景概述

用户需要能从 gallery 消息进入媒体查看器，并在查看器中浏览对应附件。final 版本还包含内容扫描和媒体优化选择的相关变更，因此查看器需要继承单媒体消息已有的安全状态、加载状态和用户选择。

### 场景逻辑步骤

- 1. 用户点击 gallery 消息中的任意媒体条目。
- 2. 客户端打开媒体查看器，并定位到被点击的条目。
- 3. 用户可以在同一 gallery 的附件之间切换，顺序与时间线展示一致。
- 4. 图片、视频和可预览文件分别使用已有单媒体预览能力。
- 5. 当内容扫描状态为扫描中、风险内容或失败时，媒体查看器展示与单媒体消息一致的安全提示。
- 6. 当用户选择查看或优化某个媒体条目时，该选择只作用于对应媒体，不错误影响其它条目。
- 7. 如果 gallery 数据源加载某个条目失败，查看器保留其它可用条目，并对失败条目展示错误状态。
- 8. 退出媒体查看器后，房间时间线保持原位置，不触发多余跳转。

## 场景三

### 场景概述

gallery 消息需要接入消息操作、回复预览、分享和 pinned event 路径。base 版本仅有单媒体操作；final 版本需要让 gallery 在这些路径中作为完整消息类型被处理。

### 场景逻辑步骤

- 1. 用户长按 gallery 消息或其中一个媒体条目。
- 2. 操作菜单展示与媒体消息兼容的操作，例如回复、转发、分享、保存、复制链接或查看详情。
- 3. 用户回复 gallery 消息时，回复预览能够表达这是多附件消息，并展示代表性缩略图或附件数量。
- 4. 用户从 pinned event 或分享入口打开 gallery 消息时，客户端仍能解析并显示所有附件。
- 5. 分享 gallery 消息时，多个附件按 final 版本规则传递给分享流程，不丢失非首个附件。
- 6. 对于不支持的附件类型，gallery 中只显示该条目的 fallback，不把整条消息降级为 unsupported。
- 7. 内容扫描状态、媒体加载状态和错误提示在操作菜单、回复预览和媒体查看器之间保持一致。
- 8. gallery 支持不应改变普通单媒体消息的操作菜单和回复预览行为。
