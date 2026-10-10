# Android OpenCode + GLM-5.3 Evaluation

This directory preserves the 2026-10-10 Android expansion of the Element X
multi-platform benchmark. Android uses the official Element X Android release
tags while sharing the same 150 public state-transition testcases and hidden
semantic oracles as the ArkTS benchmark.

## Validity

The base/final calibration is valid: every one of the 300 target-case rows
reached the Android debug provider, all base assertions failed, and all
ground-truth-final assertions passed.

The OpenCode agent run is **not a valid model score**. The configured endpoint
returned HTTP 402 with `subscription_request_limit_exhausted` during task 1 and
immediately for tasks 2-5. None of the candidates received an agent
implementation or the required debug provider. Their APKs still built and
installed successfully, but all 150 rows are `protocolFail` / `not_scored`.
Consequently this run does not satisfy the requested agent-result
discrimination criterion and must not be reported as a 0/150 semantic score.

## Results

| Task | Cases | Base pass/fail | Golden final pass/fail | Agent semantic pass/fail | Agent protocol fail | Build |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 01 User status | 26 | 0/26 | 26/0 | N/A | 26 | pass |
| 02 Gallery messages | 28 | 0/28 | 28/0 | N/A | 28 | pass |
| 03 Timeline protection/rich events | 32 | 0/32 | 32/0 | N/A | 32 | pass |
| 04 Live location | 30 | 0/30 | 30/0 | N/A | 30 | pass |
| 05 Link new device | 34 | 0/34 | 34/0 | N/A | 34 | pass |
| **Total** | **150** | **0/150** | **150/0** | **N/A** | **150** | **5/5** |

## Environment

- Official source: `element-hq/element-x-android`
- OpenCode: v2.0.20
- Model: `bigmodel-glm/glm-5.3`
- Endpoint: `https://api.kjdfhl.school/v1`
- Agent/build timeout: 3600 seconds per task
- Java: OpenJDK 21.0.12.1
- Android SDK platforms: API 36 and API 37
- Android build tools: 35.0.0, 36.0.0, and 37.0.0
- Emulator: 37.2.12.0
- AVD: Android 17/API 37, `arm64-v8a`
- FOSS/GPlay min SDK: API 24; enterprise min SDK: API 33
- Release compile/target SDK: API 36 for older tags and API 37 for newer tags

The API key remained in the local OpenCode secret file and is not stored in
this repository.

## Workflow

1. Create isolated archives from each official Android base tag and expose only
   the public requirement spec, state-test YAML, schema, and provider protocol.
2. Run OpenCode in a candidate root outside the benchmark checkout. `PWD` and
   `OLDPWD` are pinned to that root, and network/GitHub tools are denied.
3. Independently build an arm64 `gplayDebug` APK with Java 21 and the release's
   own Gradle, AGP, compile SDK, and target SDK versions.
4. Install APKs on the API 37 emulator. Query the debug provider once for the
   initial state and once after each public `stateEvent`, retaining every phase.
5. Compare every phase with the same evaluator-owned binding manifest used by
   ArkTS. Transport failures remain separate from semantic failures.

Before the formal run, endpoint calibration exposed long-context connection
resets. The local model declaration was conservatively capped at a 48,000-token
context and 8,192-token output/thinking budget so OpenCode could compact before
the gateway's practical limit. Diagnostic and contaminated attempts are not
included in the score.

## Artifacts

- `run_summary.json`: compact result and validity verdict.
- `environment.json`: Android and model environment.
- `golden_calibration_report.json`: all 300 base/final rows and phase evidence.
- `agent_strict_report.json`: all 150 agent protocol failures.
- `agent_target_matrix.json`: the generated cross-platform target matrix.
- `eval_manifest.json`: OpenCode durations, exits, APK paths, and build exits.
- `golden_build_manifest.json`: ten official-tag Android builds.
- `android_golden_apks.sha256`: hashes captured before removing large ignored
  APK binaries from the local run directory.
- `agent_failure_summary.json`: normalized quota-failure classification.
- `oracle_audit.json`: all 150 shared state-transition cases validated as
  `valid_oracle` before scoring.
- `SHA256SUMS`: hashes for this compact archive.
