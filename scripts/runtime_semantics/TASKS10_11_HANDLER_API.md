# Task10/11 Formal Handler API

Parent owns central dispatch and readiness. These modules never update either.

## Calibrated Candidate Handler

```python
from pathlib import Path
from scripts.runtime_semantics.tasks10_11_formal_scorer import dispatch

report = dispatch(
    "10_media_upload_quality",  # or "11_room_upgrade_navigation"
    platform="android",        # or "arkts"
    source=Path("/absolute/arbitrary/standalone/candidate"),
    base_source=Path("/absolute/calibration/base"),
    final_source=Path("/absolute/calibration/final"),
    output=Path("/absolute/evidence/agent.json"),
    timeout=3600,
    compile_passed=True,        # external completed app-build metric, not a slice result
    compile_command="caller-owned completed app-build command",
)
```

Equivalent task-owned APIs:

- `task10_formal_agent.score` / `task10_formal_agent.dispatch`
- `task11_formal_agent.score` / `task11_formal_agent.dispatch`

Both accept the same keyword arguments except the leading task ID. They use
actual source-parameterized runners by default. Optional `runtime_runner` and
testing injection are not needed by central dispatch.

`compile_passed=None` records app compile `not_run` and fails closed before
runtime; `False` preserves external compile failure and does not invoke runtime.
Strict runner reports independently record app compile `not_run` and
`runtimeCompile` for executed slices/device packages. No full app build is
started by this handler. Existing app-build evidence should be reused only when
the caller has verified its exact candidate source binding.

The single monotonic timeout covers source smoke, lock waits, dynamic base/final
calibration, and candidate runtime. No archived patch, project name, role, or
filename selects feature presence. Android loads the actual production state
entry; Task10 ArkTS inspects the actual original-page UI; Task11 ArkTS imports
the actual page-bound production module and probes its callable runtime API.
Missing-entry semantic failures require the exact real common-prefix controls.

## Strict Entrypoints

Each accepts `--source`, explicit `--role base|final|agent`, `--platform`,
`--output`, `--artifact-root`, and a remaining `--timeout` no greater than 3600:

- `task10_android_strict_runtime.py`
- `task11_android_strict_runtime.py`
- `task10_arkts_strict_runtime.cjs`
- `task11_arkts_strict_runtime.cjs`

The calibrated handler binds the actual production source manifests and copies
actual snapshots outside the disposable directory before deleting it. Raw
runner JSON alone is not the finalized handler envelope. The task-only
`finalize_tasks10_11_runtime.py` performs the same binding for direct diagnostic
runs, calls public validation, and hash-deletes the temporary build/input.

## Public Validation

```python
from scripts.run_runtime_transition_matrix import validate_report
validate_report(report, canonical_contract)
```

The parent-installed `SOURCE_BOUND_ENTRY_POLICIES` route calls:

```python
from scripts.runtime_semantics.tasks10_11_runtime_evidence import validate_entry_failure
validate_entry_failure(row, report, usedids, contract=canonical_contract)
```

Policy ID: `tasks10_11.android.common-prefix.v1`. Supported audited missing-entry
reports are Task10 Android/ArkTS and Task11 Android, with explicit base or agent
roles. The role must match the source-bound real execution, not just a relabelled
baseline. Task11 ArkTS uses executed ordinary transitions instead of that policy.

`tasks10_11_runtime_evidence.validate_report` adds snapshot/provenance integrity
checks, then calls the same unmodified public validator on the complete report.
Historical Task11 hash-only compact reports are partial diagnostics, not current
formal evidence. `refresh_tasks10_11_public_audit.py` retains the original verdict
and refreshes only the audited entry-policy envelope before public validation.

## Evidence And Status

Current source-bound public audit:
`experiment_results/runtime_transition_20261020/formal_tasks10_11_source_param_v1/public-audit-v6/`.

Base-copy and final-copy controls use random standalone directories and explicit
`role=agent`. They are sanity controls, never MiniMax agent results. Complete
four-way validation is still required before readiness: Task11 Android negative
control and Task11 ArkTS fresh actual-snapshot matrix remain incomplete.

APK/HAP/JAR/native intermediates are hashed before deletion. Actual before/after
snapshots and their hash-bound manifests remain readable. Device execution uses
the canonical `/tmp/ltb-arkts-device-<sha256(serial)[:16]>` lock. These Kotlin
slices do not invoke Gradle; any future Gradle probe must use the shared
`/tmp/long-term-benchmark-android-full-build.lock`. No additional Android or Rust
build should be started while the current SSD restriction is in effect.
