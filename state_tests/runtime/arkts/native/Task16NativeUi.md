# Task16 Original Page UI Diagnostics

## Bound Cases And Limits

This independent fixture targets only the two current final NS cases:

| Case | Reachable original UI path | Remaining canonical gap |
| --- | --- | --- |
| `ir_state_005_oidc_handle_routes_and_resets` | Select SSO toggle, Continue, real inline destructive confirmation, Reset identity; original async manager/service creates original OIDC handle, calls `resetOidc`, and renders the approval URL. | Rendering a URL is not `open_oidc_approval`. No actual browser launch or unavailable-custom-tab WebView fallback is established. |
| `ir_state_010_cancel_cleans_up` | Same actual OIDC path establishes success handle, active reset job and completion watcher. Physical Exit reset calls original presenter, manager and the same handle's `cancel`, then renders root again. | This is not evidence that an OIDC return and node destruction dispatch through the same cleanup path. |

Both complete diagnostic paths intentionally remain **not_scored**, with the
missing invariant unfilled. Missing classes, receiver, lifecycle, disabled
controls, or incomplete givens also remain NS. No absence of a production API
is converted to a semantic FAIL. No canonical or production repair is made.
These probes are useful additional runtime evidence, not a promise to turn
the two remaining NS into passes.

## Production Trace

Immutable candidate currently read:
`final_dev_nodes/16_identity_reset_final_0_5_1/`.

- `entry/src/main/ets/pages/Index.ets` owns the original service, manager and
  presenter. Its SSO toggle configures the original service; Continue opens an
  inline confirmation block (not an OS dialog). Confirm starts the original
  async operation and refreshes before and after completion.
- `entry/src/main/ets/features/IdentityResetFeature.ets` contains the actual
  `DemoIdentityResetService`, `IdentityResetFlowManager`,
  `IdentityResetPresenter` and `DemoOidcResetHandle`. The fixture never replaces
  these classes or methods with business implementations or SDK callbacks.
- The OIDC page displays a Text URL and an Approval completed button. It does
  not itself establish an external browser/WebView launch. The probe does not
  press Approval completed and relabel it as an OIDC browser return.
- `entry/src/main/ets/entryability/EntryAbility.ets` loads `pages/Index`.
  Actual AbilityMonitor/ApplicationContext callbacks provide lifetime evidence;
  the probe does not invoke a fabricated destruction hook or call a retained
  presenter after its page is gone.

The original Demo service/handle have no Matrix SDK/network transport. No such
transport is claimed. The fixture does not write any presenter, manager,
service or handle state; all setup comes from real controls. Host tests fake
OS/UI transport only, never count as device semantic evidence.

## Identity And Observation

`Task16Launch` registers the AbilityMonitor and ApplicationContext lifecycle
listener before launch, then bounded-polls actual root readiness. Each query
checks original foreground/top ability, observed WindowStage main ID, actual
last-window ID, matching UIContext host, native focused window and geometry,
and original `pages/Index` route. No fixed long startup sleep is used.

Only after this positive root/window evidence does standard JS `import(url)`
bind `@bundle:<candidate>/entry/ets/features/IdentityResetFeature`. There is no
static relative production import or duplicate-ABC fallback. Original method
observers retain receiver, arguments, original return/Promise identity and
exceptions; they add no Promise handlers. Disposal restores descriptors.

Continue captures the actual original page receiver before confirm. All later
checkpoints must retain its presenter/manager/service IDs and window/context.
Handle IDs connect the real OIDC call to the later physical cancellation.
The transient canonical loading state for case005 is recorded at the original
`getResetHandle` synchronous return while its Promise is pending, explicitly
**not** claimed to be a rendered loading frame. Settled OIDC UI observations
are captured separately.

Case005 exports only observed `handleState`, `url`, and `pollEffect` with its
browser/fallback gap. Case010 exports all four expected values only after the
actual cancellation call chain, but retains its lifecycle invariant gap. The
shared evaluator must preserve NS, not promote incomplete rows. Neither probe
performs an actual browser return or destroys the app to substitute for a
production navigation callback.

## Parent Integration

Parent owns all HAP compilation and device activity and has now executed both
cases below. The worker only audited retained evidence, without device access.
Select this installer only for task16 case005 or case010 in the generated
native-UI packaging branch:

```javascript
require('./state_tests/runtime/arkts/native/Task16NativeUi.install.cjs').install(work);
```

Standalone equivalent:

```sh
node state_tests/runtime/arkts/native/Task16NativeUi.install.cjs WORK
```

Keep the returned manifest in the existing `nativeUIObserver` build evidence.
The installer changes only generated test suite/native bundle lifecycle and
copies independent Task16 evaluator files. It embeds the dependency-free
adapter as an ES module; no new external CJS factory dependency is introduced.
It preserves shared `evaluateCase`, `persistRow`, canonical file transport,
and other cases' adapter dispatch. Production hashes are checked before/after.
There is no change to shared `Tasks16_18`, shared packager/executor, production,
or contracts. Do not install multiple UI installers into this generated bundle.

Interfaces:

- `runTask16NativeUi(caseJson, bundleName, driver, ON, launch)` returns JSON raw
  page evidence, frames, receipts, loading checkpoint and explicit coverage gap.
