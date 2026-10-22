# Native ArkVM Runtime Tests

## Task17 Owner-Bound Device Scoring

Task17's current formal path is the API 23 device-only owner-bound evaluator,
not the older detached-presenter strict adapter. It installs the unchanged
candidate app and ohosTest HAPs, launches the candidate Ability, performs
physical UiTest actions, and observes the real ArkUI page owner. The controlled
Matrix room is an evaluator-owned external service leaf injected before the
scored Ability starts; the candidate's page, session, list/controller, and
rendered controls remain production code.

Run the full base/final/agent calibration with:

```sh
python3 scripts/run_task17_arkts_owner_matrix_v1.py \
  --output /absolute/path/to/new-evidence \
  --agent-source /absolute/path/to/agent-candidate
```

Every role has a 3600-second overall budget. The independent verifier requires
27 scored rows, fresh install/uninstall evidence, application and runtime
compile success, ordered page-owner checkpoints, and base `0/9` plus final
`9/9` polarity:

```sh
python3 scripts/runtime_semantics/task17_arkts_owner_verify.py \
  /absolute/path/to/new-evidence/matrix.json
```

The central agent runner selects this path through
`task17_arkts_owner_agent_v3`. Missing observations, unavailable device
transport, or incomplete owner/service binding are never converted into
semantic failures.

The runner builds a small temporary copy of task12 final and invokes DevEco's
Hvigor `test` task. The installed local-test task launches the native ARM64
Previewer, which loads `libark_jsruntime.dylib` and executes Hypium in ArkVM.
No emulator, device, developer login, signing or dependency download is used.

## Commands

### Device Fixture Packaging

`arkts_native_device.cjs` packages an unchanged candidate and the existing
device-only UI fixture into separate app/ohosTest HAPs. It does not start an
emulator, install, or claim device execution:

```sh
node scripts/runtime_semantics/arkts_native_device.cjs \
  --source final_dev_nodes/12_report_room_final_25_05_0 \
  --task 12_report_room --fixture 12_15 \
  --output-dir experiment_results/runtime_transition_20261019/native-device-build/task12-final
```

Use `--fixture 16_18` for the tasks16-18 entry fixture. Optional
`--signing-config /absolute/config.json5 --signing-name NAME` selects an existing
Hvigor signing entry (a single entry, `signingConfigs`, or `app.signingConfigs`).
Material paths resolve relative to that config; password values are redacted
from build logs. Nothing is downloaded and original configs are not changed.
The default is unsigned. Both builds are verified locally; signing/install
acceptance requires the running emulator and a compatible profile.

The report includes HAP/source/fixture hashes and the `hdc shell aa test`
argument vector. Install app and test HAPs on the selected serial first. Provide
one canonical `caseSpec` JSON for the 12-15 fixture. These fixtures produce
partial UI evidence, not complete canonical passes. `--prepare-only` validates
and cleans a temporary project without building. All temp work is cleaned on
success or failure.

To package the same production factories, canonical adapter and evaluator for
device execution (no separate UI probe is merged), use one case per HAP run:

```sh
node scripts/runtime_semantics/arkts_native_device.cjs \
  --source final_dev_nodes/18_custom_notification_sounds_final_26_06_1 \
  --task 18_custom_notification_sounds --fixture bundle --role final \
  --case ns_state_004_message_custom_copy \
  --output-dir experiment_results/runtime_transition_20261019/native-device-bundle/task18-final-copy
```

This path is compile-verified, not device-executed. It adds real device-only
ES imports for fileuri, media and notifications. The context comes from the
device AbilityDelegator; its actual cacheDir supplies the fresh case sandbox,
not the host build path. The generated suite embeds the selected canonical
case; it does not need `caseSpec` at launch. All canonical cases can be packaged
individually by changing `--case`. Use a fresh install/app-data state for every
case: production's hard-coded preference names and notification slots are not
remapped into simulated namespaces or automatically restored by this bridge.
Do not run against an existing user's app data. Native `ARKTS_NATIVE_ROW` chunks
contain the evaluator result; Hypium transport completion alone is not a pass.

