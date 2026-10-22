# Task17 Android evaluator SDK classpath repair

The retained v7 compile probe
`experiment_results/runtime_transition_20261022/task17_android_compile_final_v7_v3`
reached `:app:compileGplayDebugUnitTestKotlin` and failed because evaluator-owned
sources directly import `org.matrix.rustcomponents.sdk` while the app test
source set did not expose that dependency. The fixed Android commit uses
`org.matrix.rustcomponents:sdk-android:0.2.42` through the `matrix_sdk`
version-catalog entry and `libraries:matrix:impl` declares it as
`debugImplementation`, so it is not transitively available to direct app test
imports.

The repair adds the same catalog artifact to evaluator-only
`testImplementation`. It does not add or replace an SDK interface, alter
production source, change the canonical transition contract, relax an
assertion, or modify any agent patch.

Exact fixture pin before repair:

- bytes: `5941`
- SHA-256: `428f7631692d40e34c80251c1f486340e77e1adc2b3b7c5c75912ea8d2d7e107`

Exact fixture pin after repair:

- bytes: `6037`
- SHA-256: `e914687fd23aaa90053d70c51a9da50d7ee5075ac03679f2e8a631198238b016`

The old compile log and v9 fail-closed cleanup receipt remain retained. That
run is environment/scaffold evidence and is not a benchmark compile or
semantic failure.

The exact-media policy SHA changed only because of that fixture pin:

- before: `a5da41a10d3a868ce4b6ef322f8c4f76f608a6c8b1661a8a46e23092f9ddc55a`
- after: `d0eb5dc508ce322538e11678cfa754c932a30c480e197429c79564521f733ba9`

To avoid nine independent full-project checkouts and compiles, the same
episode body is also exposed through nine distinct JUnit test methods. JUnit
creates a fresh test instance and Compose rule for each method. The runner's
`--case all` filter selects only those methods; the original one-case method is
retained for focused reproduction. The transition implementation and
assertions are unchanged.

- `Task17ConnectedFlowTest.kt` before: `27216` bytes,
  `0fe0cf5860241cdba13eb69bcfa6bd4bb11977a590204a506a4bb5075ee39b6c`
- `Task17ConnectedFlowTest.kt` after: `28299` bytes,
  `44f33db564a3e0ec11ae91170605ad66270f1113cc780914b1f7eea80a0c795b`

After the independently pinned JUnit batching update, the final exact-media
policy SHA is
`ec21e5f8ec0994787de692cfe46661fceff0367682b439d7b0d8d2d5271e9a53`.

## Robolectric AndroidKeyStore follow-up

The first nine-case runtime attempt compiled but all cases stopped before any
action or SDK call. Each raw file records the same
`java.security.KeyStoreException: AndroidKeyStore not found` while Dagger lazily
constructed the encrypted `DatabaseSessionStore`. This is a JVM environment
boundary, not a Task17 observation.

The evaluator now injects Element X's version-matched production
`:libraries:session-storage:impl-memory` `InMemorySessionStore` into the original
`RustMatrixClient` constructor. The full production Dagger node graph,
presenters, Matrix bridge, `RustMatrixRoom` and `RustTimeline` remain unchanged;
only `org.matrix.rustcomponents.sdk` leaf objects are mocked. Raw component
evidence records the selected store class, source module, reason and identity.
The failed pre-action evidence remains at
`experiment_results/runtime_transition_20261022/task17_android_final_all_v7_v1`.

Versioned fixture pins after this repair:

- `Task17ProductionBindings.kt`: `8688` bytes,
  `e2be76a9a621bf1893076decba12eafeab55be08d0bc70d78d03410665256d7b`
- `connected-init.gradle`: `6151` bytes,
  `e9aa2c40134faca97a6e8a22aa410e6b0c702163ac6a5279a33bc2fceb9dec20`
- `README.md`: `6554` bytes,
  `867763a0176b99ac008a8565133148e9fa781f9f43585c3fd3c706dd9559618a`
- exact-media policy:
  `e631ff390107bf270d0571ef8c2fef20425b6ab23fc2f3aaeee70cb0755261fc`

## Host JNA/Matrix FFI follow-up

