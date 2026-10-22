# Task17 base worker lease recovery

The Task17 base-all v1 worker left its fail-closed safety lease after producing
an unsafe revocation report. No semantic or compile verdict is inferred from
that run.

Retained lease owner payload:

```json
{
  "pid": 88160,
  "output": "/Users/z1an/research/Long-Term-Benchmark/experiment_results/runtime_transition_20261022/task17_android_base_all_v7_v1",
  "protocol": "task17.android.original-dagger.worker.v7",
  "kernelFlockSurvivesProcessExit": false
}
```

Coordinator recovery checks on 2026-10-22:

- PID 88160 was absent from `ps`.
- No Task17 worker, Gradle test, or Gradle daemon process was active.
- `lsof` reported no holder for the shared lock or safety lease.
- Only `owner.json` existed inside the lease directory.

Recovery removes only the stale `owner.json` and its now-empty lease directory.
The shared lock file, project evidence, source, build caches, and reports remain
unchanged.

## Second recovery

The base-all v4 coordinator was externally terminated after five isolated cases
and left the same fail-closed lease shape:

```json
{
  "pid": 94406,
  "output": "/Users/z1an/research/Long-Term-Benchmark/experiment_results/runtime_transition_20261022/task17_android_base_all_v7_v4",
  "protocol": "task17.android.original-dagger.worker.v7",
  "kernelFlockSurvivesProcessExit": false
}
```

PID 94406 was absent, no Task17/Gradle test process was active, and `lsof`
reported no holder. The five already-written native JSON files are retained as
raw evidence, but the revoked worker report is not promoted. Remaining cases
are executed separately and combined only by an independent hash-based
aggregator.

## Third recovery

The base case006 v5 worker crossed the disk guard during preparation and was
hard-revoked before Gradle/testcase execution. Its owner PID was `96671`; the
PID was absent and neither `ps` nor `lsof` found an active holder. The revoked
output tree is retained and is not counted as a benchmark result. Only the
orphaned lease marker is removed so a later run can proceed after storage
recovery.

## Fourth recovery

The first base case009 attempt was hard-revoked at the disk guard before test
execution. Owner PID `98954` was absent and no lock/process holder remained.
The revoked output is retained and excluded from scoring. Completed case006-008
archives are reclaimed with a separate hash ledger before retrying case009.
