# OpenCode + GLM-5.3 Long-Horizon Evaluation

This directory preserves the 2026-10-09 rerun after increasing the per-task
agent timeout to 3600 seconds and upgrading the ArkTS state-capture workflow.

## Environment

- OpenCode: v2.0.20
- Model: `bigmodel-glm/glm-5.3`
- Endpoint: `https://open.bigmodel.cn/api/coding/paas/v4`
- DevEco Studio: 6.1.1
- OpenHarmony SDK: API 23, version 6.1.0.32
- Agent timeout: 3600 seconds per task
- Agent completion: 5/5 normal exits, 0 timeouts
- Candidate build: 5/5 successful HAP builds

The API key remained in the local OpenCode secret configuration and is not
stored in this repository.

## Results

| Task | Cases | Base pass/fail | Golden final pass/fail | Agent pass/fail | Agent time | Build |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 01 User status | 26 | 0/26 | 26/0 | 10/16 | 883.8s | pass |
| 02 Gallery messages | 28 | 0/28 | 28/0 | 28/0 | 1003.0s | pass |
| 03 Timeline protection/rich events | 32 | 0/32 | 32/0 | 14/18 | 1091.4s | pass |
| 04 Live location | 30 | 0/30 | 30/0 | 27/3 | 1254.8s | pass |
| 05 Link new device | 34 | 0/34 | 34/0 | 33/1 | 1222.4s | pass |
| **Total** | **150** | **0/150** | **150/0** | **112/38** |  | **5/5** |

All 300 golden calibration rows matched the expected polarity. All 150 agent
rows reached the state-test protocol and were semantically scored. The strict
agent run contains 112 matched rows, 38 semantic mismatches, and no
`protocolFail` rows.

The old 900-second budget was too short for this workload: four of the five
successful agent runs took longer than 900 seconds, and the remaining run
finished in 883.8 seconds.

## Workflow

1. Copy each base project into an isolated candidate directory and expose only
   the public requirement spec, state-test YAML, schema, and runtime protocol.
2. Run OpenCode with GLM-5.3 for up to 3600 seconds, followed by an independent
   `ohpm install` and `hvigorw assembleHap --no-daemon` build.
3. Calibrate evaluator polarity against base and trusted final HAPs in
   `compatible` mode. Base must fail and final must pass every final-positive
   testcase.
4. Launch each agent testcase with `caseId`, poll for a case-specific ready
   marker and matching snapshot, and capture the ArkUI layout tree.
5. Deliver each public `stateEvent` through the Ability Want, wait for the
   acknowledged transition phase, and capture that phase independently.
6. Derive facts from ArkUI ids, visibility, enabled state, text, and properties;
   combine those observations with facts derived from current runtime state.
7. Score candidates in `strict` mode against evaluator-owned bindings. Strict
   mode does not accept the aggregate transition fallback used to calibrate
   legacy golden projects.

The five base projects now include the answer-free `caseId`/`stateEvent`
transport and singleton Ability launch configuration for future runs. The
candidates represented by these reports were kept as the original agent
outputs during scoring.

## Artifacts

- [`run_summary.json`](run_summary.json): compact machine-readable result.
- [`golden_calibration_report.json`](golden_calibration_report.json): all 300
  base/final calibration rows and phase details.
- [`agent_strict_report.json`](agent_strict_report.json): all 150 strict agent
  rows and phase details.
- [`agent_target_matrix.json`](agent_target_matrix.json): generated target and
  case matrix used for agent scoring.
- [`manifests/`](manifests): OpenCode/build manifests for each task.
- [`SHA256SUMS`](SHA256SUMS): artifact integrity hashes.
