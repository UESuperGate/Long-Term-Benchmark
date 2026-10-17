---
name: explore-skill
description: Extract benchmark-ready long-horizon development tasks from an Android project's release notes and matching Git history. Use when selecting version-bounded Android feature tasks, reconstructing task requirements from releases, or preparing task manifests for semantic-test generation and Android-to-ArkTS migration.
---

# Explore Android Long-Horizon Tasks

Turn release-note claims into evidence-backed Android development tasks. A task is the behavior added between an exact base ref and final ref, not the later Android-to-ArkTS migration work.

## Inputs

Require an Android Git repository and either a release interval or a set of release-note entries. Resolve every ref to an immutable commit before analysis. Keep the source checkout unchanged; use `git show`, `git diff`, or detached worktrees.

Read [task-contract.md](references/task-contract.md) before writing artifacts. For a local evidence inventory, run:

```bash
python3 scripts/collect_release_evidence.py \
  --repo /path/to/android \
  --base v1.2.0 \
  --final v1.3.0 \
  --output /path/to/task-evidence.json
```

## Workflow

1. **Freeze the release boundary.** Record the requested labels, resolved commits, release-note source, Android SDK/Gradle/JDK metadata, and repository remote. Never silently replace a missing tag with a nearby commit. Verify feature-commit containment because a release note can lag the tag that first contained the code; move the base back to the last tag without the behavior and document the mismatch.
2. **Build the evidence inventory.** Read release notes, commits, changed production files, changed tests, and changelog diffs. Cluster entries by one user-visible capability, not by commit count. Two entries may share a suite or release bundle without becoming one task; merge them only when their transitions form one connected state graph and serve one user outcome.
3. **Verify each candidate in code.** Trace the final implementation through state holders, event entrypoints, side effects, persistence or SDK boundaries, and rendered surfaces. Locate final tests, but do not treat test names alone as the requirement.
4. **Check the base.** Confirm that the final behavior is absent or observably incomplete in the base. Record the exact failing semantic boundary; a renamed API or moved file is not a feature delta.
5. **Apply the long-horizon filter.** Keep tasks that cross several implementation concerns and require multiple coherent state transitions, including at least one non-happy path. Reject dependency bumps, pure refactors, translations, formatting, one-line flags, isolated visual tweaks, and tasks whose only work is platform migration.
6. **Write the public requirement.** Describe user-visible behavior, version boundary, functional areas, failure and recovery behavior, invariants, and explicit non-goals. Do not expose final patches, private oracle selectors, or expected implementation paths to the candidate agent.
7. **Emit the handoff.** Store `task.json`, `requirement.md`, and `evidence.json` together. Hand them to `$testgen-skill`; do not generate semantic tests from release-note wording alone.

## Acceptance Gates

- Every requirement claim has release-note and code/test evidence.
- `baseRef` and `finalRef` resolve and `baseRef` is an ancestor of `finalRef`, unless a documented branch exception exists.
- The task has a coherent user outcome, at least three meaningful transitions, and at least one failure, cancellation, timeout, retry, or recovery path.
- The task is implementable from the public requirement without access to the final source.
- The task does not bundle unrelated release features merely to make it look longer.
- A merged task has one connected state graph; otherwise preserve separate task IDs and use an optional suite manifest for grouping.
- The base is the newest immutable tag proven not to contain the target behavior, even when the changelog lists the feature under a later release.

When evidence is ambiguous, keep the candidate as `needs_review` instead of inventing a requirement.
