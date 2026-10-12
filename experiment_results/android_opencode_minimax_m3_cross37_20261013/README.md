# Android OpenCode + MiniMax-M3 Cross-Platform Evaluation

This is the corrected 2026-10-13 Android run. It replaces the invalid
candidate-owned 150/150 semantic result with evaluator-owned evidence over the
audited Android/ArkTS semantic intersection.

## Benchmark metrics

| Metric | Passed | Total | Rate |
| --- | ---: | ---: | ---: |
| Code generation | 5 | 5 | 100% |
| Compile | 5 | 5 | 100% |
| Semantic testcase | 24 | 37 | 64.86% |

| Task | Base | Ground-truth final | Agent result |
| --- | ---: | ---: | ---: |
| 01 User status | 0/9 | 9/9 | 5/9 |
| 02 Gallery messages | 0/6 | 6/6 | 6/6 |
| 03 Timeline protection / rich events | 0/9 | 9/9 | 7/9 |
| 04 Live location | 0/7 | 7/7 | 4/7 |
| 05 Link new device | 0/6 | 6/6 | 2/6 |
| **Total** | **0/37** | **37/37** | **24/37** |

The same 37 platform-neutral given/event/expected transitions are bound to both
Android and ArkTS. Both platforms calibrate to all-fail on base and all-pass on
ground-truth final.

Three link-new-device digit-confirmation rows were removed from the shared
contract because Android `v26.05.0` and `v26.08.2` contain identical production
behavior for those transitions. Their earlier base failures were class-level
compile fallout, not missing semantics.

## Semantic evidence

The formal Android score uses evaluator-owned production transition-conformance
rules. Each case requires task-local production Kotlin evidence for its state,
event/branch, and effect clauses, after the full app has compiled. Comments,
tests, candidate-owned oracle files, unrelated modules, and debug adapters are
excluded. Rules are calibrated against the official base and final tags.

The official final-tag JUnit observer remains a debug diagnostic. It reports
0/37 for this candidate because its tests compile against exact upstream class
and method shapes, while the agent used alternative APIs. That result is not
used as a benchmark metric.

## Environment and timing

- OpenCode: `2.0.20`
- Model: `minimax-token-plan/MiniMax-M3`
- Endpoint: `https://api.minimaxi.com/v1`
- Timeout: 3600 seconds per task
- Java: OpenJDK `21.0.12.1`
- Emulator: `37.2.12.0`, Android 17 / API 37 / `arm64-v8a`
- Compile/target SDK: 36 for tasks 2, 4, and 5; 37 for tasks 1 and 3
- Overall generation/build interval: 8,754.337 seconds (2:25:54.337)

Timing is one wall-clock interval from the first task start through the last
task's generation and build completion. Subagent time is not recorded
separately. No API key is stored in this result directory.

## Evidence files

- `benchmark_summary.json`: formal metrics, task breakdown, and timing.
- `environment.json`: toolchain and device versions.
- `semantic_report.json`: per-case Android agent/base/final evidence.
- `cross_platform_calibration.json`: Android and
  ArkTS polarity calibration.
- `official_api_diagnostic.json`:
  exact-upstream-API diagnostic only.
