# Device UI Integration

Status: post-page original-app import and physical-click receiver capture
succeeded in the parent's task11 device diagnostic. Twenty-six local tests
cover transport and existing adapter handoff; these tests are not native UI
proof. Pre-start import remains prohibited after its observed ArkVM fatal.

Two explicit modes are supplied to the installer or through
`TASKS08_11_ORIGINAL_MODULE_IMPORT`:

- `after-page-ready-diagnostic`: retains the existing always-unscored probe.
- `after-page-ready`: permits only `ru_state_005_room_list_tombstone_preview`
  and `ru_state_007_predecessor_banner`, with identical behavior for all roles.
  After a fresh original page is verified, import and instrument, then click
  the actual old-room control to capture its receiver. Require an observed
  instance/call and agreement between current room state and real room text.
  Deliver the actual observer to the unchanged canonical adapter, which must
  independently establish its given and execute all observations/invariants.
  Case007 selects the replacement room through its real UI control. Other
  case IDs are rejected before startup/import. No success verdict is emitted
  by the transport; `setupReceiverCapture.canonicalSetupVerified` stays false.

Default `disabled` does not import/instrument a production class; its read-only
unavailable response keeps affected cases unscored. Unsupported mode names fail
installation. Cache misses may still cause native fatal; never treat JS
try/catch as protection from SIGABRT. The diagnostic success is specific to
this candidate/device and does not certify tasks12/18 or other firmware.

## Parent Hook

In the disposable device bundle workspace, immediately AFTER the existing
`Tasks08_11NativeUi.install(work)` call for task11, invoke:

```js
report.deviceUI = require(path.join(root,
  'state_tests/runtime/arkts/native/Tasks08_11DeviceUi.install.cjs')).install(work);
```

No shared platform modification is required. Capture generated evaluator
hashes after both installers. The companion installer rejects Previewer
bundles, duplicate installation, and changed/missing observer hooks. It reads
the copied candidate app/module/pages manifests using the same cached JSON5
parser as the parent packager. An optional `json5` parser can be supplied.

Only generated `entry/src/test` is changed: copy the DeviceUi `.js`, `.d.ts`,
`.core.js` and `.binding.js`; remove the test suite's relative production-class
import and `configureRoomObserver` call, and configure the native module with
the manifest-derived original app OHM URL. Replace the observer-install assignment
with `await augment(bridge)` before the existing `bridge.ui.navigate` call.
No candidate source, shared platform, adapter, or contract is changed.

## Ordering And Evidence

`configureDeviceUi(config)` registers an async original-module factory.
In either opt-in mode, `augment(bridge)` first starts the original ability
and verifies the real candidate window, entry route, full tree and Driver room
anchor. Only then it awaits standard `import(url)` for
`@bundle:<candidate bundle>/<original module>/ets/features/<original feature>`.
It instruments that namespace's actual presenter export using the existing
observer. It records the requested URL, completed import, namespace export names,
prototype descriptors and actual wrapped member names in `originalModuleBound`.
No presenter is constructed and no product method is invoked during binding.
Runtime module identity still requires real page-generated calls, not merely
successful import. Missing exports or zero wrapped members remain unsupported.
ApplicationContext ability lifecycle and AbilityMonitor listeners are registered
before the manifest's entry ability starts, allowing it to resolve the
actual foreground candidate window and its UIContext. It requires an observed
cold create, foreground callback, matching top ability and matching host
context. The real lifecycle callback supplies a WindowStage; its
`getMainWindow().id` must match `getLastWindow(ability.context).id`. Driver's
focused bundle window geometry must match both native window rectangles.
This rejects a top dialog even with matching bundle/context/route. Runtime
window type and SDK enum value/type are diagnostic only: this device does
not export the declared `TYPE_MAIN`. No numeric fallback is used.
After diagnostic binding, one actual Component click on
`room_list_tombstoned_room` attempts natural receiver capture. No getter or
presenter method is invoked to manufacture a receiver. `diagnosticReceiverCapture`
records original calls/state and before/after room text. The case deliberately
remains unscored because this setup click may change product state. Diagnostic
markers are also emitted to the process log before import and after binding.
Run exactly one case per cold process; a prestarted ability is an
unsupported setup, not a semantic failure. The bootstrap `navigate` verifies
the existing real entry route; it never pushes an evaluator route.

`ui.observe` combines bundle-scoped Driver queries with scoped keyed ArkUI
inspection. Bounds/text/enabled come from Component methods, window dimensions
from UiWindow.getBounds. Visibility/opacity are included only when actually
present in the matching keyed inspector node. Missing attributes stay absent;
accessibility presence is not a substitute for rendered visibility/occlusion.
Null/undefined `findComponents` results are normalized to empty arrays, never
positive anchors or clickable controls. Other non-array results still throw.
Each snapshot retains the complete inspector payload once under `tree`, with
`inspectorTreeField: 'tree'`; original inspector dimensions are preserved under
`inspectorTreeDimensions` because `tree.width/height` use Driver measurements.
All original child nodes/attributes remain; no trimmed tree replaces evidence.

`ui.click`, `ui.doubleClick` and parameterless `ui.sendEvent(id, 10, {})`
invoke actual Component methods after route, uniqueness, enabled, clickable
and viewport guards. Other event actions throw. Before/after evidence is
buffered until the existing runtime recorder attaches; case IDs are retained.
The shared runner already persists these startup observations in `row.calls`;
this was confirmed in the stage-lifecycle device artifact. No duplicate row
attachment is introduced, and semantic verdicts are unchanged.
Successful gesture completion carries `semanticSuccess: null`. The existing
task11 adapter must still verify original presenter calls, navigation state,
displayed room ID, retained metadata, state-owner and gateway identities.

Cleanup unregisters both lifecycle listeners and restores observer descriptors; parent
owns app/process reset. It does not terminate or rewrite the candidate.

## Bounded Check

```sh
node --test state_tests/runtime/arkts/native/Tasks08_11DeviceUi.test.cjs
```

Historical pre-start build output: `/tmp/Tasks08_11DeviceUi-original-app-import-20261019/`, selected
case `ru_state_005_room_list_tombstone_preview`. The test ABC contains a standard
`dynamicimport` instruction and the original `/entry/` request URL, and no native
`entry_test@entry.ets.features.RoomUpgradeFeature` record. Production hashes are
unchanged; temporary build/disassembly workspaces were cleaned. The generated
pre-installer suite artifact is not authoritative; inspect post-install hashes
and the actual HAP ABC instead.

Do not rerun the historical pre-start HAP. The opt-in post-load diagnostic uses
`/tmp/Tasks08_11DeviceUi-postload-diagnostic-20261019/`; parent owns any device
attempt. If it still fails, checkpoint and stop this import route rather than
retrying paths or guessing private APIs. No all-pass claim follows from
host tests, native compilation, callback delivery or gesture completion.
