# Android-To-ArkTS Migration Contract

The migration bundle must contain:

```text
migrations/<task-id>/
  manifest.json
  android/task.json
  canonical/transitions.json
  arkts/base/
  arkts/final/
  arkts/bindings.json
  results/android-base.json
  results/android-final.json
  results/android-agent.json
  results/arkts-base.json
  results/arkts-final.json
  results/arkts-agent.json
  provenance/eval-manifest.json
  provenance/calibration-summary.json
  provenance/rescore-summary.json
  provenance/patches/android-agent.patch
  provenance/patches/arkts-agent.patch
  provenance/evidence-index.json
```

`manifest.json` records exact source refs and toolchain versions. It also records which Android modules map to which ArkTS modules and identifies intentionally unsupported platform-specific behavior.

`arkts/bindings.json` maps canonical cases to ArkTS mechanics:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "canonicalContract": "../canonical/transitions.json",
  "cases": [
    {
      "caseId": "ll_start_success",
      "traceDigest": "...",
      "fixture": "LiveLocationFixture.activeRoom",
      "eventEntrypoint": "startLiveLocation(roomId)",
      "observations": ["store.expiry", "coordinator.running", "banner.visible"]
    }
  ]
}
```

Bindings may change framework-specific setup, event dispatch, and observation paths. They must not change `given`, `event`, `expected`, invariants, case grouping, or digest.

When a reviewed correction changes canonical semantics, promote `canonical/transitions.json` and `arkts/bindings.json` as one audited revision. Preserve before/after files and hashes, require every active binding row to reference the promoted case identity and digest, and reject a state where only one active file matches the audited after-version.

## Four-Way Calibration

For `N` canonical cases:

| Platform | Role | Required semantic result |
| --- | --- | --- |
| Android | base | `0/N` pass, `N/N` fail |
| Android | ground-truth final | `N/N` pass |
| ArkTS | base | `0/N` pass, `N/N` fail |
| ArkTS | ground-truth final | `N/N` pass |

Every row must be scored. A compile or adapter failure is a calibration defect until repaired.

Calibration requires `observationMode: runtime_state_transition`, execution of
the candidate's actual production methods, source hashes, before/after state,
and observed expectations and invariants. A source-observer result with perfect
polarity is still not runtime calibration. JVM or ArkVM domain execution does
not establish native UI interaction or OS persistence. Do not bypass a disabled
UI control by injecting an otherwise unreachable presenter event and call that
a user-facing semantic failure; observe the actual event boundary.

After a genuine missing-entry assertion, do not project final-only state into
guessed base values or mark later invariants false. A reviewed common-start
prefix may fail early with source-bound UI/flow evidence and an independent
positive control, while leaving canonical post-state and later invariants
explicitly unobserved. Recheck this boundary separately on both platforms;
executing a real page does not make invented post-state valid.

Never backfill a missing runtime field from the canonical expectation or assign
all invariants a constant pass value. Each invariant needs its own actual state
or ordered-effect evidence; an expected-state match does not prove a different
invariant about preservation, asynchronous completion or omitted side effects.

Observe the actual page-owned presenter/store and its SDK callbacks. Creating a
separate instance of the same production class is only a domain diagnostic, not
proof of app wiring. Controlled SDK/service test doubles are valid at the declared
external boundary, but product-owned counters or user buttons that imitate remote
completion are not evidence that the external operation occurred.

Before freezing a test-double boundary, compare it with the immutable Android
feature delta and mapped ArkTS production bodies. A new application-owned SDK
wrapper, identity/request mapper, authentication branch or persistence cleanup
must execute through the actual page's call path; faking its application
interface bypasses the task even when UI polarity is perfect. Fake external SDK
leaves instead and bind actual arguments, held completion, callbacks and effects.
Record changed-body path/symbol, compiled bytes and runtime invocation per affected
case. Preserve valid narrower UI/mapper observations without promoting them to
complete calibration. This does not require live Matrix servers or forbid
unchanged peripheral interfaces from being doubled.

For isolated model tasks, expose the exact public dependency metadata and
necessary SDK API references inside each candidate before timing. Bind their
hashes; do not rely on model exploration of forbidden external dependency caches
or expose final/evaluator source. Match information availability across platforms
without fabricating equivalent private APIs.

Establish derived given-state through the original input/event sequence. Assigning
a current handle, async success flag or screen field in the test bypasses the
transition being validated. A mounted page next to a separate test-created
presenter does not repair this gap. Keep domain diagnostics separate, and withdraw
incomplete positive calibration before scheduling the next model experiment.

A candidate need not retain final-template filenames or UI IDs. Existing
controls under a different production architecture require executable bindings;
absence of a private selector is not proof of missing functionality. Keep an
unbound candidate unscored and withdraw any earlier misleading score from the
current manifest without changing its patch or successful application build.
Likewise, do not reject a source-bound standard text editor solely because its
placeholder differs from the reference implementation. Preserve real UI ownership,
event eligibility and unknown-action checks while binding the candidate's surface.
In particular, a common-entry absence proof needs a complete observed UI boundary:
additional or renamed unbound interactive controls make that proof unavailable.
Selecting a fixture by a familiar filename must not decide the semantic verdict.

On native ArkVM, importing an entry-HAP production module before its original
ability loads can abort the process with HSP resolution errors. Preserve the
actual lifecycle: load the original app, drain prior asynchronous setup work,
install only external inputs, then re-enter the unchanged production page.
Record that setup order; do not repair it by substituting a host-transpiled
copy or by modifying the production page.

Validate the formal scorer with random-directory base and final copies under
the identical `agent` role, not only role-specific calibration or a final-copy
success. These are evaluator controls and must not be reported as model scores.

Agent reports are interpreted only after calibration. Base plus each published binary-safe patch must reconstruct the scored candidate, including untracked production files. The evidence index records SHA-256 and byte length for retained patches and local logs; provider or transport failures remain unavailable and outside benchmark denominators.

Distinguish technical review from user authorization in every audit. A coordinator
review or later parser check must not be recorded as human approval or relabel an
original frozen isolation result. Preserve the earlier finding and use a separately
versioned, accurately attributed addendum.

Retain original native results and execution/build/log bytes before temporary
cleanup. Normalized snapshots alone do not bind every status and invariant to
what ran. Verify that retained-path mappings preserve original hashes and that
the independent verifier still works after temporary inputs are removed. Large
JSON may be losslessly compressed with a verified restoration manifest; do not
discard semantic raw data under the hash-only binary-cleanup policy.

Freeze and archive the actual clean-room ArkTS baseline before the model starts,
including public inputs and commit/tree hashes. A later migrated base may differ;
patch reconstruction against that later tree cannot independently prove unread,
unchanged original inputs. Retain the small compressed source snapshot when
removing temporary candidate checkouts.

When a semantic row is assembled from multiple runtime probes, the binding must map its canonical `key` to exactly one declared combination of probes. Required rows are conjunctive and mutually exclusive by key: duplicates, missing members, unknown keys, or overlapping ownership are adapter failures, not opportunities to select the most favorable pole. Environment, device transport, and evaluator `runtimeCompile` failures produce `not_scored`; they do not change the separately recorded standalone application compile result.

A shared contract correction may also change the public task inputs. Audit both platforms' archived prompts and completed reads before calling a replay a revised model result. If the agents received a different public given, keep that replay as evaluator diagnostics and require fresh isolated one-shot runs with the corrected common inputs after calibration. Do not tune or repair the archived patches using testcase feedback.

## Completeness Review

Before calling an ArkTS project a migrated base or final, verify navigation reachability, state/effect implementation, SDK or service boundaries, persistence, errors and cancellation, real UI rendering, resources, and unrelated workflows needed to exercise the feature. Passing a small semantic subset is necessary but not sufficient evidence of complete migration.

Preserve existing sibling workflows on the same task surface. For example, adding
an address-join action to an existing start-chat menu must not turn its shared
base into a Back-only screen by removing direct-chat or room-creation routes.
Keeping their source files as unreachable code does not preserve that behavior.
A minimal staged overlay may expose this gap, but cannot be promoted as a faithful
base/final migration until the required common paths are actually wired.
