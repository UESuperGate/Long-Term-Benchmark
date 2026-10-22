# Task11 Stage Window Guard Audit

## Post-Load Device Success And Bounded Scoring (Current)

Parent-provided evidence, read without modifying or rerunning the device:
`experiment_results/runtime_transition_20261019/device-calibration/task11-postload-module-diagnostic/native-result.json`
(926648 bytes, SHA-256
`26d2a020ebced05fc583e9cc31acf677c56041a2108b68fd26197a9d8c6cc075`).

`originalModuleBound.requestedModuleUrl` is exactly
`@bundle:com.qingyu.elementx.roomupgrade.final/entry/ets/features/RoomUpgradeFeature`.
Import completed. The artifact lists ten wrapped methods/getters and eleven
prototype descriptors including the unwrapped constructor, not eleven wrapped
methods. `diagnosticReceiverCapture` records available=true, instanceId=1,
stateOwnerId=1, gatewayId=1, and capturedSelectOldRoom=true after the original
button click. Before/after rendered room is `!old:example.org`; original history
is `["Earlier message"]`, successor is `!new:example.org`, navigationCount=0,
navigationState=idle. This proves a same-page receiver was reached in this run;
it does not prove navigation success or a canonical case pass. The diagnostic
row remains unscored by design.

New explicit `after-page-ready` mode is bounded to canonical cases005/007 only.
It follows the same cold lifecycle and post-page import sequence, captures a
receiver through one real old-room setup click, and verifies current state ID
against real rendered room text. It then exposes the actual observer unchanged
to existing `nativeRoomUpgrade`, not a derived PASS or synthesized state. That
adapter validates canonical room ID, last message/history, successor/predecessor
metadata before observations. For 007 it physically selects the replacement
room. It checks real banner/history visibility and ordinary room-beginning
visibility; 005 checks rendered summary/avatar and retained last message.
Missing givens or unavailable UI observations remain NS; wrong observed values
and failed invariants remain failures. No contract or production changes.

Default remains `disabled`; diagnostic mode remains always unscored, including
when capture succeeds. Twenty-six local tests cover both modes, role-neutral
allowlisting, unavailable receiver/root rejection, installer mode guards, and
the unchanged adapter with real transpiled production state plus explicit OS
transport doubles. Negative tests reject incorrect canonical givens and retain
absent-banner/invariant failures. No device execution or new build was run for
this scoring-mode change; parent will build and run exactly 005/007. Shared
packager and other task fixtures are unchanged.

## Native Fatal And Cache Diagnostic (Prior Investigation)

`task11-original-app-module/native-process.log:159-161` proves a native fatal:
the reader attempts `/data/storage/el1/bundle/entry.hsp`, extraction fails, and
ArkVM aborts in LoadJSPandaFile. No canonical row exists. This is NOT a semantic
failure or a catchable ordinary import rejection. Do not promote the pre-start
import path to tasks12/18. Its compile/ABC verification remains valid but did
not establish device loader availability.

Bounded upstream source inspection found a reason to test post-load exactly once:

