# Explore-Skill Artifact Contract

Store one directory per candidate task:

```text
tasks/<task-id>/
  task.json
  requirement.md
  evidence.json
```

`task.json` is the machine-readable handoff:

```json
{
  "schemaVersion": 1,
  "taskId": "04_live_location",
  "title": "Live location lifecycle",
  "status": "accepted",
  "android": {
    "repository": "https://example/repo.git",
    "baseRef": "v1.2.0",
    "baseCommit": "...",
    "finalRef": "v1.3.0",
    "finalCommit": "..."
  },
  "releaseNotes": [{"text": "...", "source": "CHANGELOG.md"}],
  "functionalAreas": ["lifecycle", "persistence", "failure_recovery"],
  "stateSurfaces": ["manager", "store", "screen"],
  "eventEntrypoints": ["start", "stop", "restore", "expire"],
  "evidence": {
    "productionPaths": ["feature/src/main/..."],
    "testPaths": ["feature/src/test/..."],
    "commits": ["..."]
  },
  "nonGoals": ["Unchanged map-provider behavior"],
  "handoff": {"requirement": "requirement.md", "evidence": "evidence.json"}
}
```

Allowed status values are `accepted`, `rejected`, and `needs_review`. Use `needs_review` when release wording and implementation evidence disagree.

`requirement.md` must contain the version boundary, user outcome, functional requirements, failure/recovery behavior, invariants, and non-goals. It must not contain final patches, private selectors, exact oracle facts, or instructions to copy final code.

`evidence.json` may contain detailed commits, diff paths, symbols, tests, and release-note excerpts. This file is evaluator-private and is not copied into an agent workspace.
