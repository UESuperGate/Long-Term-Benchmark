# Task12 Blank-Reason Device Wiring

Only `rr_state_006_blank_reason_disabled` is newly bound. No native execution
or semantic pass is claimed by the local scaffold tests.

## Production Trace

`entry/src/main/ets/pages/Index.ets` owns one `ReportRoomPresenter` with its
original service/gateway. Native input invokes `updateReason`, native Toggle
invokes `toggleLeaveRoom`, and the original page `refresh()` copies those
values into the rendered controls. The original `canReport` getter remains
the source of the domain field; the native submit control remains the source
of `submitEnabled`. They are independent observations, not aliases.

The observer wraps only original prototype methods, preserving receiver,
arguments, return/Promise identity, and exceptions. It never constructs a
presenter, modifies its fields, or replaces its service/gateway. It reads the
original getter on the receiver captured from UI-driven calls. Missing
methods, absent calls, multiple receivers, mismatching UI values, or offscreen
required controls prevent complete coverage and remain NS.

## Parent-Owned Build Integration

Preferred generated-bundle integration (after `generate(..., {device:true})`):

```js
report.nativeUIObserver = require(
  './state_tests/runtime/arkts/native/Tasks12_15NativeUi.install.cjs'
).install(work);
```

Gate this in the parent packager on `--native-ui` and task12. The installer
copies eight evaluator modules, configures the original app module URL in
`NativeBundle.test.ets`, and adds a bridge around generated bundle lifecycle
hooks. Only `blank_reason_disabled` skips the old preliminary navigation and
calls the exported `runTasks12To15NativeUi(caseSpec, bundleName)` function.
Other cases keep the old adapter and navigation. No shared packager/executor
or production file is edited by this installer.

The adapter registers the original feature source through `load` without
constructing it. The normal loader's observation recorder registers actual
native frames/calls and the original page hash. The unchanged `evaluateCase`
compares all expected fields and the recomputed leave invariant; its row is
written through existing `persistRow` / `ARKTS_NATIVE_ROW_FILE` transport and
can use the existing `apply_arkts_device_evidence.py` verification/merge.
Installer output retains original source and evaluator hashes for the build
report. The exported probe returns failures as data; only the standalone
Hypium wrapper asserts, so a semantic FAIL does not break bundle transport.

Important: matching import paths do NOT prove runtime module identity.
`entry_test` and `entry` may contain separate ABC copies of the class. If UI
operations produce zero intercepted receivers, the probe and normal adapter
remain NS. No fallback constructs another presenter or supplies `canReport`.
The parent must verify this on device. The Task12 binding now uses its own
standard-JS `import(url)` with the manifest-bound URL
`@bundle:<bundleName>/entry/ets/features/ReportRoomFeature`, without depending
on Task11's whitelist. No relative production import is generated.

For standalone suite integration instead of the generated bundle:

Copy these evaluator files into the disposable device test target, preserving
their relative imports:

- `Tasks12_15NativeUi.ets`
- `Tasks12_15NativeUi.test.ets`
- `Tasks12_15ReportPageObserver.js`
- `Tasks12_15ReportPageObserver.d.ts`
- `Tasks12_15NativeUi.binding.js`
- `Tasks12_15NativeUi.binding.d.ts`

Configure `configureTasks12ReportPageBinding(configJson)` with the same
manifest-derived configuration returned as `binding` by the installer, then
register `tasks12To15NativeUiTests()`. Configuration stores strings only: it
does not import production. Do not import the feature using `../main`, and
never import its `@bundle` URL during suite registration. If the postload
original export is absent or cannot load, retain NS without a test-copy
fallback. Preserve the original module/page hashes in parent provenance.

Pass runner parameters `taskId=12_report_room`, `caseSpec=<the complete
canonical case JSON>`, and optional `abilityName` (default `EntryAbility`).
Use one cold candidate process per case. Do not pre-render the domain adapter
or another presenter as a fixture. The exact lifecycle is `startAbility`,
positive root/form controls and actual candidate window, postload original
module import, observer installation, then native toggle/reason setup. An
`original_page_ready_before_binding` frame records the pre-import controls.
The original presenter already exists on the page; only its prototype is
instrumented before subsequent UI calls. Each canonical frame records the
requested URL, import phase, wrapped methods, and whether a receiver was
actually observed. Register this selected UI suite
instead of concurrently running another suite that constructs presenters.

DeviceTestRunner must lazy-load the suite after `onRun`. The suite uses the
working static `Driver, ON` UiTest binding, not a dynamic OS module namespace.
Empty `findComponents` results accept both null and
an empty array. Observer cleanup runs in `finally` after the UI frames.

The canonical render event needs no submit click. Setup uses the real input
to enter exactly three spaces and the real Toggle to establish leave=true.
Two subsequent frames must show those exact givens, the same sole presenter,
original `canReport=false`, native `submitEnabled=false`, and leave remaining
selected. No SDK result is required by this particular contract. Space
normalization by the device that prevents the given stays NS.

The `task12-postload-page-binding` device row stopped after successful spaces
input with `Native toggle is unavailable`, not a runner timeout. Keyboard
occlusion is a possible cause, not an observed fact from that row. The blank
case now selects leave before input, then requests the real OS
`inputMethod.getController().hideTextInput()` (API10+) without using Back or
changing app state directly. Its action receipt records success or the OS
error; neither is treated as proof that controls are visible. All original
native-control, same-receiver, given, expected and invariant checks remain.
Other cases keep their original fixture order.

`original_page_observer_installed` and `fixture_leave_selected` checkpoints
retain import/receiver progress before text input. Exceptions retain
`failure.stage`, `message`, `stack`, `code`, and the observer snapshot before
disposal. A best-effort `failure_diagnostic_only` frame is never a canonical
event frame; a failed diagnostic capture retains its separate `captureError`.
The canonical row reason includes the underlying collection error, while its
evidence retains the complete raw result.

Parse the existing `ARKTS_12_15_UI_CHUNK` records. Full field/invariant
checks are in `canonicalAssertion`, `givenChecks`, `expectedChecks`, and
`invariantChecks`; each frame retains controls and `presenterEvidence`.
An incorrectly enabled button produces a fully observed FAIL, not NS.
The parent still owns normalized reporting, provenance, and canonical merge.

## Local Verification

`node --test state_tests/runtime/arkts/native/Tasks12_15NativeUi.test.cjs state_tests/runtime/arkts/native/Tasks12_15NativeUi.install.test.cjs`

These tests use fake UiTest/inputMethod transport and the unchanged production class
transpiled only for observer/scaffold regression tests. They are not ArkVM or
device results. Native compilation, original module identity, API23 whitespace
input, Toggle accessibility, and same-process observation still require the
parent's serialized device run. Tasks13-15 and task12 partial-leave recovery
remain outside this bounded addition.
