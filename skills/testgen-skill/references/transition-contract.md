# Canonical Transition Contract

The canonical contract is platform-neutral and evaluator-owned:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "owner": "evaluator",
  "cases": [
    {
      "caseId": "ll_start_success",
      "key": "start_success",
      "functionalArea": "lifecycle",
      "given": {"activeShares": [], "permission": "granted"},
      "event": {"name": "startShare", "roomId": "!room"},
      "expected": {
        "state": {"activeShares": ["!room"]},
        "effects": ["persistExpiry", "startCoordinator"],
        "ui": ["liveLocationBanner"]
      },
      "invariants": ["other room state is unchanged"],
      "evidence": {"androidProduction": ["..."], "androidTests": ["..."]},
      "traceDigest": "sha256-of-normalized-taskId-key-given-event-expected"
    }
  ]
}
```

Normalize `taskId`, `key`, `given`, `event`, and `expected` as JSON with sorted keys and compact separators before hashing. This matches Long-Term-Benchmark's `generate_cross_platform_contract.py`. Platform bindings point to the digest; they never alter the semantic payload. Invariants are still compared across platforms even though the current schema does not include them in the digest.

## Case Design Rules

- One case proves one meaningful state transition or one atomic initial-state constraint.
- Observe state and externally visible effects, not class names or exact implementation shape.
- Include negative assertions when absence matters, such as no duplicate dispatch or no leaked status text.
- Exercise async completion explicitly: request, loading, success/failure, and cleanup are separate phases when observable.
- Keep unchanged regression tests outside the polarity set because base must fail every scored case.
- Prefer runtime tests. A source observer is acceptable only when runtime execution is unavailable and must be labeled `observationMode: source_transition_conformance`. It scans configured production roots plus changed production files and accepts equivalent implementation structures. If no production source is observed, every case is `not_scored`, never `fail`.

## Result Format

Normalize each evaluated target to:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "platform": "android",
  "role": "agent",
  "codeGeneration": {"passed": true, "changedProductionFiles": ["..."]},
  "compile": {"passed": true, "command": "./gradlew ..."},
  "semantic": {
    "cases": [
      {"caseId": "ll_start_success", "traceDigest": "...", "status": "pass"}
    ]
  },
  "diagnostics": {"adapter": "ready", "transport": "ready"}
}
```

Statuses are `pass`, `fail`, or `not_scored`. Diagnostics explain missing observations but are not benchmark metrics.
