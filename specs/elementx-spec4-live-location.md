# 实时位置分享（v26.04.0 -> v26.05.1）

## 生产级长程任务定义

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

## 场景一

### 场景概述

用户可以在房间中发起实时位置分享。base 版本中实时位置相关分支和权限基础存在，但没有完整的启动 side effect、后台更新和 thread 限制；final 版本根据 release note 中 “Feature: share live location” 和 “Prevent user from starting Live Location Sharing in thread”等变更，需要完成从入口到启动分享的闭环。

### 场景逻辑步骤

- 1. 用户进入普通房间并打开发送位置相关入口。
- 2. 客户端检查定位权限；未授权时展示权限请求或解释界面。
- 3. 用户授权后，选择实时位置分享时长或使用默认时长。
- 4. 用户确认开始分享后，客户端创建实时位置分享事件，并启动 active live location share 管理逻辑。
- 5. 管理逻辑开始采集当前位置，并按 Android final 版本的节奏更新结构化 LastLocation 数据。
- 6. 开始分享成功后，房间时间线出现实时位置分享消息。
- 7. 如果用户在 thread 内尝试启动实时位置分享，入口应被禁用或展示不可用提示。
- 8. 权限拒绝、定位失败或发送失败时，用户可返回房间，且不会留下错误的 active share 状态。

## 场景二

### 场景概述

时间线需要渲染实时位置分享消息，并允许用户打开地图查看。base 版本会将实时位置 fixture 视为 unsupported；final 版本需要渲染 timeline item、地图入口、位置更新和超时状态。

### 场景逻辑步骤

- 1. 用户进入包含实时位置分享事件的房间时间线。
- 2. 客户端将 live location SDK timeline item 映射为受支持的 UI 类型。
- 3. 时间线展示实时位置分享卡片，包括发送者、最后位置、分享状态和剩余时间或结束状态。
- 4. 用户点击卡片后，打开实时位置地图视图。
- 5. 地图视图展示分享者最后一次有效位置，并在新位置到达时更新。
- 6. 当分享仍处于活跃状态时，地图和时间线都展示活跃状态。
- 7. 当分享超时或被停止时，时间线和地图切换为已结束状态。
- 8. 无位置、定位权限缺失、地图加载失败等异常只影响实时位置视图，不影响其它消息展示。

## 场景三

### 场景概述

客户端需要在用户自己正在分享实时位置时展示全局或房间级状态，并提供停止分享能力。该能力需要和 active share 管理器、时间线事件、通知渲染保持一致。

### 场景逻辑步骤

- 1. 用户成功开始实时位置分享后，客户端记录当前 active live location share。
- 2. 登录后主流程或房间界面展示正在分享位置的 banner/status。
- 3. 用户点击该 banner/status 时，客户端返回对应房间或实时位置地图。
- 4. 用户选择停止分享时，客户端调用停止逻辑并发送结束或更新事件。
- 5. 停止成功后，active share 管理器停止定位采集。
- 6. banner/status 消失，时间线中的实时位置消息更新为已结束。
- 7. 如果分享达到超时时间，客户端自动执行与停止分享一致的状态收敛。
- 8. 当收到实时位置分享开始的推送或通知渲染请求时，通知文案应能表达这是 live location share start。