See [UI_PROOF.md](UI_PROOF.md) for the Previewer entry-proof API and proposed
typed entry-failure validator and its pending case-specific policy. Native production factories now get
lexical `getContext()` forwarding only when the actual case context is usable.
The agreed audio fixture shape is
`native.audioSources[canonicalURI] = { uri, displayName }`, populated only from
real provider/file fixtures. No audio source, app context, preference isolation,
or notification service is fabricated by this runner.

### Previewer Execution

From the repository root, run the direct ArkTS smoke test:

```sh
node scripts/runtime_semantics/arkts_native_smoke.cjs
```

Run the canonical adapter matrix in native ArkVM:

```sh
node scripts/runtime_semantics/arkts_native_smoke.cjs \
  --bundle all --role all \
  --output-dir experiment_results/runtime_transition_20261019
```

Run one externally supplied candidate without reconstructing or patching it:

```sh
node scripts/runtime_semantics/arkts_native_smoke.cjs \
  --bundle 12_report_room --role agent --source /absolute/path/to/candidate \
  --output-dir /absolute/path/to/results
```

`--source` requires one task and one role. Without it, base/final projects come
from `benchmark_tasks/TASK/task.json`; agent projects are reconstructed from
base plus the archived semantic-repair patch, matching the parent matrix.
`--keep-temp` retains build assets; the default removes them after evidence
collection, including when generation or build fails. `--prepare-only` retains
a successfully prepared project without building or running it; failed
preparation still cleans up unless `--keep-temp` was explicitly requested.

Loader and cleanup regression tests do not launch ArkVM:

```sh
node --test state_tests/runtime/arkts/native/*test.cjs
```

The verified Hvigor invocation is:

```sh
/Applications/DevEco-Studio.app/Contents/tools/node/bin/node \
  /Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor/bin/hvigor.js \
  test --mode module -p module=entry@default -p product=default \
  -p buildMode=debug -p isLocalTest=true -p unitTestMode=true \
  -p ohos-test-coverage=false --no-daemon --no-parallel
```

The runner supplies SDK paths, dependency links and the Hypium test entry.
This installation calls the task `test`, not `localUnitTest`.

## Evidence And Scoring

Per-task reports are `OUTPUT/reports/arkts_TASK_ROLE.json`. Shared logs,
generated bundle, source/adapter/contract digests, native process evidence and
compiled bytecode are under `OUTPUT/native/RUN/`. A complete matrix also writes
`OUTPUT/arkts_native_summary.json` without repeating the case rows.

- `compile.passed` is null: the candidate application was not built.
- `runtimeCompile.passed` describes the generated bundle and Hypium wrapper.
- Hypium success means a case wrapper completed. Semantic pass/fail/unscored
  results remain separate in each report's `semantic.cases`.
- Every canonical case ID and trace digest must survive the native round trip.
- The direct smoke imports the unchanged production `.ets` module and asserts
  `ReportRoomPresenter.submit()` preserves the form after report failure and
  makes no leave call.
- The matrix transpiles original production domain modules to JavaScript,
  bundles the existing adapter logic, and compiles that JS into Ark bytecode.
  It extracts the actual `snapshot`, `compareExpected` and `evaluateCase`
  functions from the host evaluator. It does not reimplement business logic.
- `es2abc` rejects the adapter spelling `async delete(...)`; an AST transform
  quotes that property name as `async "delete"(...)`. Original and emitted
  adapter hashes are recorded.

The matrix uses registry-only file existence/path shims, real native timers,
a wall-clock `performance.now` shim, and deep equality restricted to plain data.
`@ohos.file.fs`, `@ohos.data.preferences` and `@ohos.router` are native ES imports
forwarded into production factories with call recording. Unsupported methods and
unavailable context remain explicit unsupported observations, never substituted
services. Other platform imports are inert sentinels except immutable `@ohos.notification.SlotType`
constants extracted from the installed SDK declaration, whose path, hash and
values are recorded in the bundle manifest. No notification operations are
implemented by the shim. Any actual platform-service access is
recorded and leaves the case unscored. Native ArkUI behavior, persistence,
networking and media encoding are not validated. Missing UI observations are
never inferred into passing results.

