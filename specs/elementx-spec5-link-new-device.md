# 新设备登录与二维码超时保护（v26.05.0 -> v26.08.2）

## 生产级长程任务定义

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

## 场景一

### 场景概述

用户从已登录设备发起“连接新设备”时，需要先通过设备所有者验证。base 版本已有 QR 登录占位和部分验证流程；final 版本根据 release note 中 “Protect link new device”、设备凭据或应用 PIN 解锁、二次生物识别失败修复等变更，需要补齐入口保护和失败重试。

### 场景逻辑步骤

- 1. 用户进入设置页的安全或会话管理区域。
- 2. 用户点击连接新设备入口。
- 3. 客户端在展示二维码或验证码流程前，先进入设备所有者验证。
- 4. 用户可以使用系统设备凭据、生物识别或应用 PIN 完成验证。
- 5. 验证成功后，客户端进入连接新设备方式选择或扫码准备页面。
- 6. 如果第一次生物识别失败，用户可以再次尝试或切换到其它验证方式。
- 7. 第二次及后续失败不得导致流程卡死、重复弹窗或错误地跳过验证。
- 8. 用户取消验证时，流程安全退出并返回原设置页。

## 场景二

### 场景概述

连接新设备流程需要支持移动端扫码、桌面端提示和验证码路径，并处理 SDK split steps。final 版本包含 QR code login iteration、缺失 digits 页面、扫描页警告、错误映射和完成检测等变更。

### 场景逻辑步骤

- 1. 设备所有者验证通过后，用户选择连接手机、桌面端或使用验证码相关路径。
- 2. 选择扫码路径时，客户端展示 QR code 扫描页面，并显示安全警告。
- 3. 选择桌面或验证码路径时，客户端展示对应 notice、digits 或等待确认页面。
- 4. 客户端根据 SDK 返回的 split step 推进流程，而不是假设所有步骤一次完成。
- 5. 当 SDK 要求展示验证码或确认信息时，客户端显示对应屏幕。
- 6. 当 SDK 返回 already signed in、另一个设备已退出、取消、继续失败等错误时，客户端映射为可理解的错误页面或提示。
- 7. 当新设备完成验证后，客户端检测完成状态并进入成功页。
- 8. 完成或取消后，流程返回安全设置或会话列表，且不保留过期临时状态。

## 场景三

### 场景概述

二维码登录需要受超时保护。final 版本经历过自动轮换 QR code 的迭代，最终通过 “Disable QrCode rotation” 和 “Add timeout” 收敛为受控的超时/重试体验：二维码或桌面 notice 超时后提示用户重试，而不是无限轮换或只显示底层错误。

### 场景逻辑步骤

- 1. 用户进入扫码或桌面 notice 流程后，客户端启动与 Android final 版本一致的超时计时。
- 2. 在超时前，二维码或等待确认界面保持可用，并能继续接收 SDK 状态更新。
- 3. 如果 SDK 报告二维码过期，客户端不崩溃，也不直接暴露底层错误。
- 4. 客户端停止无界自动轮换行为，避免用户看到不断变化且不可控的二维码。
- 5. 达到约定超时时间后，扫码页面和桌面 notice 页面都进入 timeout notice 状态。
- 6. timeout notice 清楚告知当前连接尝试已失效，并提供重试或退出。
- 7. 用户点击重试时，客户端创建新的连接尝试并重新进入验证后的连接流程。
- 8. 用户退出时，客户端取消当前流程、清理临时二维码和计时器，并返回安全设置。
