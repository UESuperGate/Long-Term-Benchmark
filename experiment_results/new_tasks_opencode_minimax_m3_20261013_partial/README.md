# Element X tasks 08-18 benchmark

This bundle records 11 tasks calibrated on Android and migrated to ArkTS with one shared transition contract per task.

Evaluation is partial: 13 of 22 platform-task runs are unavailable or not yet run and are excluded from all benchmark denominators. Resume with `python3 scripts/run_new_tasks_opencode_eval_macos.py --run-id new_tasks_opencode_minimax_m3_20261013 --agent-timeout 3600 --parallel 2 --resume`.

| Metric | Result |
| --- | ---: |
| Code generation | 9/9 |
| Compile | 8/9 |
| Semantic testcase | 40/80 |
| Evaluation coverage | 9/22 runs |

Four-way polarity valid: `true`. Agent discrimination is reported as evidence and is not forced by changing semantic expectations.
