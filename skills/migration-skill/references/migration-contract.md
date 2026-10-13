# Android-To-ArkTS Migration Contract

The migration bundle must contain:

```text
migrations/<task-id>/
  manifest.json
  android/task.json
  canonical/transitions.json
  arkts/base/
  arkts/final/
  arkts/bindings.json
  results/android-base.json
  results/android-final.json
  results/arkts-base.json
  results/arkts-final.json
  results/arkts-agent.json
```

`manifest.json` records exact source refs and toolchain versions. It also records which Android modules map to which ArkTS modules and identifies intentionally unsupported platform-specific behavior.

`arkts/bindings.json` maps canonical cases to ArkTS mechanics:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "canonicalContract": "../canonical/transitions.json",
  "cases": [
    {
      "caseId": "ll_start_success",
      "traceDigest": "...",
      "fixture": "LiveLocationFixture.activeRoom",
      "eventEntrypoint": "startLiveLocation(roomId)",
      "observations": ["store.expiry", "coordinator.running", "banner.visible"]
    }
  ]
}
```

Bindings may change framework-specific setup, event dispatch, and observation paths. They must not change `given`, `event`, `expected`, invariants, case grouping, or digest.

## Four-Way Calibration

For `N` canonical cases:

| Platform | Role | Required semantic result |
| --- | --- | --- |
| Android | base | `0/N` pass, `N/N` fail |
| Android | ground-truth final | `N/N` pass |
| ArkTS | base | `0/N` pass, `N/N` fail |
| ArkTS | ground-truth final | `N/N` pass |

Every row must be scored. A compile or adapter failure is a calibration defect until repaired.

## Completeness Review

Before calling an ArkTS project a migrated base or final, verify navigation reachability, state/effect implementation, SDK or service boundaries, persistence, errors and cancellation, real UI rendering, resources, and unrelated workflows needed to exercise the feature. Passing a small semantic subset is necessary but not sufficient evidence of complete migration.
