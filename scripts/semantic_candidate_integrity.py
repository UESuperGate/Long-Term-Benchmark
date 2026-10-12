#!/usr/bin/env python3
"""Reject candidate-owned semantic oracles and benchmark-specific state machines."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


ANDROID_PROTECTED = {
    "app/src/debug/AndroidManifest.xml",
    "app/src/debug/kotlin/io/element/android/x/StateTestContract.kt",
    "app/src/debug/kotlin/io/element/android/x/StateTestProbeProvider.kt",
    "app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt",
}

FORBIDDEN_ADDED_PATTERNS = {
    "case_id_literal": re.compile(r"(?:us|gm|tp|ll|lnd)_state_\d+"),
    "candidate_semantic_facts": re.compile(r"\bsemanticFacts\b|stateProbeSemanticFacts"),
    "candidate_probe_snapshot": re.compile(r"state_probe_snapshot|stateProbeSnapshot"),
    "candidate_fact_marker": re.compile(r"strict_state_fact"),
}


def _git(candidate: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=candidate,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _changed_paths(candidate: Path) -> set[str]:
    changed = _git(candidate, "diff", "--name-only", "HEAD", "--").stdout.splitlines()
    untracked = _git(candidate, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    return {value.strip().replace("\\", "/") for value in [*changed, *untracked] if value.strip()}


def _added_text(candidate: Path, changed_paths: set[str]) -> str:
    diff = _git(candidate, "diff", "--unified=0", "--no-ext-diff", "HEAD", "--").stdout
    added = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    tracked = set(_git(candidate, "ls-files").stdout.splitlines())
    for relative in sorted(changed_paths - tracked):
        path = candidate / relative
        if path.is_file() and path.stat().st_size <= 1_000_000:
            added.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(added)


def audit_candidate(candidate: Path, platform: str) -> dict[str, Any]:
    if not (candidate / ".git").exists() or _git(candidate, "rev-parse", "--verify", "HEAD").returncode != 0:
        return {
            "valid": False,
            "status": "baseline_missing",
            "violations": ["Candidate has no immutable Git baseline for integrity comparison."],
        }

    changed_paths = _changed_paths(candidate)
    violations: list[str] = []
    if platform == "android":
        protected = sorted(changed_paths & ANDROID_PROTECTED)
        if protected:
            violations.append("Modified evaluator-owned Android scaffold: " + ", ".join(protected))

    state_test_sources = sorted(
        path for path in changed_paths
        if "StateTest" in Path(path).name and path not in ANDROID_PROTECTED
    )
    if state_test_sources:
        violations.append("Added or modified candidate-owned state-test source: " + ", ".join(state_test_sources))

    added_text = _added_text(candidate, changed_paths)
    for name, pattern in FORBIDDEN_ADDED_PATTERNS.items():
        if pattern.search(added_text):
            violations.append(f"Added benchmark-specific semantic output ({name}).")

    modified_inputs = sorted(path for path in changed_paths if path.startswith("_benchmark_inputs/"))
    if modified_inputs:
        violations.append("Modified immutable benchmark inputs: " + ", ".join(modified_inputs))

    return {
        "valid": not violations,
        "status": "valid" if not violations else "candidate_oracle_detected",
        "violations": violations,
        "changedPathCount": len(changed_paths),
    }
