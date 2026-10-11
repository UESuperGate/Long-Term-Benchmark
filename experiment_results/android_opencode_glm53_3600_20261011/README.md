# Android OpenCode + GLM-5.3 Post-Recharge Retry

This directory preserves the 2026-10-11 retry of the Android Element X
multi-platform benchmark after the configured GLM endpoint resumed service.
Android uses official Element X Android release tags and the same 150 public
state-transition testcases and evaluator-owned semantic oracles as ArkTS.

## Validity

The base/final calibration remains valid and is copied from the immediately
preceding Android calibration run: all 300 target-case rows reached the debug
provider, base passed 0/150, and ground-truth final passed 150/150.

The agent retry is **not a valid semantic model score**. The endpoint accepted
requests, but tasks 1-4 reached the 3600-second agent timeout. Task 5 exited
normally after 2921.534 seconds without changing the base checkout. Four APKs
built and installed; task 2 failed to compile. None of the five candidates
implemented the required debug state-test provider, so strict evaluation
classified all 150 rows as `protocolFail` / `not_scored`. This must not be
reported as a 0/150 semantic score and does not satisfy the requested
agent-result discrimination criterion.

## Results

| Task | Cases | Base pass/fail | Golden final pass/fail | Agent semantic pass/fail | Agent protocol fail | Agent exit | Build |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 01 User status | 26 | 0/26 | 26/0 | N/A | 26 | 124 (timeout) | pass |
| 02 Gallery messages | 28 | 0/28 | 28/0 | N/A | 28 | 124 (timeout) | fail |
| 03 Timeline protection/rich events | 32 | 0/32 | 32/0 | N/A | 32 | 124 (timeout) | pass |
| 04 Live location | 30 | 0/30 | 30/0 | N/A | 30 | 124 (timeout) | pass |
| 05 Link new device | 34 | 0/34 | 34/0 | N/A | 34 | 0 | pass |
| **Total** | **150** | **0/150** | **150/0** | **N/A** | **150** | **4 timeouts** | **4/5** |

Protocol failure breakdown: task 2 contributed 28 `artifact_missing` rows;
the four installable APKs contributed 122 `snapshot_missing` rows because the
`${applicationId}.state-test-probe` provider was absent.

## Agent Behavior

- Task 1 spent most of its window upgrading the Matrix SDK and repairing
  compatibility breaks. Its partial candidate built, but did not implement the
  requested end-to-end feature or provider.
- Task 2 added partial gallery API, mapping, and UI model work, then failed the
  full build on non-exhaustive timeline-content branches and caption parsing.
- Task 3 added a partial content-scanner API scaffold. Its APK built without a
  provider.
- Task 4 repeatedly re-read the contract after context compaction and timed out
  with no production changes.
- Task 5 repeatedly re-read the contract, exited 0 without changing the base,
  and therefore produced a buildable but semantically unchanged APK.

Long endpoint response delays were observed, especially before substantive
work on tasks 2, 3, and 5. OpenCode also compacted repeatedly at the declared
48,000-token context limit; GLM frequently resumed by re-reading the same
contract and source files instead of continuing implementation.

## Environment

- Official source: `element-hq/element-x-android`
- OpenCode: v2.0.20
- Model: `bigmodel-glm/glm-5.3`
- Endpoint: `https://api.kjdfhl.school/v1`
- Agent/build timeout: 3600 seconds per task
- Declared context/output: 48,000 / 8,192 tokens
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

1. Create isolated candidates from each official Android base tag and expose
   only the public requirement spec, state-test YAML, schema, and provider
   protocol.
2. Run OpenCode in an external candidate root with `PWD` and `OLDPWD` pinned to
   that root. Network and GitHub tools are denied.
3. Independently build an arm64 `gplayDebug` APK with Java 21 and each release's
   own Gradle, AGP, compile SDK, and target SDK versions.
4. Install candidate APKs on an API 37 emulator. Query the debug provider for
   the initial state and after every public `stateEvent`.
5. Compare every phase with the same evaluator-owned binding manifests used by
   ArkTS. Transport/protocol failures stay separate from semantic failures.

The tool audit found no forbidden network command and no tool input that
accessed the benchmark checkout. GitHub URLs present in edit inputs were
existing source-code comments, not network retrieval.

## Artifacts

- `run_summary.json`: compact result and validity verdict.
- `environment.json`: Android, model, and timeout environment.
- `golden_calibration_report.json`: reused valid 300-row base/final evidence.
- `agent_strict_report.json`: all 150 strict agent protocol failures.
- `agent_target_matrix.json`: generated cross-platform target matrix.
- `eval_manifest.json`: agent durations, exits, APK paths, and build exits.
- `agent_failure_summary.json`: normalized timeout/build/protocol disposition.
- `oracle_audit.json`: all 150 shared cases validated as `valid_oracle`.
- `SHA256SUMS`: hashes for this compact archive.