- `bridge.runTask16UI(caseSpec)` attaches production source provenance.
- Independent `Task16NativeUi.adapter.cjs.runCase(args)` retains the native
  evidence and produces incomplete observed values plus explicit unsupported
  reason for the unchanged shared evaluator.

## Host Verification

```sh
node --test state_tests/runtime/arkts/native/Task16NativeUi.test.cjs
```

Seven passing host regressions cover original async OIDC behavior, physical
Exit cancellation through the same handle, missing/disabled/window/duplicate
binding guards, provenance/action receipts, Promise identity, isolated
installer/transport, and interception limited to the two cases. These validate
the scaffold against unchanged production feature code with fake OS/UI
transport. They are not native UI results. Parent's actual device replays below
also retain NS for the two incomplete cases; neither justifies promotion of the
final 8P/0F/2NS matrix.

## Actual Device Evidence

Both raw rows were checked against their `device-execution.json` artifact
hashes and canonical case digests, then read through the unchanged independent
adapter. This evidence replay reproduced the observed fields and same original
receiver/context binding; it is not an additional device execution. Both
transport records attest a fresh install and production unchanged. No fixture,
production source, contract or assertion was changed during this audit.

### Case005: OIDC Entry

Evidence directory:
`experiment_results/runtime_transition_20261019/device-calibration/task16-real-oidc-entry/`.

- `native-result.json`: **not_scored**, 64773 bytes, SHA-256
  `aced60fe6a149d39de73c983db29768661593813414d0403b5215a6f179b8945`.
- Execution nonce: `570509275e80ab2a5b8a9feb0ddc4f94`.
- Canonical digest:
  `05b6ba2ddca9261f000f3a636ba30619d00ac898408a4a697eb088b9e52d84f9`.
- Physical OIDC toggle, Continue and Confirm clicks are recorded at sequences
  2, 3 and 5. Sequence 4 observes the actual visible/enabled inline confirmation
  on the original root page; sequence 6 observes the OIDC page and visible URL.
- Original presenter/manager/service IDs remain 1 on window 126,
  `pages/Index`. Original handle ID 1 receives `resetOidc`. The original manager
  synchronous-return snapshot records `loading` with authentication `oidc`;
  this is not described as a rendered loading frame.
- Actual exported observations are `handleState=success`,
  `url=https://id.example/reset`, `pollEffect=reset_oidc`.

`effect=open_oidc_approval` and the fallback-WebView invariant remain missing.
This run establishes original UI/handle execution, **not** a browser launch,
browser absence across all execution paths, or custom-tab fallback behavior.
The observed URL remains text evidence only, and no missing browser API is
converted to FAIL.

### Case010: Physical Cancel

Evidence directory:
`experiment_results/runtime_transition_20261019/device-calibration/task16-real-cancel-cleanup/`.

- `native-result.json`: **not_scored**, 92153 bytes, SHA-256
  `ba74dbfd1a71a082cd5cebcccb39df8c933b5c2a91eeb29764b0fff61f2acfc2`.
- Execution nonce: `70a3d8469c992c7d954713f11dfb0e7e`.
- Canonical digest:
  `7e89fb15e0ae6f65fc8fd7b4c17e9b9aefd4025092952fbb30bb59a081e503dd`.
- `before_event` sequence 6 establishes the canonical success handle, active
  reset job and active completion watcher, with actual visible/enabled Exit
  reset on the OIDC page. Its handle ID is 1 and `cancelled=false`.
- Physical Exit reset at sequence 7 calls original presenter.cancel,
  manager.cancel and handle.cancel on that same handle. `after_event` sequence
  8 has `handleState=uninitialized`, `resetJobActive=false`,
  `completionWatcherActive=false`; retained handle evidence is `cancelled=true`
  and the manager no longer holds it. The native Continue control is visible
  again on the root screen.
- Presenter/manager/service IDs remain 1, window 127 and `pages/Index` remain
  unchanged. This is a screen-state change inside the live original page, not
  proof of router navigation or node destruction.

All four expected fields are observed, including the actual cancellation
effect. The invariant `OIDC return and node destruction use the same cleanup
path` remains unobserved. Exit reset alone does not establish either lifecycle
path, so this case remains NS rather than a full semantic PASS.

Both device rows record the same production hashes:

- `entry/src/main/ets/features/IdentityResetFeature.ets`:
  `db5fd86eb665395758248c0a23c03bfaeb5f5df083ad290e3eaf3eb4d829eb19`.
- `entry/src/main/ets/pages/Index.ets`:
  `31c3c89d717870fc2d487eeabd213f6696d1e391f81fe9af9e0ea75ec63b28fd`.

The executed service and handle remain the original in-memory Demo types.
Neither run is evidence of Matrix network/SDK behavior. No other task or case
is covered or modified by this documentation audit.

Files: `Task16PageObserver.js`, `Task16Launch.js`, `Task16LaunchNative.js`,
`Task16LaunchNative.d.ts`, `Task16NativeUi.js`, `Task16NativeUi.d.ts`,
`Task16NativeUiSuite.ets`, `Task16NativeUiBridge.js`,
`Task16NativeUiBridge.d.ts`, `Task16NativeUi.adapter.cjs`,
`Task16NativeUi.install.cjs`, `Task16NativeUi.test.cjs`, and this document.
