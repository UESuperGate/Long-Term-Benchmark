# Canonical Transition Contract

The canonical contract is platform-neutral and evaluator-owned:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "owner": "evaluator",
  "cases": [
    {
      "caseId": "ll_start_success",
      "key": "start_success",
      "functionalArea": "lifecycle",
      "given": {"activeShares": [], "permission": "granted"},
      "event": {"name": "startShare", "roomId": "!room"},
      "expected": {
        "state": {"activeShares": ["!room"]},
        "effects": ["persistExpiry", "startCoordinator"],
        "ui": ["liveLocationBanner"]
      },
      "invariants": ["other room state is unchanged"],
      "evidence": {"androidProduction": ["..."], "androidTests": ["..."]},
      "traceDigest": "sha256-of-normalized-taskId-key-given-event-expected"
    }
  ]
}
```

Legacy digests hash `taskId`, `key`, `given`, `event`, and `expected` as JSON with sorted keys and compact separators. Versioned action-prefix cases additionally hash `setup` and `invariants`; cases with `traceSchemaVersion: 2` also hash that discriminator and invariants even without setup. Use the packaged generator rather than recomputing legacy digests for revised cases. Preserve revision/execution metadata. Platform bindings point to the same digest and never alter the semantic payload; all invariants are compared across platforms, including legacy cases whose digest omitted them.

## Case Design Rules

- One case proves one meaningful state transition or one atomic initial-state constraint.
- Observe state and externally visible effects, not class names or exact implementation shape.
- Include negative assertions when absence matters, such as no duplicate dispatch or no leaked status text.
- Exercise async completion explicitly: request, loading, success/failure, and cleanup are separate phases when observable.
- Inputs must be reachable at the chosen production boundary. For derived state, supply its real upstream inputs and observe the derivation; replacing the derivation with fixture constants invalidates the case. A writable or nullable presenter property is not, by itself, an external fixture input. Distinguish unit conventions and numeric rounding when translating across platforms.
- When correcting an established contract, preserve its old payload/digest, upstream runtime evidence, revision rationale and authorization. Regenerate both platforms from the same revised contract and revalidate every role; do not combine old and new case scores.
- When one case needs several runtime probes, declare the required probes as one mutually exclusive combination keyed by the canonical `key`. Every required probe must contribute exactly one row for that key. Reject duplicate, missing, unknown, or overlapping key ownership; never select whichever probe happened to pass or combine rows from different contract revisions.
- A persistence assertion requires the production store and actual backing I/O, including reopen when restoration is claimed. An in-memory substitute can test caller behavior but does not establish persistence.
- Keep unchanged regression tests outside the polarity set because base must fail every scored case.
- Benchmark semantic tests require runtime execution of actual production transitions, including before/after observations and effects. Source observers are diagnostics only. Unavailable runtime or missing observation bindings produce `not_scored`. Compile failures or missing APIs do not establish semantic failure, and domain-only execution does not establish native UI/OS behavior.
- Observe effects at the depth the contract requires: a navigation callback proves a request, not successful navigation or a visible destination. Keep callback payload diagnostics separate from actual navigator/backstack observations on both platforms.
- A real missing-entry probe does not observe later canonical state. Never fill the expected shape with guessed idle/false/empty values or mark all later invariants false. Under an independently reviewed common-start/action-prefix policy, an early semantic failure must retain the actual UI/flow observation and positive control, use `observed: null`, and list later expectations/invariants as unobserved. Compilation errors, missing symbols, or an unestablished common start remain `not_scored`.
- Missing evaluator-specific filenames, exports or final-template UI IDs are not missing-feature assertions. Inspect the actual candidate surface and bind its production architecture; additional unbound controls make the result unavailable rather than a base-like failure. Audit extreme agent scores even when randomized base/final controls pass.
- Keep UI binding eligibility separate from canonical semantics. Cosmetic placeholder text must not silently become a gold-only requirement. Bind a standard editor's native selection/long-press capability to its actual semantic control and owner; retain visibility, type, duplicate-control and unknown-action checks. A binding repair must not force-click hidden controls or erase evidence of a genuinely unreachable action.
- Never fill an absent observed field from `expected`, or mark every invariant true after a general expected-state comparison. Bind each invariant to its actual before/after state or effect/completion evidence. Missing evidence remains unscored, including when all visible expected fields match.
- Capture the production instance owned by the real entry path. A fresh presenter/store created by the test is domain-only evidence, even if the app imports the same class. Keep test doubles at the declared SDK/service boundary and observe actual boundary invocations; product-owned counters alone do not prove an external effect.
- Diff the immutable base/final application-owned SDK adapters before choosing doubles. If the task adds or changes a bridge, request mapping, callback routing, persistence cleanup or codec-preset dispatch, the affected case must execute that production body. An interface fake that supplies its result can hide a TODO or missing implementation while producing perfect polarity. Bind the original receiver/call path, SDK leaf arguments and held response to actual page state. Unchanged peripheral interfaces may still be doubled; live servers are not required merely to execute a changed application wrapper.
- Keep a changed-body coverage ledger: immutable path/symbol, affected case IDs, compiled source hash and actual runtime call/response evidence, or an explicit unscored gap. A compiled class alone does not establish invocation. A separate mapper test does not prove that the original page consumes the real bridge result, though its narrower mapping evidence remains valid.
- Audit runtime instrumentation as well as compiled bytes. Prototype replacement, method interception or reflection can bypass a changed production body while every source hash remains unchanged. Transparent observers must call the original receiver/body and preserve its return or exception; only declared external leaves may supply controlled results. Do not accept an observer's own `passThrough` flag as proof of this property.
- Workspace-only model exploration requires public dependency APIs to be discoverable inside the candidate. During preflight expose exact declared dependency/version metadata and a candidate-local public API reference or resolved SDK symbols when the source tree lacks them. Use only public dependency information, never final implementations, hidden assertions or evaluator selectors. Retain its content hash and keep it identical across comparable runs; inaccessible external caches must not silently become an information prerequisite.
- Identify whether runtime evidence uses an approved staged contract or the active shared contract. Promote audited contracts, bindings and aggregate metadata together after matching calibration; do not relabel staged reports with active digests. Withdraw invalid scores in current manifests and publication gates while retaining original evidence and independent generation/compile results.
- Recovery fixtures must preserve production lifecycle and resource ownership. A retained composition after real dismissal, or an opaque media object after production cleanup, cannot prove a reachable retry. Observe the actual surviving file/resource and relevant screen lifecycle, or leave that recovery case unscored.

## Result Format

Normalize each evaluated target to:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "platform": "android",
  "role": "agent",
  "observationMode": "runtime_state_transition",
  "runtime": "production_runtime_identifier",
  "codeGeneration": {"passed": true, "changedProductionFiles": ["..."]},
  "compile": {"passed": true, "command": "./gradlew ..."},
  "semantic": {
    "cases": [
      {
        "caseId": "ll_start_success", "traceDigest": "...", "status": "pass",
        "productionSources": [{"path": "...", "sha256": "..."}],
        "checkpoints": [{"label": "before", "state": {}}, {"label": "after", "state": {}}],
        "observed": {},
        "invariantChecks": []
      }
    ]
  },
  "diagnostics": {"adapter": "ready", "transport": "ready"}
}
```

Statuses are `pass`, `fail`, or `not_scored`. Diagnostics explain missing observations but are not benchmark metrics.
The empty state, observed and invariant containers above are schema placeholders:
real reports must include the actual before/after values and complete canonical
expectations and invariants. They cannot receive pass/fail without that evidence.
Use `compile.passed: null` for an unattempted application build; a successful
test-slice compilation is a separate `runtimeCompile` diagnostic.
Environment, transport, and `runtimeCompile` failures make affected semantic rows
`not_scored` and the report unpublishable. They must not overwrite the standalone
candidate application's `compile` result or be counted as semantic failures.

Before enabling a formal candidate scorer, execute random-directory copies of
both base and final using the same `agent` role. Require `0/N` and `N/N` with
no unscored rows through the public validator. These controls are evaluator
sanity checks, not model performance or evidence that a new model candidate
binds successfully.

Also execute the real default candidate-only entrypoint end to end, including
standalone compilation, public report admission and post-cleanup verification.
A role-specific control factory or mocked orchestration test does not exercise
every candidate-only branch. Validate artifact-record schemas at their consumers:
hash-check a recorded artifact before loading its path, rather than assuming the
record itself is a path. A successful final-copy default smoke is still a control,
not a model score or proof that a different candidate UI is bound.
