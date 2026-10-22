# Task17 Final Empty-Success Slice

Independent case `pm_state_003_empty_success` only. The archived v6 execution
passed in 43.964 seconds using real Compose UI / Robolectric API36 native Skia.
This is not an emulator, complete app build, Node navigation test, or Matrix
server integration. `compile.passed` remains null; `runtimeCompile` passed.
Primary reports and shared runners/mergers are unchanged.

## Evidence and Identity

- Report: `experiment_results/runtime_transition_20261019/android17_followup/empty-ui/final-v6.json`
- Report SHA256: `6e439b59370978f7dcbbcac2771931ab2b2578fd13948b6f5ebbf91e0f575867`
- Candidate commit: `eff868ddf9e1caef8182e55ac59054e81526a68f`
- Candidate tree: `0cd8a58632515f8e0f6fb669b02c8b35614d9181`
- Contract SHA256: `351bacebd24bd1c95707bfea9e5caa8d4813a087f88606a3571d8c73d168fd93`
- Case trace digest: `0848f056c3d15e7e25ad5d4038e3118286bc6e232124202d066b12027429fd96`

The report contains hashes for 390 immutable production source/resource/catalog
records, evaluator sources, configuration, JVM log, dependencies and two actual
411x891 screenshots. Its sibling log contains the matching `RUNTIME_RESULT`.
The normalized independent `final-v6.validated.json` is 1P/0F/8NS. It does not
replace the existing primary case002 PASS. A reviewed merge would produce
2P/0F/7NS for final; this task does not perform that merge.

## Actual Path and Boundaries

1. The original `PinnedEventsTimelineProvider` calls the controlled MatrixRoom
   SDK interface. The suspend completion is held. The original presenter yields
   Loading and the original View renders a real progress semantics node.
2. Given `pinnedTimelineItems=[]` comes from the SDK Timeline interface's empty
   flow. The production factory has not emitted anything at the given checkpoint.
3. Completing that same pending SDK call with `Result.success(timeline)` is the
   canonical `timeline_load_completed` event. The fixture correctly boxes the
   nested Kotlin coroutine result; it does not set production state.
4. The original provider produces Success. The original presenter collects and
   debounces the SDK flow and invokes original `TimelineItemsFactory.replaceWith`.
   Real diff cache, grouper and indexer execute and the real factory emits `[]`.
5. The same original presenter yields Empty. The same original View renders its
   empty-state headline; progress and failure UI are absent. The full expected
   object is observed: `listState=empty`, `loadedPinnedMessagesCount=0`,
   `failureVisible=false`. The successful-empty invariant is asserted from the
   actual provider/factory/presenter chain, not assumed from SDK input.

MatrixRoom and Timeline are controlled external SDK interfaces, not live Matrix
services. Feature flags, connectivity, permissions and dispatchers are controlled
environment inputs. Dispatchers use the actual Android main looper. The
canonical case has no route-entry/navigation/persistence requirement.

## Stub Audit

No legacy task17 `UnexercisedFactory`, `Actions`, model or UI stubs are compiled.
Original concrete factory constructors are called recursively; 17 constructor
class names are recorded and matched to immutable production files. Event and
virtual-item factories are real but their conversion methods are not exercised
because this case is empty. The factory's grouping/indexing/emit path is real.

The assisted `ActionListPresenter.Factory` fixture only wires the actual
`DefaultActionListPresenter` constructor. It does not substitute action behavior;
`present()` is not reached in the Empty branch. Navigator, preferences and unused
factory interface dependencies throw if invoked. Before/after traces contain
only the reviewed SDK/feature-flag calls and no unexpected invocations.

Compile-only shims are Anvil annotation metadata (`Annotations.kt`, common
`Anvil.kt`) and generated location resource defaults copied from the immutable
location Gradle configuration. They do not implement runtime business logic;
location/map code is not executed. Common `Harness.kt` supplies observation/JUnit
transport; its `NoNodes`/`CompositionDriver` are not used by this fixture. The
actual Compose UI test rule hosts the original View.

## Reproduce and Verify

Run from the repository root with a NEW evidence output filename:

```sh
python3 state_tests/runtime/android/17_pinned_messages/empty_ui/run.py \
  --output experiment_results/runtime_transition_20261019/android17_followup/empty-ui/new-run.json \
  --timeout 180
python3 -m unittest discover \
  -s state_tests/runtime/android/17_pinned_messages/empty_ui -p test_verify.py -v
python3 state_tests/runtime/android/17_pinned_messages/empty_ui/verify.py \
  --output experiment_results/runtime_transition_20261019/android17_followup/empty-ui/new-validation.json
```

The verifier intentionally accepts only the hash-pinned archived v6 report, not
arbitrary future reruns. New runs need independent review. All 18 verifier tests
passed, including changed given/event, incomplete observations, unknown versus
false, wrong source/digest, reused case/frame, changed receiver, missing factory
emission, legacy stub inclusion and executed non-SDK interfaces.

Dependencies reuse local caches. Four missing small official Compose metadata
JARs are stored in this fixture's `.dependencies` (about 16 KiB on disk) and
hash-recorded. Original Material API versions are retained without source edits.
The test-slice compiler is Kotlin2.2.10 with Compose UI1.8.3 and Robolectric4.16.1;
this is not a claim that the original Gradle application builds on that toolchain.
Temporary compilation directories are removed by the shared runner; no build
process remains after completion.

## Remaining Gaps

Case001 requires original parent/Node navigation. Cases004-006 require populated
real factory/render/action paths. Case007 requires actual navigation and focus,
not callback interception. Cases008-009 require original unpin UI/event plus
adequate success/failure and recovery boundary evidence. None is inferred from
this empty-list result. Earlier v1-v5 attempts are harness/dependency diagnostics,
not semantic failures; v5 established Loading but its coroutine Result boxing
error prevented the production completion path.
