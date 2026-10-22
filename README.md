# Element X Multi-Platform Long-Term Benchmark

This workspace contains long-horizon Element X tasks for Android and
ArkTS/OpenHarmony, including the original five-task suite and release-derived
extensions. Both platforms consume the same public requirement specs, case ids,
state vectors, transition events, and semantic oracles. Platform-specific
runners differ only in how they apply a transition and capture the resulting
state.

The ArkTS migrations use task-scoped Matrix service boundaries and semantic UI
ids. Runtime audits have found migration omissions, so full base/final parity
is not yet established for the extended suite. The Android benchmark is built from the
official [Element X Android](https://github.com/element-hq/element-x-android)
release tags and keeps the upstream Kotlin/Compose and Matrix Rust SDK
architecture.

SDK policy:
- compileSdkVersion: 23
- compatibleSdkVersion: 23
- minAPIVersion: 23
- targetAPIVersion: 23

Local build environment:
- DevEco Studio: `C:\Program Files\Huawei\DevEco Studio`
- OpenHarmony SDK: `C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23`
- Helper script: `powershell -ExecutionPolicy Bypass -File C:\Users\xiexi\qingyu\scripts\set-oh-build-env.ps1`
- Build all bases: `powershell -ExecutionPolicy Bypass -File C:\Users\xiexi\qingyu\scripts\build-all.ps1`
- Apply function-level Android parity overlay: `python C:\Users\xiexi\qingyu\scripts\apply_function_level_alignment.py`
- Android/ArkTS equivalence check: `python C:\Users\xiexi\qingyu\scripts\verify_android_arkts_equivalence.py`
- Equivalence reports: `C:\Users\xiexi\qingyu\verification_reports\android_arkts_equivalence_report.md`
- Function-level report: `C:\Users\xiexi\qingyu\verification_reports\function_level_alignment_report.md`
- Generate final development nodes: `python C:\Users\xiexi\qingyu\scripts\create_final_dev_nodes.py`
- Build final development nodes: `powershell -ExecutionPolicy Bypass -File C:\Users\xiexi\qingyu\scripts\build-finals.ps1`
- Review final migration: `python C:\Users\xiexi\qingyu\scripts\verify_final_migration.py`
- Final review report: `C:\Users\xiexi\qingyu\verification_reports\final_migration_review.md`
- Full Harmony client: `C:\Users\xiexi\qingyu\elementx_harmony_client`
- Build full Harmony client: `cd C:\Users\xiexi\qingyu\elementx_harmony_client; powershell -ExecutionPolicy Bypass -Command ". C:\Users\xiexi\qingyu\scripts\set-oh-build-env.ps1; ohpm install; hvigorw assembleHap --no-daemon"`
- Full-client dynamic report: `C:\Users\xiexi\qingyu\verification_reports\full_client_dynamic\full_client_dynamic_report.md`
- Full-client parity report: `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\full_client_parity_report.md`
- Production-readiness audit: `python C:\Users\xiexi\qingyu\scripts\audit_production_readiness.py`
- Production-readiness report: `C:\Users\xiexi\qingyu\verification_reports\production_readiness.md`
- Upgrade production long-task specs/state tests: `python C:\Users\xiexi\qingyu\scripts\upgrade_production_longtask_specs.py`
- Generate evaluator-owned state binding manifests: `python C:\Users\xiexi\qingyu\scripts\generate_state_binding_manifests.py`
- Production state-test oracle audit: `python C:\Users\xiexi\qingyu\scripts\strict_state_oracle_audit.py`
- Production state-test target matrix: `python C:\Users\xiexi\qingyu\scripts\state_target_matrix.py`
- Production dynamic state matrix: `powershell -ExecutionPolicy Bypass -File C:\Users\xiexi\qingyu\scripts\run-state-strict-matrix.ps1`
- DevEco/DeepSeek production candidate run: `powershell -ExecutionPolicy Bypass -File C:\Users\xiexi\qingyu\scripts\run-deveco-deepseek-eval.ps1`

## Android benchmark

The Android base and final labels use the official Element X release tags that
correspond to the same feature intervals represented by the ArkTS tasks.

| Task | Base tag | Ground-truth final tag | Cases |
| --- | --- | --- | ---: |
| User status | `v26.07.0` | `v26.08.4` | 26 |
| Gallery messages | `v26.06.1` | `v26.08.1` | 28 |
| Timeline protection/rich events | `v26.07.1` | `v26.08.0` | 32 |
| Live location | `v26.04.0` | `v26.05.1` | 30 |
| Link new device | `v26.05.0` | `v26.08.2` | 34 |

The extended canonical-transition suite adds:

| Task | Base tag | Ground-truth final tag | Canonical cases |
| --- | --- | --- | ---: |
| Multi-select polls | `v26.08.4` | `v26.09.1` | 9 |
| Recent search history | `v26.09.2` | `v26.09.3` | 11 |

Their extraction evidence and shared contracts live under `benchmark_tasks/`.
The Android and ArkTS base/final projects calibrate to `0/20` and `20/20`
respectively; the MiniMax-M3 run is archived in
[`experiment_results/extended_opencode_minimax_m3_20261013`](experiment_results/extended_opencode_minimax_m3_20261013/README.md).

The active extracted batch is **tasks 08-17: 10 tasks, 91 cases per platform**
(182 across Android and ArkTS). Task18 was excluded on 2026-10-20 by user
request, instead of upgrading the API23 environment. It is excluded from current
calibration, agent selection and metric denominators on both platforms.
[The exclusion audit](experiment_results/runtime_transition_20261020/task18_exclusion/README.md)
preserves its projects, contracts and historical evidence. Tasks01-07 are unchanged.

The historical tasks 08-18 batch added 11 long-horizon capabilities: threads, Spaces,
media-upload quality, room-upgrade navigation, room reporting, user
verification, join-by-address, account deactivation, identity reset, pinned
messages, and custom notification sounds. That archive contains 101 cases per
platform. The historical MiniMax-M3 archive records code generation `22/22`
and compile `18/22`. Its `99/202` result (`47/101` Android, `52/101` ArkTS)
was **source-transition conformance, not runtime semantic testcase execution**.
Its source-based `0/N -> N/N` calibration does not validate a runtime benchmark.
The historical table, environment, reports, and reconstructable agent patches are in
[`experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair`](experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/README.md).

Runtime revalidation now uses `scripts/run_runtime_transition_matrix.py` and
`scripts/run_task_runtime_tests.py`. Missing runtime observations are
`not_scored`, never inferred failures or source-based passes. Until every
base/final pole calibrates through production execution, no aggregate semantic
benchmark score is valid. The 2026-10-19 evidence and limitations are tracked in
[`experiment_results/runtime_transition_20261019`](experiment_results/runtime_transition_20261019/README.md).

The approved [contract revision 2](experiment_results/runtime_transition_20261019/contract_audit/revision_2/README.md)
corrects invite cleanup and dimension-derived video size estimation only.
Old contracts, digests, and runtime reports are archived separately; old and new
contract results must not be combined.

The authorized 2026-10-20 repairs and staged
[contract revision 3](experiment_results/runtime_transition_20261020/contract_audit/revision_3/manifest.json)
cover real modal blocking, message-only notification version initialization,
and task12 independent operation prefixes. Old payloads/reports are retained;
the active canonical contracts and aggregate scores are not silently relabelled.
Migration source repairs have separate before/after audits. New evidence is in
[`experiment_results/runtime_transition_20261020`](experiment_results/runtime_transition_20261020/README.md).
No new agent benchmark result is claimed before complete four-way runtime calibration.

The current integration checkpoint is
[`RUNTIME_CHECKPOINT.md`](experiment_results/runtime_transition_20261020/RUNTIME_CHECKPOINT.md).
The October21 [runtime-boundary audit](experiment_results/runtime_transition_20261021/public_owner_boundary_withdrawal_v1/README.md)
withdraws incomplete owner/navigation and changed-SDK-bridge calibration. Existing
UI/domain observations remain evidence, but no full score follows from a test
double that bypasses task-added production logic, even with unchanged source
hashes. Missing calibration is not a model semantic failure.
It distinguishes runtime calibration, standalone candidate scorer checks, and
fresh model-generated results. A copy of final submitted with role `agent` is
only a scorer check and does not count as an OpenCode/MiniMax agent result.
The retained-batch runner uses `minimax-token-plan/MiniMax-M3`, the configured
MiniMax endpoint, a shared Android full-build lock, and an 8 GiB storage guard.
Build outputs are hashed and removed before semantic evaluation.

Historical original-five Android evaluation environment:

- Java: 21.0.12.1
- Android compile/target SDK: API 36 for older tags and API 37 for newer tags,
  as declared by each upstream release
- Android min SDK: API 24 for the FOSS/GPlay benchmark variants
- Android Emulator: 37.2.12
- AVD: `Medium_Phone_API_37.0`, Android 17/API 37, `arm64-v8a`
- OpenCode: v2.0.20
- Agent model: `bigmodel-glm/glm-5.3`
- Per-task agent and build timeout: 3600 seconds

Build the ten evaluator-instrumented base/final APKs and calibrate polarity:

```sh
python3 scripts/build_android_golden_macos.py \
  --run-root eval_runs/<run-id> --timeout 3600 --clean

QINGYU_BENCH_ROOT="$PWD" \
QINGYU_ANDROID_GOLDEN_APK_ROOT="$PWD/eval_runs/<run-id>/android_golden_apks" \
QINGYU_STATE_REPORT_DIR="$PWD/eval_runs/<run-id>/verification_reports/state_dynamic" \
python3 scripts/state_target_matrix.py

QINGYU_BENCH_ROOT="$PWD" \
ANDROID_HOME="$HOME/Library/Android/sdk" \
ANDROID_SDK_ROOT="$HOME/Library/Android/sdk" \
python3 scripts/run_snapshot_state_matrix.py \
  --matrix eval_runs/<run-id>/verification_reports/state_dynamic/state_dynamic_target_matrix.json \
  --out eval_runs/<run-id>/verification_reports/android_golden_strict \
  --platform android --target-role both --transition-mode strict
```

Run clean-room OpenCode candidates and score the agent APKs against the same
150 transition-driven testcases:

```sh
python3 scripts/run_opencode_glm_android_eval_macos.py \
  --run-id <run-id> \
  --candidate-root "$PWD/../Long-Term-Benchmark-android-eval/<run-id>" \
  --agent-timeout 3600 --build-timeout 3600 --parallel 1

QINGYU_BENCH_ROOT="$PWD" \
QINGYU_ANDROID_GOLDEN_APK_ROOT="$PWD/eval_runs/<run-id>/android_golden_apks" \
QINGYU_ANDROID_AGENT_ROOT="$PWD/../Long-Term-Benchmark-android-eval/<run-id>" \
QINGYU_STATE_REPORT_DIR="$PWD/eval_runs/<run-id>/verification_reports/state_dynamic" \
python3 scripts/state_target_matrix.py

QINGYU_BENCH_ROOT="$PWD" \
python3 scripts/run_snapshot_state_matrix.py \
  --matrix eval_runs/<run-id>/verification_reports/state_dynamic/state_dynamic_target_matrix.json \
  --out eval_runs/<run-id>/verification_reports/android_agent_strict \
  --platform android --target-role agent_result --transition-mode strict
```

The Android debug `ContentProvider` protocol and its relationship to the ArkTS
Ability/ArkUI protocol are documented in `state_tests/README.md`. Generated
agents receive the public specs and YAML only; evaluator bindings and official
final sources remain hidden.

macOS OpenCode + GLM-5.3 evaluation:

```sh
# Generate and build candidates. The long-horizon agent budget is one hour per task.
python3 scripts/run_opencode_glm_eval_macos.py \
  --run-id opencode_glm53_3600_$(date +%Y%m%d_%H%M%S) \
  --agent-timeout 3600

# Calibrate evaluator polarity against the trusted base/final mirrors.
QINGYU_BENCH_ROOT="$PWD" \
QINGYU_HDC="$HOME/Library/OpenHarmony/Sdk/23/toolchains/hdc" \
python3 scripts/run_snapshot_state_matrix.py \
  --matrix verification_reports/state_dynamic/state_dynamic_target_matrix.json \
  --out verification_reports/workflow_calibration \
  --platform arkts --target-role both --transition-mode compatible \
  --ready-timeout 12 --transition-timeout 1

# Generate a matrix for one candidate root, then score it with phase-strict transitions.
QINGYU_BENCH_ROOT="$PWD" \
QINGYU_ARKTS_AGENT_ROOT="$PWD/eval_runs/<run-id>/arkts_agent_results" \
QINGYU_STATE_REPORT_DIR="$PWD/eval_runs/<run-id>/verification_reports/state_dynamic" \
python3 scripts/state_target_matrix.py

QINGYU_BENCH_ROOT="$PWD" \
QINGYU_HDC="$HOME/Library/OpenHarmony/Sdk/23/toolchains/hdc" \
python3 scripts/run_snapshot_state_matrix.py \
  --matrix eval_runs/<run-id>/verification_reports/state_dynamic/state_dynamic_target_matrix.json \
  --out eval_runs/<run-id>/verification_reports/snapshot_state_dynamic_strict \
  --platform arkts --target-role agent_result --transition-mode strict
```

The GLM API key is read from the local OpenCode provider configuration and must
not be committed to this repository. The complete state capture and transition
contract is documented in `state_tests/README.md`.

Latest archived run: [`experiment_results/opencode_glm53_3600_20261009`](experiment_results/opencode_glm53_3600_20261009/README.md)

Latest Android archive: [`experiment_results/android_opencode_glm53_3600_20261011`](experiment_results/android_opencode_glm53_3600_20261011/README.md). The base/final calibration is valid. After quota recovery, the agent retry produced four timeouts, one no-change normal exit, four buildable APKs, and 150 protocol failures; it remains explicitly invalid as a semantic model score.

Production benchmark contract:
- Specs live in `C:\Users\xiexi\qingyu\specs` and now describe production-grade long-horizon tasks.
- State tests live in `C:\Users\xiexi\qingyu\state_tests` and cover 150 final-positive semantic cases across the five tasks.
- Binding manifests live in `C:\Users\xiexi\qingyu\state_tests\bindings`; they are generated by evaluator-side static tooling, not by the development agent.
- `run-state-strict-matrix.ps1` evaluates each case independently. Target-level feature markers are smoke evidence only and are not counted as production testcase passes.
- Legacy scripts named `run-state-dynamic-*` or `run-android-state-dynamic-tests.ps1` have been archived under `_archive`; do not use them as benchmark score.

Full-client direction:
- `elementx_harmony_client` is the unified Harmony client app, separate from the five benchmark harness apps.
- It starts from Android-aligned signed-out onboarding, exposes manual sign-in, QR sign-in and create-account routes, and then enters one signed-in app shell with Home, Timeline, Settings and Devices tabs.
- The five migrated final feature surfaces are now available inside this single client shell.
- The current Matrix layer is an adapter boundary in `entry/src/main/ets/services/MatrixClientService.ets`; it now exposes Android-aligned root navigation, session cache, sync, push, verification, recovery, network, intent and homeserver capability states.
- Android `MatrixClient.kt` now has a method-level ArkTS contract in `entry/src/main/ets/services/MatrixClientContract.ets` and a SDK 23-compilable fixture implementation in `entry/src/main/ets/services/FixtureMatrixClientAdapter.ets`.
- Real Matrix Client-Server scaffolding now lives in `entry/src/main/ets/services/MatrixClientServerApi.ets`, covering homeserver discovery, `/versions`, password login and `/sync` request construction through `@ohos.net.http`.
- Matrix `/sync` mapping now lives in `entry/src/main/ets/services/MatrixSyncMapper.ets`, converting joined rooms, `m.room.message` timeline events and public `ephemeral.m.receipt` payloads into the existing Harmony UI model after real password login.
- Room selection is now room-scoped: `TimelineEvent` carries `roomId`, room rows switch the selected room, and the Timeline tab renders the selected room instead of one hard-coded timeline.
- Persistent launch restore now lives in `entry/src/main/ets/services/PersistentSessionStore.ets`, using `@ohos.data.preferences` plus the `ohos.permission.INTERNET` manifest permission for real homeserver traffic.
- Manual sign-in now accepts homeserver, username and password. Supplying a password uses the real Matrix password-login path; leaving it empty keeps the local fixture path for no-credential UI regression.
- Timeline now includes a message composer. Access-token-backed sessions use the Matrix text-message send endpoint; fixture sessions append a local echo for dynamic UI regression.
- Settings now includes a profile editor. Access-token-backed sessions update Matrix display name through the Client-Server profile endpoint, while display name, avatar URL and user status are persisted in the local session store for launch restore.
- Timeline now includes a selected-room `Mark read` action, and Home includes `Mark all read`. Access-token-backed sessions send Matrix `m.read`/`m.read.private` receipts and fully-read markers; fixture sessions mutate room-scoped unread state for UI regression. Settings persists the public/private receipt preference. Dynamic evidence lives in `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\read_marker_home_before.ui.md`, `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\read_marker_home_after.ui.md`, `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\read_receipt_preference_restore_private.ui.md` and `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\mark_all_read_home_after.ui.md`.
- Opening a room now automatically marks the selected timeline as read using the same receipt path and per-room repeat suppression. Dynamic evidence lives in `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\auto_read_home_after_open.ui.md`.
- Timeline events now render Android-style read receipt avatars and a compact reader summary when the public/presence preference is enabled, and hide them when the preference is private. The client stores separate send/render receipt preferences and migrates old records by following the previous send preference. Tapping the receipt row opens a `Seen by` sheet with every reader and receipt time. Dynamic evidence lives in `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\read_receipts_timeline_public_visible.ui.md`, `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\read_receipts_timeline_private_hidden.ui.md`, `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\read_receipts_bottom_sheet_visible.ui.md` and `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\presence_split_timeline_private_hidden.ui.md`.
- EntryAbility now captures cold/hot-start Wants through `LaunchIntentStore`, and `module.json5` registers Element/Matrix URI filters. `elementx://notification/markRead?roomId=dm-bob` resolves to the client and marks only that room read; evidence lives in `C:\Users\xiexi\qingyu\verification_reports\full_client_parity\implicit_notification_mark_read_dm_bob.ui.md`.
- Complete Android parity still requires replacing the remaining fixture room/timeline/sync/crypto/media/push implementation with real Matrix-backed behavior, a Matrix Rust SDK-equivalent runtime or native bridge, and secure token/crypto storage. The production-readiness audit intentionally fails until those blockers are resolved.

Function-level parity:
- Each base includes `entry/src/main/ets/androidparity/FunctionLevelParity.ets`.
- The parity layer maps Android classes, composable functions, presenter functions, event branches and helper methods to ArkTS equivalents.
- The Contract tab exposes the scenario-specific parity rows via `ElementBaseViewModel.getFunctionLevelAlignmentRows()`.

Base apps:
- `01_user_status_base_26_07_0`: before User Status is enabled.
- `02_gallery_messages_base_26_06_1`: before gallery messages are supported.
- `03_active_call_timeline_base_26_07_1`: before active call timeline items are rendered.
- `04_live_location_base_26_04_0`: before live location sharing is available.
- `05_link_new_device_base_26_05_0`: before the richer link-new-device QR flow iterations.
- `06_multi_select_polls_base_26_08_4`: before polls support multiple answers.
- `07_recent_search_history_base_26_09_2`: before global search persists recent queries and rooms.

Each app intentionally uses the same ArkTS structure so benchmark tasks can compare implementation trajectories cleanly:
- `AppScope/app.json5`
- `build-profile.json5`
- `entry/src/main/module.json5`
- `entry/src/main/ets/entryability/EntryAbility.ets`
- `entry/src/main/ets/pages/Index.ets`
- `entry/src/main/ets/model/ElementModels.ets`
- `entry/src/main/ets/services/MockMatrixService.ets`
- `entry/src/main/ets/viewmodel/ElementBaseViewModel.ets`
