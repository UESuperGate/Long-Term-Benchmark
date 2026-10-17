# Element X Harmony Full-Client Reconstruction

## Objective

Reconstruct the Element X Android product as a production-capable OpenHarmony
SDK 23 application. The result is the frozen ArkTS baseline used to derive the
five multi-platform long-horizon benchmark tasks. It must not be a task-specific
demo, a fixture-backed shell, or a collection of symbol-name placeholders.

## Source of truth

- Android repository: `element-hq/element-x-android`
- Initial complete checkpoint: `v26.04.0` (`8019e235d4`)
- Release checkpoints to preserve: `v26.05.0`, `v26.05.1`, `v26.06.1`,
  `v26.07.0`, `v26.07.1`, `v26.08.0`, `v26.08.1`, `v26.08.2`, `v26.08.4`
- OpenHarmony compile, compatible, minimum, and target API: 23

## Architecture requirements

1. Preserve feature, library, and service ownership boundaries from Android.
   Platform-specific implementations may differ, but unrelated domains must not
   be collapsed into one page or one mutable service.
2. Reuse the pinned Matrix Rust SDK through a typed C ABI and N-API bridge where
   the Android application delegates sync, timeline, encryption, verification,
   media, room-list, and session behavior to the SDK.
3. Implement OpenHarmony equivalents for navigation, lifecycle, permissions,
   secure storage, notifications, media, background work, and platform intents.
4. Keep mocks and deterministic fixtures in test-only source sets. Production
   ArkTS must not import or instantiate fixture or mock adapters.
5. Expose stable state-observation adapters for the evaluator without placing
   expected testcase answers in production code.

## Required product behavior

The reconstructed client must cover the Android product paths at the selected
checkpoint, including signed-out onboarding, authentication and session restore;
room list and room navigation; timeline rendering and pagination; sending and
editing messages; reactions, replies and rich events; encrypted rooms and media;
session verification, recovery and device management; profiles and preferences;
media viewing and sharing; calls and live location; push notifications and deep
links; moderation, room details, room creation, search, spaces, and logout.

The five benchmark feature families must be implemented through the same
production services and state holders as the rest of the client:

- user status
- gallery messages
- timeline protection and active-call rich events
- live location
- link new device

## Migration evidence

`scripts/generate_full_migration_inventory.py` enumerates every production
Android Gradle module from the source tag. Each module must have one entry in
`elementx_harmony_full/verification/migration-map.json` with one of these final
dispositions:

- `ported`: implemented as production ArkTS/OpenHarmony code
- `native_bridge`: implemented by the pinned native Matrix runtime
- `platform_equivalent`: replaced by a tested OpenHarmony platform service
- `not_applicable`: impossible or irrelevant on OpenHarmony, with a reviewed
  reason and regression evidence

`unmapped`, `planned`, and `partial` are progress states and fail acceptance.
Every final mapping must reference existing target files, concrete symbols, and
tests. File names or declaration-only contracts are not implementation evidence.

## Acceptance gates

1. OpenHarmony SDK 23 type-check and HAP build pass from a clean checkout.
2. Native bridge host tests and `aarch64-unknown-linux-ohos` build pass against
   the pinned Matrix Rust SDK revision.
3. The strict reconstruction audit reports no unmapped or partial modules, no
   missing evidence, no production fixtures, and no unavailable native runtime.
4. Android and Harmony pass the same core journey and state-transition suites.
5. For each benchmark task, the full base fails all target-feature cases, the
   trusted full final passes all cases, and unrelated regression cases continue
   to pass.
6. Device tests cover cold start, process restart, offline recovery, background
   and foreground transitions, runtime permission changes, and deep links.

## Benchmark derivation

Benchmark candidates are copied from the complete Harmony checkpoint matching
the Android base tag. A trusted final is the complete base plus the transitive
closure of the selected upstream feature change. The migration itself is
benchmark infrastructure and is never included in an evaluated agent's score or
wall-clock time.
