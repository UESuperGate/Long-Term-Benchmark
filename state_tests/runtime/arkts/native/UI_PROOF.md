# Native UI Entry Evidence v1

Adapter API: `await native.ui.probeEntry(targetId, anchorId)`. Available through
both `args.native` and `args.context.native`; enable single-candidate
`--native-ui --bundle TASK --role ROLE --source CANDIDATE`.

The bridge returns facts, not a semantic failure. `backend` is
`native_previewer_arkui`, not a device or complete OS claim.

```js
{
  schemaVersion: 1,
  kind: 'native_ui_entry_probe',
  backend: 'native_previewer_arkui',
  caseId: 'TASK:ROLE:CASE',
  instanceId: 'unique native context/sandbox identity',
  observationId: 'unique probe identity within this instance',
  candidateRoute: 'pages/Index',
  before: {
    capturedAt: 0,
    available: true,
    route: { index: 2, path: 'pages/', name: 'Index' },
    candidateRouteVerified: true,
    fullTreeAvailable: false,
    anchor: {
      selector: { kind: 'arkui_id', value: 'leave_room' },
      present: true,
      node: { type: 'Button', nativeId: 22, bounds: '[60,634],[1020,754]',
        visible: true, enabled: true, label: 'Leave room' }
    },
    target: { selector: { kind: 'arkui_id', value: 'submit_report_room' },
      present: false, node: null }
  },
  action: {
    api: 'sendEventByKey',
    selector: { kind: 'arkui_id', value: 'submit_report_room' },
    action: 10, params: {}, attempted: true, attemptedAt: 0,
    delivered: false
  },
  after: { /* same observation shape, freshly queried after the attempt */ },
  available: true,
  prerequisiteChecks: [/* route, anchor, selector and native delivery checks */],
  selectorReachability: 'absent_action_rejected',
  taskEntryReachable: null,
  givenEstablished: null,
  semanticVerdict: null
}
```

This illustrative shape is not evidence. Retain the actual returned values.
If the anchor/route is unverified, target presence is null and no event is sent.
An exception, accepted event, or changed/unverified page cannot produce
`absent_action_rejected`. A present control does not prove task entry reached.
`fullTreeAvailable: false` means keyed evidence only: it cannot exclude renamed
controls, alternate navigation, offscreen controls, or other entry routes.

## Implemented Early Assertion

`entry-assertion.d.ts` defines the discriminated `EntryAssertion` type.
`entry-assertion.js` implements creation and independent revalidation. The
implemented discriminator is **`kind: 'runtime_entry_assertion'`**; this replaces
the earlier proposed `runtime_precondition_failure` name. The raw UI probe type
is unchanged. Actual assertions are emitted inside
`platform.entryAssertion.assertion`; `platform.entryAssertion.assessment` is a
separate verdict, never an implicit semantic pass from the Hypium wrapper.

```js
{
  schemaVersion: 1, kind: 'runtime_entry_assertion', failPhase: 'entry',
  taskId, role, caseId, traceDigest,
  policyId, policySha256, sourceSha256,
  givenChecks: [ /* one explicit same-instance binding for EVERY given field */ ],
  probes: [ /* actual per-selector native probe results, one fresh case instance */ ],
  prerequisiteChecks: [ /* references into those probes */ ],
  postState: null,
  transitionExecuted: false,
  invariants: { evaluated: false, unobserved: [ /* canonical invariant descriptions */ ] }
}
```

Policies are external evaluator inputs, not adapter-provided approval claims.
They bind one exact canonical case/event/trace, candidate page SHA-256, route,
positive anchor, exhaustive entry selectors, and explicit given-to-observation
rules. `approval: pending` or incomplete selector review always yields NS.
Missing givens, source drift, alternate unattempted selectors, reused probes,
wrong cases, unmounted/offscreen anchors, unattempted/errored actions, and
invented post-state/invariants also yield NS. The validator recomputes these
conditions; it does not trust prerequisite `passed` flags. No broad task/role
absence rule exists.

### Parent Integration

After normal canonical identity/native provenance validation, recognize this
discriminator BEFORE demanding transition post-state/invariants. Call
`assessEntryAssertion(assertion, canonicalSpec, trustedPolicy, executionBinding,
usedObservationIds)`. Only a returned `status: fail` permits an entry-phase
failure. Never accept a pass from this branch. Record `postState: null` and
invariants as unevaluated; do not fill missing expected fields. Maintain a
report-wide consumed observation-ID set to reject reuse across rows. Cases
without this typed assertion retain the existing full-field validator.