The next nine-case attempt passed compilation and the session-store boundary,
then all cases stopped while the original `RustRoomFactory` called
`TimelineEventTypeFilter.exclude`. Android Gradle exposes JNA classes but strips
the macOS dispatcher from the transformed AAR; even with that dispatcher, the
Android Matrix SDK artifact has no macOS Matrix SDK dynamic library. No case
produced a frame or action, so the retained v2 result remains environment
evidence rather than semantic failure.

The evaluator now controls this exact `org.matrix.rustcomponents.sdk` static
factory call at the already declared leaf boundary. It records the real call
and argument count, returns a strict audited `TimelineEventTypeFilter` SDK
object, and always removes the object mock during cleanup. The original
`RustRoomFactory`, `RustMatrixRoom`, timelines, nodes, presenters and canonical
assertions remain unchanged. No host Rust build or application implementation
is substituted.

Versioned pins after the SDK-leaf repair:

- `Task17SdkInputs.kt`: `9300` bytes,
  `aef62b58f5d3951194ee38feebb2b21798a1352efd7e14894bda024e5290bf71`
- `README.md`: `6985` bytes,
  `dd6968539e15f85479fa07de61a007dc4b7da0be699fc745d987cc4cd59d3ce2`
- exact-media policy:
  `3677ce4b3f7d0e67f73d63f3a161d87242dae2a90b1c3e1ca002f0aa02bf4553`

## Generated SessionStore provider follow-up

The focused case001 probe then reached the SDK leaf and constructed the real
`RustMatrixClient` plus `SessionComponent`, but resolving the production
`AnalyticsService` followed its `SessionObserver` back to Dagger's separate
encrypted store provider. The evaluator now seeds the same Element X
`InMemorySessionStore` into the unique generated `Provider<SessionStore>`
singleton before any dependent provider is resolved. It requires the reviewed
`dagger.internal.DoubleCheck` wrapper and verifies provider readback identity.
Production analytics, node factories, presenters and Task17 behavior are not
replaced; the component evidence records the exact generated field and object.

The first focused readback showed that generated field is declared as
`Provider<DatabaseSessionStore>`, not the interface spelling. Matching therefore
uses `SessionStore.isAssignableFrom(declaredType)` while retaining the unique
match, reviewed wrapper and identity checks.

Final pins for this metadata correction:

- `Task17ProductionBindings.kt`: `10908` bytes,
  `5b05d05853ba7b0f06e55f215e0c4b4276a64009df6e08dd91ce97f0743268fe`
- `README.md`: `7424` bytes,
  `82f15e220d266543b74a80de9e601d1ea5124d3dc725537d2e4daa38df41fa74`
- exact-media policy:
  `5d0139b2a5e9562ba155570b0cf1abb5d6ed747f4b9790ffc9f3f4bedf20ae5d`

## Appyx outer-host mount follow-up

After the environment providers were fixed, case001 entered Compose but the
evaluator's outer Host rendered its initial backstack in the same frame that
Appyx was still attaching the corresponding child. Appyx correctly rejected
the out-of-sync request before any production page frame existed. The Host now
collects its own `children` flow and calls `BackstackView` only after attachment.
This condition applies only to the evaluator wrapper; every production node and
view remains mounted by its original Appyx code.

Versioned pins after the Host mount repair:

- `Task17ConnectedFlowTest.kt`: `28504` bytes,
  `b6ee94ab287b8dc38d8f6c4881f461e767aaa60b280a1788d4fba157373f477b`
- `README.md`: `7724` bytes,
  `bad09a82c660e8d63e305573ddd0e8add5b245aa147fb8fb8067e4badb318e48`
- exact-media policy:
  `e3d0bf0ff2fbc47ecbc0eddc19631f5c643d091a632432dea4aaeb94672df9dc`

Versioned pins after the generated-provider repair:

- `Task17ProductionBindings.kt`: `10892` bytes,
  `829fb40e06183c0991cea75989779ac532f4049ec2d611fef037dc1bf8a92633`
- `README.md`: `7387` bytes,
  `e2c5e1585fe44e80006743184c135ff996941ebd0ebf17426dadaa54846ea26d`
- exact-media policy:
  `94997c517f6f9db17f1bf5187c31621b344369a790e5469192c3d3c2daeac5ee`
