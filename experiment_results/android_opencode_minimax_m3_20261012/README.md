# Android OpenCode + MiniMax-M3 Evaluation

> **Validity correction (2026-10-12):** the previously published `150/150`
> semantic result is invalid because all five candidates modified or introduced
> candidate-owned oracle code. Code generation and compile results remain raw
> run measurements. See `semantic_validity_correction.json` for the audit.

This directory preserves the completed 2026-10-12 Android Element X run of the
multi-platform long-horizon benchmark. Android uses the official Element X
Android release tags and the same 150 public state-transition testcases and
evaluator-owned semantic oracles as ArkTS.

## Benchmark Metrics

Only these three values are benchmark metrics. Adapter, transport, timeout, and
compiler details are diagnostics.

| Metric | Passed | Total | Rate |
| --- | ---: | ---: | ---: |
| Code generation | 5 | 5 | 100% |
| Compile | 5 | 5 | 100% |
| Semantic testcase | N/A | 0 scored / 150 expected | N/A |

| Task | Cases | Base | Ground-truth final | Agent result |
| --- | ---: | ---: | ---: | ---: |
| 01 User status | 26 | 0/26 | 26/26 | not scored |
| 02 Gallery messages | 28 | 0/28 | 28/28 | not scored |
| 03 Timeline protection / rich events | 32 | 0/32 | 32/32 | not scored |
| 04 Live location | 30 | 0/30 | 30/30 | not scored |
| 05 Link new device | 34 | 0/34 | 34/34 | not scored |
| **Total** | **150** | **0/150** | **150/150** | **not scored** |

The historical runner reported 150 matches, but those rows were produced through
candidate-owned semantic adapters and are retained only as debugging evidence.
They are not benchmark semantic passes. Base/final calibration proves scorer
polarity only; it does not prove product-level behavior.

## Timing

The recorded duration is the single wall-clock interval from the beginning of
the first Android task through the completed 150-case cross-task verification:
15,756 seconds (4 hours, 22 minutes, 36 seconds). Subagent timings are not
recorded separately.

## Environment

- OpenCode: v2.0.20
- Model: `minimax-token-plan/MiniMax-M3`
- Endpoint: `https://api.minimaxi.com/v1`
- Agent/build timeout: 3600 seconds per task
- Java: OpenJDK 21.0.12.1
- Emulator: 37.2.12.0
- AVD: Android 17 / API 37 / `arm64-v8a`
- Older base tags: compile/target SDK 36, Gradle 9.2.1, AGP 8.13.2
- Newer base tags: compile/target SDK 37, Gradle 9.5.1, AGP 9.2.1

The API key remained in a local OpenCode secret file and is not stored here.

## Workflow

1. Create an isolated candidate from each official Android base tag.
2. Expose the public requirement and full YAML state oracle to the candidate.
3. Run OpenCode inside the candidate with project-local reads/edits, optional
   subagents, no web access, and a 3600-second task budget.
4. Build an arm64 `gplayDebug` APK independently with the release's own Android
   toolchain and a local Maven mirror.
5. Install each APK on the API 37 emulator, query initial and transition phases,
   and score strict semantic facts against the shared oracle.
6. Feed failed semantic phases back to the same model and repeat until the
   candidate-owned adapter satisfies all 150 public cases. This historical step
   is the reason the semantic result is now invalidated.

## Artifacts

- `benchmark_summary.json` / `.md`: the three formal benchmark metrics.
- `run_summary.json`: calibration, totals, and per-task results.
- `agent_strict_report.json` / `.md`: final combined 150-case evidence.
- `agent_target_matrix.json` / `.md`: generated multi-role target matrix.
- `golden_calibration_report.json` / `.md`: base/final calibration evidence.
- `oracle_audit.json` / `.md`: shared testcase oracle audit.
- `eval_manifest.json`: model, overall timing, build, and code-generation data.
- `environment.json`: Android and model environment versions.
- `SHA256SUMS`: hashes for the compact archive.
