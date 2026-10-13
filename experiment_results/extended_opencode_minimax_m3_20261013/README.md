# Extended Element X benchmark, 2026-10-13

This bundle records two tasks extracted with `explore-skill`, calibrated on Android with `testgen-skill`, and migrated to ArkTS with `migration-skill`:

- `06_multi_select_polls`: Android `v26.08.4 -> v26.09.1`, 9 canonical transitions.
- `07_recent_search_history`: Android `v26.09.2 -> v26.09.3`, 11 canonical transitions.

The same case IDs, normalized transitions, and digests are used on Android and ArkTS. Both platforms calibrate base `0/20` and ground-truth final `20/20`.

## MiniMax-M3 result

| Platform | Code generation | Compile | Semantic testcase |
| --- | ---: | ---: | ---: |
| Android | 2/2 | 2/2 | 20/20 |
| ArkTS | 2/2 | 2/2 | 18/20 |
| Total | 4/4 | 4/4 | 38/40 |

The two ArkTS failures are substantive: the candidate wires an in-memory store instead of its file-backed implementation, and selecting a query history entry switches to messages instead of rooms.

## Quality decision

The artifacts meet release/Git traceability, transition parity, polarity, build, and production-wiring gates. They contain 10 cases per task versus 7.4 per task in the original five. Android agent discrimination is weaker because both new Android candidates pass all cases; this is recorded as a caveat, while the cross-platform result remains discriminative.

Only code generation, compile, and semantic testcase outcomes are benchmark metrics. Provider, isolation, adapter, JDK, and disk events are retained in `diagnostics.json`.
