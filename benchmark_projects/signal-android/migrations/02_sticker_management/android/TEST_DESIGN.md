# Android focused runtime test design

Each role compiles the exact official Java/Kotlin bytes listed in
`IMMUTABLE_SOURCES.json`, preserving upstream packages and method bodies. The
final probe directly invokes `StickerManagementViewModel` and
`StickerManagementRepository`; the base probe directly invokes the legacy
ViewModel/repository action prefix. This makes missing multi-select, drag-save,
and confirmation behavior score as real base failures instead of a fabricated
missing-feature model.

`evaluator/{base,final}` owns fixtures and observation only and is kept outside
both candidate-visible build roots. `stubs` controls Android, lifecycle,
database, JobManager, key-value, and JSON leaves. The exact upstream repository
body still performs reference writes, job creation, linked-device mapping,
uninstall fan-out, and order persistence before the leaves are observed. The
scorer uses runtime before/after state, ordered states/effects, and derived
invariants; it never uses a source observer or reimplements the expected oracle
in production code.

The exact slice is packaged in a minimal evaluator-owned Android application and
was installed and executed on the API37 `emulator-5554`. Its app runtime observer
recorded per-case before/after checkpoints, effects, invariants, invoked upstream
methods, and production source hashes. Native calibration is base 0/10 and final
10/10. This focused harness exercises production methods rather than claiming
pixel-level Compose gesture/dialog or independent Android OS-persistence coverage.