The exit code indicates build/native transport completion, not semantic
calibration. Base cases without executable feature APIs remain unscored,
not artificial failures. Read per-case semantic results before scoring.

## Native Platform Bridge

Adapters receive `context.native` with `context`, `capabilities`, `sandbox`,
`fs`, `preferences`, `preferenceName`, `openPreferences()`, `reopenPreferences()`
and `ui`. Each case gets a fresh native-created sandbox.
The runCase argument exposes both `args.native` and `args.context.native` as
the same bridge; `args.context.productionCalls` and `native.productionCalls`
reference the actual production loader's call log, not a reconstructed trace.
Previewer filesystem write/read has been verified against the resulting host file. Its application
context directories are empty: preferences and other context-backed services
are not proven supported. The adapter must inspect capabilities before use.
`copyFile`, `copyFileSync` and `readTextSync` are absent in this Previewer, not
emulated. The platform probe separately verifies async open/write/close/stat/read
with a byte round trip and host filesystem check; inspect `asyncFilesystem`
before relying on this API family. Method presence alone is not a service proof.

For a single candidate, compile and navigate its unchanged ArkUI pages:

```sh
node scripts/runtime_semantics/arkts_native_smoke.cjs \
  --bundle 12_report_room --role base --native-ui \
  --output-dir /absolute/path/to/separate-results
```

`--native-ui` requires one task and role. It extends the temporary Hvigor test
page list without modifying installed SDK files or candidate page bodies.
`native.ui.observe(ids, anchorId)` returns native keyed inspector results only
after verifying the candidate route and a rendered positive-control anchor.
Absent controls have `present: false` only when that evidence is available;
otherwise `present` is null. The full-tree inspector can return only an empty
root even when keyed component inspection works; empty trees are never treated
as absence evidence. Valid UI observations add the compiled page's source hash
and native UI calls to the evaluator's execution evidence. Adapters still own
canonical expectations and before/after traces; a missing class is never a fail.

Other UI APIs are `snapshot()`, `inspect(id)`, `navigate(url)` and
`sendEvent(id, action, params)` (native ArkUI click action is 10).
These do not claim installation/device-service coverage. A reusable capability
probe can render either a base or final root without evaluating canonical cases:

```sh
node scripts/runtime_semantics/arkts_native_smoke.cjs --probe-platform \
  --source /absolute/path/to/candidate --output-dir /absolute/path/to/probe
```

The installed emulator is `Pura 90 Pro Max`, HarmonyOS 6.1.0/API 23. Its image is
already downloaded. The parent accepted the license and owns emulator startup.
Earlier on 2026-10-19 both the existing instance and a temporary smaller
instance were rejected by `CheckRuntimeEnv: No enough space to start Emulator`.
After the user freed space to about 26 GiB, the existing instance cold-booted
successfully at 17:16 local time. HDC connected at `127.0.0.1:5555`, reporting
API 23 and `emulator 6.1.0.115(SP11DEVC00E115R4P11)`. Task18's unsigned app and
ohosTest HAPs installed successfully. The first test launch ended with result
`-2`, `TestAbility was destroyed before Hypium completed`, without semantic
rows. Boot/install success does not imply a semantic pass. Historical startup
failures and the successful retry are retained in the experiment directory's
`native_device_environment.json` and `native_device_retry_20261019_171612.json`.

The evaluator now overlays `DeviceTestRunner.ets` only in the temporary test
project, invoking Hypium directly like its bundled runner. The native loader
also preserves Promise protocol behavior for absent `then` properties without
inventing service operations. Device re-execution completed transport and
verified a real audio file through AVMetadataExtractor. The task18 production
store was called, but `getPreferences` rejected the supplied Context; the row
remains unscored, not a semantic pass or fail. Evidence is under
`native-device-harness/task18-final-copy-then-fix/` in the experiment directory.
The temporary app was uninstalled and the emulator stopped after verification;
the existing instance and previously installed user apps were preserved.
