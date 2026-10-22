# Tasks 08-11 Native Fixture Handoff

No production, archived patch, canonical contract, or shared runner is edited.
All original case IDs and digests are retained. Missing APIs/givens remain
`not_scored`, not a source-absence failure.

## Same-Page Room State

`Tasks08_11RoomObserver.js` wraps original presenter methods/getters with
pass-through calls. It does not create a presenter, inject a result, replace
business logic, or mutate room/gateway state. Returns, promises, receivers, and
exceptions are preserved. Read snapshots include actual retained room history,
predecessor event ID, current room, navigation state/counter, and stable
presenter/store/gateway identities. Disposal restores property descriptors.

Install BEFORE mounting the candidate page, from the same original `.ets`
module imported by that page. ArkTS forbids importing `.ets` from JS, so the
generated ArkTS Hypium entry passes the original class to
`configureRoomObserver`. JS then calls `installConfiguredRoomObserver()`.
Attach its returned object as `context.native.roomUpgrade`. Never pass a class
from the transpiled domain bundle: that would observe a different instance.
On device, installation must run in the candidate's own engine/module cache;
installing the observer in a separate instrumentation process is insufficient.

`Tasks08_11NativeUi.install.cjs` implements this wiring in a disposable generated
`--native-ui` bundle only. It supports the original `RoomUpgradeFeature` and
alternative `RoomFeature` APIs, with no role-dependent verdict. It does not edit
the shared bundler or candidate source. The parent may call `install(work)`
after bundle generation, before compilation.

## UI Transport Requirements

The adapter uses `native.ui.observe(ids, anchor)` and `sendEvent(id, 10, {})`.
An optional asynchronous `native.ui.click(id)` takes precedence over keyed
events. It must click the actual enabled candidate control, not invoke a
presenter method. Optional `native.ui.doubleClick(id)` performs the native
double-click gesture; otherwise two immediate keyed events are diagnostic only.

The local Previewer accepted keyed click dispatches (`true`) while no original
`openSuccessorRoom`/selection method executed. Navigation count stayed zero and
the rendered/current room remained unchanged. The adapter explicitly checks
the original callback invocation and leaves this condition unscored. It must
not be interpreted as a candidate failure or successful navigation.

Required parent infrastructure:

- Real candidate UI click transport that demonstrably executes the original
  callback. No device serial was used by this fixture.
- Same-page observer installation before page creation, and disposal after
  page teardown. Preserve source and generated bundle hashes in native reports.
- Candidate-owned route verification for the alternative `pages/RoomDetail`
  route; the current bridge accepts only `pages/Index`. Do not disable route
  verification or treat the Hypium host as a candidate page.
- Rendered destination room-ID observation on alternative pages without
  `current_room_id`; do not infer it solely from callback payload/state.
- Full native tree/text selectors for the baseline flat home list, which has
  no stable keyed anchor. The Previewer inspector tree may omit children.
- An independent binding for `tombstone_is_read_only.given.composerEnabled`.
  The final page is constructed with tombstone metadata and exposes only the
  already-derived `canCompose` getter. Neither its hidden composer nor that
  derived getter establishes the canonical pre-render input `true`. The native
  path now keeps this fixture unscored pending a real input boundary; this is
  not permission to change the canonical contract.

The adapter records native viewport/visibility, positive anchors, original
metadata before/after, and actual navigation counters. Single-click canonical
observations are frozen before a separate double-tap probe. The latter never
adds/changes a canonical case or invariant; its failure cannot overwrite the
canonical single-click result. Model-only UI booleans are not used on this path.

## Bounded Local Verification

```sh
node --test state_tests/runtime/arkts/tasks08_11.test.cjs state_tests/runtime/arkts/tasks09_10.test.cjs
node state_tests/runtime/arkts/native/Tasks08_11Previewer.cjs base /tmp/Tasks08_11-base-proof
node state_tests/runtime/arkts/native/Tasks08_11Previewer.cjs final /tmp/Tasks08_11-final-proof
node state_tests/runtime/arkts/native/Tasks08_11Previewer.cjs agent /tmp/Tasks08_11-agent-proof
```

Run Previewer commands serially. The helper refuses to run alongside another
Previewer/native build, invokes no `hdc`, bounds build time, and removes its
temporary candidate project. JSON reports contain compile/transport status
separately from per-case semantic verdicts and unchanged-source checks.

Initial final11 proof compiled and ran unchanged native `.ets` and ArkUI with
the observer. It exposed the keyed-click no-op limitation above. This is NOT
full base/final calibration. Host tests execute all four tasks base/final first,
then reconstruct unchanged archived patches; they are domain regressions, not
native UI proof or a fresh agent run under revised public inputs.

The intermediate `/tmp/Tasks08_11-reviewed-final/Tasks08_11-report.json` recorded
three passes before the independent composer-input guard was added. Its
`tombstone_is_read_only` pass is superseded by that guard, not final calibration.
The base native report confirmed the actual composer/root in all six cases;
all six remain unscored because upgrade givens are unavailable.

The current `/tmp/Tasks08_11-final-given-guard/Tasks08_11-report.json` compiles,
runs all six unchanged case IDs, and verifies unchanged production hashes:
two passes (room-list preview and native-domain metadata mapping), four
unscored (composer input, successor click callback, and both predecessor
fixtures). Double-tap code is prepared but has not produced genuine UI evidence
because its prerequisite single-click path is unavailable. Native archived-agent
replay was deferred when the shared build slot was busy; host archived replay
completed as diagnostics. Full calibration is not claimed.

Base production still lacks thread context, Space lifecycle inputs, media
quality/metadata inputs, and upgrade metadata ingestion. Ordinary room sends,
home selection, original uploads, and room opening can execute, but cannot
establish those canonical givens. The adapter records this partial execution
and actual native entry observations where available. An absent selector alone
does not authorize a semantic failure, and no fabricated post-state is emitted.
