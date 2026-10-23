# Android focused runtime test design

Each role compiles the exact bytes listed in its `IMMUTABLE_SOURCES.json`. Those
files retain their upstream package declarations and method bodies; the manifest
records the immutable commit, Git blob ID, SHA-256, and byte count. The final
probe invokes `MediaKeyboardViewModel`, `GifPageViewModel`,
`StickerPageViewModel`, and `ChatStickerConfirmationController` directly. The
base probe invokes the real `MediaKeyboardController.show` action prefix from
the old tag and observes that the new transition contract is absent.

`evaluator/{base,final}` is evaluator-owned orchestration kept outside both
candidate-visible build roots. `stubs` contains only compiler,
Android/Compose/lifecycle, resource, logging, and repository service leaves. It
does not replace an application state transition. The JavaScript scorer compares
runtime before/after state and observed effects with the canonical contract; it
does not inspect source to decide a case.

The exact slice is packaged in a minimal evaluator-owned Android application and
was installed and executed on the API37 `emulator-5554`. The app runtime observer
recorded per-case before/after checkpoints, effects, invariants, invoked upstream
methods, and production source hashes. Native calibration is base 0/10 and final
10/10. This focused harness exercises production methods rather than claiming
pixel-level Compose, IME, or independent Android OS-persistence coverage.