The independent CLI also checks current production/contract/policy hashes,
actual Previewer process/library evidence, bytecode/log hashes, and reconstructs
the assertion from native log chunks to detect report-only modifications:

```sh
node scripts/runtime_semantics/arkts_native_entry_validate.cjs \
  --report /absolute/path/to/platform-report.json \
  --policy state_tests/runtime/arkts/native/entry-policy-task14-initial.proposed.json
```

The proposed task14 policy deliberately remains pending. It covers ONLY
`jr_state_001_entry_opens_address_flow`. Parent review must confirm that the
source-bound start-chat anchor and empty/unfocused search establish the two
canonical givens and that selector coverage is exhaustive. Changing approval
changes the policy hash, so rerun the actual case after approval; old smoke
records cannot be promoted retroactively.

```sh
node scripts/runtime_semantics/arkts_native_smoke.cjs \
  --probe-platform --source 14_join_room_by_address_base_25_02_0 --role base \
  --entry-policy state_tests/runtime/arkts/native/entry-policy-task14-initial.proposed.json \
  --output-dir experiment_results/runtime_transition_20261019/native-entry-assertion/task14-initial
```

No independent-validator or adapter files outside native infrastructure are
modified by this implementation. The standard matrix remains unchanged until
the parent reviews and wires this branch.

## Earlier Envelope Rationale

The parent evaluator, not the bridge, owns this semantic envelope:

```js
{
  schemaVersion: 1,
  kind: 'runtime_entry_assertion',
  failPhase: 'entry',
  taskId, role, caseId, traceDigest,
  given: { canonicalDigest, established: [/* fact + evidence reference */],
    unestablished: [/* every unresolved canonical precondition */] },
  entryContract: { contractDigest, requiredSelector, anchorSelector,
    requiredRoute, candidateSourceSha256, justification },
  prerequisiteChecks: [
    // Copy the ACTUAL probe checks; append separately established given checks.
    // Each evidence pointer resolves in the matching observation, never another case.
    { id: 'positive_anchor_rendered', expected: true, observed: true, passed: true,
      evidence: [{ observationId, pointer: '/before/anchor' }, { observationId, pointer: '/after/anchor' }] },
    { id: 'required_selector_present', expected: true, observed: false, passed: false,
      evidence: [{ observationId, pointer: '/before/target' }, { observationId, pointer: '/after/target' }] }
  ],
  uiProof: /* actual native.ui.probeEntry return value */,
  nativeEvidence: { reportPath, bytecodeSha256, nativeLogSha256,
    productionSourceSha256 },
  blockedTransition: { canonicalActionId, reason: 'required_entry_unavailable' },
  postState: null,
  invariants: { evaluated: false }
}
```

Validation requirements:

1. Bind case/role/task/trace/given/source digests to the exact current candidate
   and canonical scenario, and resolve report/log/bytecode evidence. Require
   actual native execution; generated-wrapper compilation is not app compilation.
2. Require a fresh mounted candidate page per case, unique instance/probe IDs,
   verified route and visible nonzero-bounds positive anchor before and after.
   Check timestamps bracket the actual attempted action.
3. Require missing target before/after and native `delivered === false`.
   A thrown action or missing class/module is not negative UI evidence.
4. Review the selector contract against this candidate and canonical action.
   Establish which entry routes were required/exhausted. Missing one ID alone
   cannot establish feature absence or make `taskEntryReachable` false.
5. Independently validate relevant given/setup evidence. Do not pretend
   unestablished preconditions were satisfied. A case requiring prior state
   mutation or service setup stays NS if those cannot be established.
6. Accept this distinct precondition outcome only when the canonical contract
   explicitly permits failing at that entry stage. Do not require invented
   post-state fields, but do not count unevaluated invariants as passing or
   claim the canonical transition ran. Otherwise retain NS.
7. Reject reuse of one root marker/probe across cases. Fresh probes alone do
   not make unrelated cases eligible: each must independently satisfy 1-6.

The sketch in this rationale section is not the executable schema; use the
typed implementation above. Parent validation decides whether the reviewed
entry-contract evidence permits a failure or remains NS.

The raw probe emits four prerequisite checks: `candidate_route_mounted`,
`positive_anchor_rendered`, `required_selector_present`, and
`native_entry_action_delivered`. `passed` is null for an unobservable target or
unattempted/errored action. These are UI transport facts only. Native delivery
can be true even for a disabled button; it does not prove business execution.
There is no generic `feature_available` field. Canonical `given` checks are never
auto-generated. `platform_probe` smoke observations are not case-scoring inputs.