- [JSPandaFileManager::LoadJSPandaFile](https://github.com/openharmony/arkcompiler_ets_runtime/blob/master/ecmascript/jspandafile/js_pandafile_manager.cpp)
  checks its filename-indexed file/buffer caches before calling the HSP buffer
  reader. An unsuccessful buffer resolution can terminate with native FATAL.
- [BuiltinsPromiseJob::DynamicImportJob](https://github.com/openharmony/arkcompiler_ets_runtime/blob/master/ecmascript/builtins/builtins_promise_job.cpp)
  resolves the ABC before consulting the module namespace cache. Thus the
  module cache alone is insufficient; the ABC filename cache must also match.
- The prior successful page run in `task11-tombstone-null-query/native-process.log:47`
  logs executing an Ark buffer with filename
  `/data/storage/el1/bundle/entry/ets/modules.abc`, matching the failed request.
  This supports a post-page-load cache hypothesis, not proof of a cache hit.
- [JsModuleReader](https://github.com/openharmony/ability_ability_runtime/blob/master/frameworks/native/runtime/js_module_reader.cpp)
  services HSP paths on this loading route. A valid OHM record does not imply
  an arbitrary unstarted HAP can be fetched through that route.

These upstream master sources are reference implementations, NOT an identified
source revision of the installed software 6.1 image. A same-process loaded ABC
could avoid the failed cold-load path, but filename aliases, VM/module-cache
identity or firmware differences could still cause failure. No public cache
probe was found or used. No private loader or guessed numeric/path fallback is
introduced.

The installer defaults originalModuleImportMode to `disabled`: no import or
production instrumentation executes, and observer reads explicitly report
unavailable. The only allowed opt-in is `after-page-ready-diagnostic`, via its
installer option or `TASKS08_11_ORIGINAL_MODULE_IMPORT` environment variable.
That mode requires real original stage/window/route/tree/Driver anchor readiness
before the single import, emits a process-log marker, and installs the existing
pass-through observer afterward. One original room-list Button Component click
attempts natural receiver capture; state/calls and actual room text are logged.
No getter/business method is invoked to manufacture an active instance.
Canonical scoring is deliberately disabled for this diagnostic because the
setup click can mutate product state. Missing anchors prevent import entirely.

Nineteen local transport tests pass, including default zero imports, deferred
binding order, no import on missing page, one physical-click transport dispatch,
and an explicitly unscored diagnostic result. Device execution remains owned
by the parent. If the one post-load attempt fails, stop this route. Same-entry
ABC evaluator/TestRunner packaging is a reasonable next investigation, but no
manifest overlay, production file or shared packager was changed here.

The explicit post-page diagnostic was packaged successfully in
`/tmp/Tasks08_11DeviceUi-postload-diagnostic-20261019/device-build-report.json`.
The report records `built_not_executed`, `runtimeCompile.passed: true`,
`productionUnchanged: true`, `copiedProductionUnchanged: true`, and
`temporaryProjectRemoved: true`. Both HAPs are unsigned; this build is not
device acceptance or cache-hit evidence. SHA-256:

```text
entry-default-unsigned.hap
fc09b955e11e9919e3b37506c150d830b0c4e04305b971555b3a78d6d09ed515
entry-ohosTest-unsigned.hap
b89ac415a81ebafc12d2bb5b6cdcbaa7264a5700232bfe5dfe56e269582ba5fa
```

## Original App Module Binding (Historical Build)

Read-only ABC inspection of the two HAPs in
`experiment_results/runtime_transition_20261019/device-calibration/task11-tombstone-null-query/`
confirmed two distinct production class records. The original page requests
`@bundle:com.qingyu.elementx.roomupgrade.final/entry/ets/features/RoomUpgradeFeature`;
the test's relative import requests
`@bundle:com.qingyu.elementx.roomupgrade.final/entry_test@entry/ets/features/RoomUpgradeFeature`.
Both ABCs define their own RoomUpgradePresenter. Original `Index.aboutToAppear`
calls `observeTimelineRoomInfo`, `refresh` reads `isTombstoned`, and `build`
calls `roomListPreview`; absence of constructor instrumentation is not the cause
of zero observed calls. `nativeRoomUpgrade.capture` does call observer.read.

The device companion installer now removes the generated suite's relative
production import entirely. It supplies the actual app manifest bundle/module
and selected original export to a standard variable `import(url)` inside
`Tasks08_11DeviceUi.js`. `augment` awaits the imported class's existing observer
installation before registering lifecycle listeners or starting EntryAbility.
No eval, private loader, copied business implementation, presenter construction,
synthetic method invocation, or candidate source change is used.

`originalModuleBound` records requestedModuleUrl, importCompleted, namespace
exports, presenter export, prototype descriptors and the names whose original
descriptors were actually wrapped. `receiverObserved: false` describes binding
time only. Successful import does not itself prove a page receiver; only later
original page calls can satisfy the unchanged observer/read checks. The public
import operation does not expose an independent resolved-record URL; the
requested URL is not mislabeled as such. Compiled paths are audited separately.

Independent build output (no device execution):
`/tmp/Tasks08_11DeviceUi-original-app-import-20261019/`.
Both app and ohosTest builds passed for `ru_state_005_room_list_tombstone_preview`;
the build report says `built_not_executed`, runtimeCompile.passed=true.
All production source hashes still match the pre-build manifest. Build and
unzip/disassembly temporary workspaces were removed. Sixteen host tests pass.

ABC verification:

- App defines `com.qingyu.elementx.roomupgrade.final.entry.ets.features.RoomUpgradeFeature`.
- Test no longer defines any `entry_test@entry.ets.features.RoomUpgradeFeature` record.
- Test retains the original `/entry/` OHM URL and executes `lda v3; dynamicimport`
  in `Tasks08_11DeviceUi`'s import transport function. No source-relative native
  class import is left in the generated suite.
- Device behavior is pending. Namespace/descriptor diagnostics will be emitted
  only if the actual device import succeeds, and receiver identity still needs
  to be observed through the original page.

Build digests (SHA-256):

```text
app HAP: 06b5c82a98da1f565afdba51a7b2147bc3cc3dfd50bd72697a0b24ca6c03f1ef
test HAP: 5c746131237a3e22d553f1532b718c310074746defafdb7869328b365c88ddd9
app ABC: 1e02c470f6dd0cf84b2dbeef6c67eefaf0dc5669e20995529985c70f0d5a6171
test ABC: 331fcf3fc9e5526f164f7e44697a632d8c055fc697ff856b78301263a5cb868b
```

The previous recommendation to reuse this import path for tasks12/18 is withdrawn
after the native fatal. The duplicate-record diagnosis still applies, but its
runtime remedy is not validated. No task12/18 files were changed.

## Null Query Follow-Up (Latest)

The persisted `task11-tombstone-stage-lifecycle/device-execution.json` reports
`transport_completed`, unchanged production, and a not-scored
`ru_state_005_room_list_tombstone_preview` at `inspect:181` (reading the query
result's length). The device startup ownership chain now executes. `row.calls`
already contains observer installation, both stage callbacks, candidate window,
`deviceUiReady` and `navigate`; no new startup attachment is necessary.

The query helper now normalizes only null/undefined to an empty array for
inspection and gestures. Missing anchors remain unavailable and missing
controls cannot be clicked. A non-array, non-nullish result remains an error.
Fourteen transport tests pass, including null/undefined/empty results, absent
control with a real anchor, malformed return rejection, and startup recorder
evidence surviving serialized row JSON without changing its NS verdict.

The historical native result is 539059 bytes; redundant `inspectorTree`
copies under its two recorded snapshots account for 258524 bytes. Those
artifacts are untouched. New snapshots keep the full tree once under `tree`
for existing traversal consumers, with `inspectorTreeField: 'tree'` and original
root dimensions under `inspectorTreeDimensions`. All original node attributes
and structure remain. Snapshots at different times are deliberately not
deduplicated; they represent distinct observations. No device operation or
production/shared runner edit was made for this follow-up.

## Runtime Enum Follow-Up (Current Repair)

Parent's `task11-tombstone-stage-main` attempt reports that software 6.1 does
not export the API23-declared `WindowType.TYPE_MAIN`. The enum-dependent
repair below is therefore superseded, not counted as native success.

Production `entry/src/main/ets/entryability/EntryAbility.ets` loads the original
`pages/Index` but does not retain its WindowStage. No production lifecycle
method is wrapped or replaced. SDK `ApplicationContext.on('abilityLifecycle',
callback)` supplies the real stage to
`AbilityLifecycleCallback.onWindowStageCreate(ability, windowStage)`;
unlike AbilityMonitor, this callback includes the WindowStage.
Local SDK declarations: `application/ApplicationContext.d.ts:99,186`,
`@ohos.app.ability.AbilityLifecycleCallback.d.ts:114`, and
`@ohos.window.d.ts:9244` (`WindowStage.getMainWindow`).

Current ownership chain, with no numeric enum fallback:

1. Observer and both native lifecycle listeners install before startAbility.
2. Cold-create/foreground/top-ability checks remain. Only the exact configured
   bundle/module/ability tuple can supply the original candidate WindowStage.
3. Stage `getMainWindow()` and `getLastWindow(monitoredAbility.context)` must
   return the same valid native window ID. A same-bundle dialog is rejected
   even when its context, geometry and route otherwise match.
4. Actual Window.getUIContext().getHostContext() must match the candidate
   bundle/module/ability tuple. No synthetic/global context is substituted.
5. Actual UiTest window must be focused and report the candidate bundle; its
   bounds must exactly match both native rectangles. UiWindow in this SDK
   has no getId API, so the evaluator does not invent one: ID equality is
   between the two native Window APIs, not falsely attributed to Driver.
6. Original scoped route/root and control checks remain required. Window type
   and enum are recorded with both value and typeof, including undefined.

Missing stage/ownership data remains unsupported. Main-window identity comes
from the stage API, not from inferring that bundle/geometry alone imply main.
Eleven host tests pass, including absent enum acceptance with proven transport
ownership, dialog ID rejection, foreign host/stage/window rejection, unfocused
and mismatched geometry rejection, cleanup and original observer identity.
These are OS transport doubles, not native proof; no device was accessed.
The installer hook is unchanged. Parent must rebuild and verify on device.

## Prior Attempt (Historical)

Date: 2026-10-19. Case: `ru_state_003_open_successor`, final.
Scope: evaluator-owned `Tasks08_11DeviceUi*` only. No device operation,
production/contract change, candidate page replacement, or navigation result
inference was performed in this repair.

## Evidence

Evidence directory:
`experiment_results/runtime_transition_20261019/device-calibration/task11-open-successor-native-unlocked/`.

- `aa-test.log:19-23`: startup times out after 10738 ms in `augment`, with
  `Candidate main application window is unavailable`. This is an evaluator
  setup error, not a production navigation semantic failure.
- `native-process.log:112-115`: original `onWindowStageCreate` calls
  `LoadContent`; window stage ID is 37.
- `native-process.log:235-256`: candidate bundle/entry initializes
  `pages/Index`, `RunPage` executes, window 37 load content returns 0.
- `native-process.log:277-298`: `GetTopWindowWithContext: mainId:37`, followed
  by original `pages/Index` creation and `LoadPage Success`.
- The old core checks cold create/foreground and top-ability identity before
  resolving `getLastWindow(created.context)`. Its reported error is after that
  resolution and `getWindowProperties`, but BEFORE `Window.getUIContext()`.
  Thus the message did not prove UIContext itself was unavailable.

## SDK Contract And Defect

Local SDK root: `/Users/z1an/Library/OpenHarmony/Sdk/23/ets/api/`.

- `@ohos.window.d.ts:103`: `WindowType.TYPE_APP = 0` is `@FAModelOnly`.
- `@ohos.window.d.ts:152`: `WindowType.TYPE_MAIN = 32`, since API18.
- `@ohos.window.d.ts:1467`: `WindowProperties.type` is the native-returned
  `WindowType` property; the property name itself was correct.
- `@ohos.window.d.ts:2727`: `getLastWindow(context)` returns the application's
  top window, or main window if no child window exists. It is not a guarantee
  that the returned window is the main window, so a main-window guard remains.
- `@ohos.window.d.ts:5166`: `Window.getUIContext()` obtains that window's
  actual content context and is Stage-model-only.
- `application/AbilityMonitor.d.ts:120,143,212`: creation, foreground and
  window-stage callbacks receive a `UIAbility`. The latter does NOT provide a
  `WindowStage`. Using the observed ability's `.context` remains appropriate;
  no fake stage or global/pre-start UIContext is introduced.

Defect: the evaluator supplied FA-only `TYPE_APP` to a Stage main-window
guard, preventing access to the created page's UIContext. The original host
transport fixture also returned type 0, masking this integration error.
The logs do not include the actual JS `properties.type`; the native WMS
`type:1` at line 68 is an internal value and must NOT be reinterpreted as
the public JS enum. No numeric 1/0 fallback is added.

## Repair And Verification

- Device entry now supplies `window.WindowType.TYPE_MAIN` as `mainWindowType`.
- Core rejects an unavailable SDK enum and any returned type not equal to it.
  It preserves cold-start, foreground/top-ability, host-context, original
  route/root and Driver control checks. No loading, clicking or app mutation
  has been added to the window resolution path.
- `candidateWindow` records actual ID/name/type/rect, monitored ability
  identity and required enum. Consecutive identical records are deduplicated.
  A mismatch error also includes actual/required types and window ID, so the
  parent receives diagnostics even if startup fails before recorder binding.
- Nine host transport tests pass, including execution of the device-entry
  wiring with OS module doubles, Stage type acceptance, FA/dialog/unknown
  rejection, missing-enum rejection, foreign-host rejection, lifecycle order,
  same observer preservation, clicks, visibility limits and generated-only
  installer behavior. Device-entry JS syntax also checks successfully.

These tests are scaffold verification, not native UI proof. Parent must
regenerate/rebuild using the unchanged installer hook, hash generated files
after installation, and rerun the one case when the device is free. If a
later native context/inspector/click/navigation gap appears, retain it as
unsupported; neither a window nor click completion establishes room navigation.

## Input Digests

SHA-256:

```text
aa-test.log
b5cfe325bf940c02c149eba8e8a2be3384aa707810d8231953084c52964ec4db
native-process.log
66fa852fda8c2eaddb60a0bad25b2621433983fe0529a581e34dfb3f561e1900
SDK @ohos.window.d.ts
35af4442c05a57dc6ed37d77dabee2a1084df2e95f17e699abf4a212c3ac3780
SDK application/AbilityMonitor.d.ts
96778cf857aacd231016c6576761f5763f68201a30234ef0913e836b4526e38c
```
