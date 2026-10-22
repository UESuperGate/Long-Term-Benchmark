# Task13 Original Profile UI Probe

## Status

Independent evaluator fixture, ready for parent integration. No device run or
native build was performed for this change. The 18 host regressions validate the
evaluator wiring, not native UI success. Canonical scoring remains exclusively
in the shared `evaluateCase`; this module never creates a score.

Only `profile_routes_user_request` is handled. Other cases keep their existing
path. Production, canonical contracts, shared adapters, and generic installers
are unchanged.

## Source Audit

Candidate: `final_dev_nodes/13_user_verification_final_25_03_2`.

- `entry/src/main/ets/pages/Index.ets:15-23` constructs the original identity
  store and presenter with a User request for `@alice:example.org` before any
  profile action. The identity store describes the profile target, not the
  currently authenticated account.
- `Index.ets:35-40` renders that profile. Lines 68-75 expose `verify_user_action`
  and call that same presenter's `requestVerification`, then `refresh`.
- `Index.ets:76-90` renders waiting/accept/cancel controls on the same page.
  No navigation call or distinct verification route is implemented here.
- `UserVerificationFeature.ets` implements the User/current-session request
  distinction and gateway calls. The gateway is the candidate's own migrated
  counter implementation, not a real Matrix service and not an evaluator fake.
- The base page lacks this action. Missing action/module remains unavailable,
  never an inferred semantic failure.

The profile ID and actionable Verify control are observable. Canonical
`given.isCurrentUser=false` has no authoritative current-account source on this
entry path. Canonical `expected.route=verify_user` is not established by the
presenter step or an existing request. These two boundaries stay explicit NS.
This is a source-confirmed migration coverage gap, not a native semantic FAIL.

SHA-256 at audit:

| Input | SHA-256 |
| --- | --- |
| Original page | `dc78c8debd4f3e3e6efef8f5afd4428177f3dca79f192f3465198d7e8dda1c8c` |
| Original feature | `f90fc9abcc4df2a01b9c88bb1f4dd17b68ce9f492f2ce3593fd805afc9570387` |
| Task13 transitions.json | `745b24bb407931840849c70748b1d50156f053924aba60660b7711fe820038c8` |

## Parent Integration

After generating the ordinary native-device work directory, before build:

```sh
node state_tests/runtime/arkts/native/Task13NativeUi.install.cjs /absolute/generated/work
```

The installer modifies only disposable generated test files, adds three fixture
files, and verifies production hashes before/after. It does not add a fourth
CJS factory. It rejects changed lifecycle tokens and duplicate installations.
The existing generic installer must not subsequently overwrite these files.

Parent adds the following early branch to shared `tasks12_15.cjs` `runCase`,
after its `native` resolution and before domain context construction:

```js
if (args.taskId === '13_user_verification' &&
    args.caseSpec.key === 'profile_routes_user_request' &&
    typeof native?.evaluateTask13UI === 'function') {
  return native.evaluateTask13UI(args);
}
```

No shared files were edited here. Without that branch this fixture is not a
replacement for the existing domain adapter and must not be counted as UI
coverage. The installer exposes `bridge.evaluateTask13UI(args)` and disables
generic navigation only for its handled case. It attaches before the shared
observation recorder is registered and restores observer descriptors on dispose.

## Runtime Evidence

1. Launch the original manifest ability and obtain its actual SDK Context and
   window UIContext in memory. Never serialize or clone the Context.
2. Capture a completed mounted profile frame and require the candidate focused
   window, actual profile text, and visible/enabled/clickable original control.
3. Only then dynamically import the candidate's original app module URL and
   install pass-through prototype observers. No presenter/gateway is constructed
   by the fixture, and original return values/exceptions are preserved.
4. Capture `before_event`; perform the real UiTest Component click; capture
   `after_event` with actual router state and rendered controls.
5. Match the original presenter receiver with its nested original gateway
   receiver. Record request, step, counters and identity target before/after.
   Missing/duplicate receivers, wrong module binding, incomplete frames or
   missing click evidence do not establish an observation.

The returned object contains raw evidence/checkpoints, observed request fields,
and the exact canonical self-session request-type invariant. It deliberately
does not invent `observed.route`. Actual router name/path/index and screen
controls are retained for audit. `unsupportedObservations` names route and the
non-self GIVEN boundary; the shared evaluator therefore retains NS even when
the original request and invariant are observable. Canonical fields, digest,
expected values and invariant text are unchanged.

Incremental checkpoints survive query/click failures. A cooperative 35-second
native budget and 45-second bridge watchdog bound observation; watchdog expiry
prevents subsequent fixture UI actions and retains partial evidence.

## Verification

```sh
node --check state_tests/runtime/arkts/native/Task13NativeUi.install.cjs
node --test state_tests/runtime/arkts/native/Task13NativeUi.test.cjs
```

18 host regressions pass, including execution of untouched transpiled production
presenter methods, shared `evaluateCase` integration, original receiver binding,
negative binding/identity/action cases, installer production immutability and
factory count, UiTest ordering, SDK Context identity, and partial failure
evidence. Synthetic external SDK/UI boundaries in these regressions are test
fixtures only. They are not device evidence or benchmark PASS results.

The parent-reported `arkts-limited-throw` failure is repaired by rethrowing a
new `Error`, preserving the original message/stack and serialized error info in
the partial frame. Added regressions cover SDK Error fields, primitive throws,
and circular serialization fallback. Native recompilation remains pending.

Native compilation and device evidence remain parent-owned follow-up work.
