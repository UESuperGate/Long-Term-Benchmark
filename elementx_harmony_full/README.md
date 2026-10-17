# Element X Harmony Full Reconstruction

This project is the production-baseline reconstruction used to rebuild the
ArkTS side of the multi-platform long-horizon benchmark. It starts from the
Android `v26.04.0` product graph and advances through reproducible release
checkpoints. The older `elementx_harmony_client` remains a UI prototype and is
not accepted as proof of full-client parity.

## Source checkpoint

- Android repository: `element-hq/element-x-android`
- Initial tag: `v26.04.0`
- Initial commit: `8019e235d4`
- OpenHarmony SDK: 23

## Acceptance gates

The reconstruction is complete only when all of these gates pass:

1. Every Android production Gradle module is represented in the generated
   migration manifest as `ported`, `native_bridge`, `platform_equivalent`, or
   justified `not_applicable`; `unmapped` is forbidden.
2. Every mapping has existing target-file and target-symbol evidence.
3. Production ArkTS sources do not import fixture or mock implementations.
4. The Matrix native bridge is built against a pinned Matrix Rust SDK revision
   and passes ABI/contract tests. An unavailable bridge is not parity.
5. The SDK 23 HAP builds and launches, and the common Android/Harmony semantic
   transition suites pass on both platforms.
6. Each benchmark checkpoint preserves existing regression behavior while its
   target base/final polarity is all-fail/all-pass.

`verification/full-client-capabilities.json` and
`verification/migration-map.json` are evidence inputs, not completion claims.
The strict audit must remain failing while any production capability is
missing or partial.

## Build

```sh
export OHOS_BASE_SDK_HOME="$HOME/Library/OpenHarmony/Sdk"
export JAVA_HOME="/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home"
export PATH="/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin:/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin:/Applications/DevEco-Studio.app/Contents/tools/node/bin:$PATH"
ohpm install
hvigorw assembleHap --no-daemon
```

The production build must not enable fixture-backed fallback paths.

The current production bridge restores authenticated Matrix SDK sessions,
performs room sync, loads backward room history, and sends text messages with
server event acknowledgement. Rich-message sending, live timeline updates,
end-to-end encryption, receipts, media transport, and the remaining Android
module surface are still explicit parity gaps.

## Reproducible checks

Run the complete local build and evidence refresh without claiming parity while
the reconstruction is still incomplete:

```sh
python3 scripts/run_full_reconstruction_checks.py
```

Release and benchmark checkpoint creation must use the strict gate:

```sh
python3 scripts/run_full_reconstruction_checks.py --strict
```

The check runner builds both the production HAP and the `ohosTest` HAP. A test
HAP compile proves ArkTS test discovery and compilation only; semantic testcases
are counted as executed only after Hypium runs them on an online signed device.

Preview and execute bounded cleanup after preserving reports and final HAPs:

```bash
python3 scripts/cleanup_reconstruction_intermediates.py
python3 scripts/cleanup_reconstruction_intermediates.py --execute
```

Use `--deep` only when the Matrix Rust archive may be rebuilt on the next run.

The non-strict command exits successfully only when the inventory, harness
tests, native bridge build, and HAP build are reproducible. Its report still
records `parity_status=FAIL` until every production module is mapped, fixtures
are removed from the production dependency graph, the real Matrix runtime is
linked, and Android/ArkTS semantic tests are all-pass. The strict command also
fails on any of those parity gaps.
