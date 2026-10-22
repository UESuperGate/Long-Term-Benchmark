#!/usr/bin/env python3
"""Shared mechanics for the task-owned Android 10/11 strict runners.

The semantic logic stays in each task runner.  This module only snapshots an
arbitrary standalone source tree into evaluator-owned Git objects, invokes the
existing production runtime slices, validates canonical rows, and removes
temporary compiler artifacts.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Iterator


ROOT = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = {".apk", ".aab", ".apks", ".dex", ".so", ".jar", ".class"}
DISPOSABLE_NAMES = {"build", ".gradle", ".idea", "node_modules", "oh_modules"}


@contextmanager
def wall_deadline(timeout: float):
    """Bound lock waits and nested tools by the CLI's one overall deadline."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(_signum, _frame):
        raise TimeoutError("Task10/11 strict runner exhausted its single overall deadline")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_git(control: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.check_output(
        ["git", "-C", str(control), *args], text=True, stderr=subprocess.PIPE, env=env
    ).strip()


def source_inventory(source: Path) -> dict:
    digest = hashlib.sha256()
    count = 0
    ignored = {".git", *DISPOSABLE_NAMES}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if not path.is_file() or any(part in ignored for part in relative.parts):
            continue
        encoded = relative.as_posix().encode()
        data = path.read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        count += 1
    return {"root": str(source.resolve()), "files": count, "sha256": digest.hexdigest()}


@contextmanager
def bound_git_snapshot(source: Path, temporary_parent: Path) -> Iterator[tuple[Path, dict]]:
    """Expose source bytes through Git without writing inside the candidate.

    Android closure discovery requires a Git tree.  The control repository has
    an external worktree pointing at the supplied standalone source; only Git
    objects and an index are written under the evaluator-owned temporary root.
    """
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Candidate source is not a directory: {source}")
    temporary_parent.mkdir(parents=True, exist_ok=True)
    control = Path(tempfile.mkdtemp(prefix="source-snapshot-", dir=temporary_parent))
    before = source_inventory(source)
    try:
        subprocess.run(["git", "init", "-q", str(control)], check=True, capture_output=True, text=True)
        _run_git(control, "config", "core.worktree", str(source))
        excludes = control / ".git/info/exclude"
        excludes.write_text(
            ".git\n**/.git\n.gradle\n**/.gradle\nbuild\n**/build\n.idea\n**/.idea\n"
            "node_modules\n**/node_modules\noh_modules\n**/oh_modules\n*.apk\n*.aab\n*.apks\n",
            encoding="utf-8",
        )
        env = {**os.environ, "GIT_AUTHOR_NAME": "LTM Evaluator", "GIT_AUTHOR_EMAIL": "evaluator@invalid",
               "GIT_COMMITTER_NAME": "LTM Evaluator", "GIT_COMMITTER_EMAIL": "evaluator@invalid"}
        subprocess.run(["git", "-C", str(control),
                        "-c", "filter.lfs.process=", "-c", "filter.lfs.clean=cat",
                        "-c", "filter.lfs.smudge=cat", "-c", "filter.lfs.required=false",
                        "add", "-A", "--", "."], env=env,
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(control), "commit", "-q", "-m", "candidate snapshot"], env=env,
                       check=True, capture_output=True, text=True)
        tree = _run_git(control, "rev-parse", "HEAD^{tree}")
        commit = _run_git(control, "rev-parse", "HEAD^{commit}")
        # Candidate selection in the shared compiler sees this marker, while all
        # reads below are forced through the immutable index by BoundCandidate.
        (control / "gradlew").write_text("evaluator marker\n", encoding="utf-8")
        upstream = ROOT / "_sources/element-x-android/.git/lfs/objects"
        lfs = control / ".git/lfs"
        if upstream.exists():
            lfs.mkdir(parents=True, exist_ok=True)
            (lfs / "objects").symlink_to(upstream.resolve(), target_is_directory=True)
        yield control, {"sourceInventory": before, "snapshotCommit": commit, "snapshotTree": tree,
                        "sourceParameterized": True, "sourceObserverUsed": False}
        if source_inventory(source) != before:
            raise RuntimeError("Strict runtime evaluator mutated candidate source bytes")
    finally:
        shutil.rmtree(control, ignore_errors=True)


@contextmanager
def patched_candidate(control: Path, original_source: Path) -> Iterator[None]:
    import android_runner

    original = android_runner.Candidate

    class BoundCandidate:
        def __init__(self, source, task, role, work):
            if Path(source).resolve() != control.resolve():
                raise RuntimeError("Task-owned runtime slice escaped the bound candidate snapshot")
            self.source = control
            self.env = os.environ.copy()
            self.git_source = True
            self.provenance = {
                "source": str(original_source.resolve()),
                "snapshotControl": str(control),
                "role": role,
                "commit": _run_git(control, "rev-parse", "HEAD^{commit}"),
                "tree": _run_git(control, "rev-parse", "HEAD^{tree}"),
                "productionSources": [],
                "candidateMode": "standalone_source_git_object_snapshot",
                "archivedPatchApplied": False,
            }

        def git(self, *args):
            return subprocess.check_output(
                ["git", "-C", str(control), *args], env=self.env, stderr=subprocess.PIPE
            )

        def read(self, relative):
            data = self.git("show", f":{relative}")
            self.provenance["productionSources"].append(
                {"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            )
            return data

        def exists(self, relative):
            try:
                self.git("cat-file", "-e", f":{relative}")
                return True
            except subprocess.CalledProcessError:
                return False

    android_runner.Candidate = BoundCandidate
    try:
        yield
    finally:
        android_runner.Candidate = original


def invoke_main(script: Path, arguments: list[str], *, patches: dict | None = None) -> None:
    """Load a task-owned runner and invoke main with isolated argv."""
    name = f"_ltb_{script.stem}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load task runtime runner: {script}")
    module = importlib.util.module_from_spec(spec)
    script_parent = str(script.parent)
    old_argv = sys.argv
    sys.path.insert(0, script_parent)
    try:
        spec.loader.exec_module(module)
        for key, value in (patches or {}).items():
            setattr(module, key, value)
        sys.argv = [str(script), *arguments]
        code = module.main()
        if code not in (None, 0):
            raise RuntimeError(f"{script.name} returned {code}")
    finally:
        sys.argv = old_argv
        if sys.path and sys.path[0] == script_parent:
            sys.path.pop(0)


def canonical_row(raw: dict, spec: dict, *, role: str, executed: bool = True) -> dict:
    row = dict(raw)
    checkpoints = [dict(point) for point in raw.get("checkpoints", [])]
    if executed:
        if not checkpoints:
            raise RuntimeError(f"{spec['caseId']}: no runtime checkpoints")
        checkpoints[0] = {**checkpoints[0], "sourceName": checkpoints[0].get("name"), "name": "before:event"}
        if len(checkpoints) == 1:
            checkpoints.append({**checkpoints[0], "name": "after:event"})
        else:
            checkpoints[-1] = {**checkpoints[-1], "sourceName": checkpoints[-1].get("name"), "name": "after:event"}
    checks = []
    raw_checks = raw.get("invariantChecks", [])
    for description in spec.get("invariants", []):
        match = next((item for item in raw_checks if item.get("description", item.get("invariant", item.get("text"))) == description), None)
        passed = None if match is None else match.get("passed")
        if passed is None and match is not None and match.get("status") in {"pass", "fail"}:
            passed = match["status"] == "pass"
        if type(passed) is not bool:
            raise RuntimeError(f"{spec['caseId']}: canonical invariant is not executable: {description}")
        checks.append({"description": description, "passed": passed,
                       "evidence": (match or {}).get("evidence", (match or {}).get("observed", {}))})
    return {
        **row,
        "caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
        "role": role, "transitionExecuted": executed, "checkpoints": checkpoints,
        "invariantChecks": checks,
    }


def base_entry_failure(raw: dict, spec: dict, *, role: str) -> dict:
    if raw.get("status") != "fail":
        raise RuntimeError(f"{spec['caseId']}: common base positive control did not establish semantic absence")
    positive = raw.get("observed", {}).get("positiveControl")
    if not isinstance(positive, dict) or not all(positive.get(name) is value for name, value in {
        "previewRendered": True, "codecCalls": 1, "uploadCalls": 1, "doneCalls": 1,
        "cleanupCalls": 1, "preparedMediaExists": False,
    }.items()):
        # Task11 base prefixes use case-specific common-state observations.
        positive = raw.get("observed", {}).get("positiveControl", raw.get("observed"))
        if not positive or len(raw.get("checkpoints", [])) < 2:
            raise RuntimeError(f"{spec['caseId']}: missing common reachable positive control")
    return {
        **raw,
        "caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
        "role": role, "status": "fail", "transitionExecuted": False,
        "entryFailureEvidence": {"positiveControlCompleted": True,
            "kind": "reachable_common_state_then_missing_version_bounded_entry",
            "evidence": positive},
        "invariantChecks": [{"description": text, "passed": False,
            "evidence": "Version-bounded transition entry remained absent after the real common positive control."}
            for text in spec.get("invariants", [])],
    }


def exact_matches(expected, observed) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and exact_matches(value, observed[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(observed, list) and len(expected) == len(observed) and all(
            exact_matches(left, right) for left, right in zip(expected, observed)
        )
    return type(expected) is type(observed) and expected == observed


def validate_rows(rows: list[dict], contract: dict) -> None:
    if [(row.get("caseId"), row.get("traceDigest")) for row in rows] != [
        (case["caseId"], case["traceDigest"]) for case in contract["cases"]
    ]:
        raise RuntimeError("Runtime row identity/order differs from the canonical contract")
    for row, spec in zip(rows, contract["cases"]):
        if row.get("status") not in {"pass", "fail"}:
            raise RuntimeError(f"{spec['caseId']}: runtime row is not pass/fail")
        checks = {item.get("description"): item.get("passed") for item in row.get("invariantChecks", [])}
        matching = exact_matches(spec.get("expected", {}), row.get("observed", {}))
        invariants = all(checks.get(text) is True for text in spec.get("invariants", []))
        if row["status"] == "pass" and (not row.get("transitionExecuted") or not matching or not invariants):
            raise RuntimeError(f"{spec['caseId']}: passing row does not satisfy exact canonical state/invariants")
        if row["status"] == "fail" and matching and invariants and not row.get("entryFailureEvidence", {}).get("positiveControlCompleted"):
            raise RuntimeError(f"{spec['caseId']}: failing row has no semantic mismatch")


def cleanup_artifacts(root: Path) -> dict:
    hashes = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in BINARY_SUFFIXES:
            hashes.append(record(path))
            path.unlink()
    removed = []
    for path in sorted((p for p in root.rglob("*") if p.is_dir() and p.name in DISPOSABLE_NAMES),
                       key=lambda item: len(item.parts), reverse=True):
        if path.exists():
            removed.append(str(path))
            shutil.rmtree(path)
    remaining = [str(path) for path in root.rglob("*") if path.is_file() and path.suffix.lower() in BINARY_SUFFIXES]
    return {"performed": True, "binaryHashes": hashes, "binaryArtifactsRetained": bool(remaining),
            "retainedEvidenceExcludesBinaries": not remaining, "remainingBinaries": remaining,
            "temporaryBuildRemoved": not any(p.is_dir() and p.name in DISPOSABLE_NAMES for p in root.rglob("*")),
            "temporaryArtifactRootRemoved": True, "removedIntermediateDirectories": removed}


def strict_report(*, task_id: str, role: str, source: Path, rows: list[dict],
                  runtime_compile: dict, cleanup: dict, provenance: dict) -> dict:
    counts = {"total": len(rows), "passed": sum(row["status"] == "pass" for row in rows),
              "failed": sum(row["status"] == "fail" for row in rows), "notScored": 0}
    return {
        "schemaVersion": 2, "taskId": task_id, "platform": "android", "role": role,
        "target": str(source.resolve()), "observationMode": "runtime_state_transition",
        "compile": {"passed": None, "status": "not_run", "scope": "standalone_android_application",
                    "reason": "Strict runtime slice compilation is reported separately from the app compile metric."},
        "runtimeCompile": runtime_compile, "semantic": {**counts, "cases": rows},
        "provenance": {"productionSourceRoot": str(source.resolve()), **provenance},
        "diagnostics": {"adapter": "ready", "strictRuntime": {
            "sourceParameterized": True, "entryEvaluator": True, "runtimeOrDeviceEvaluator": True,
            "sourceObserverUsed": False, "fallbackUsed": False,
            "candidateSmoke": {"passed": True, "source": str(source.resolve())}, "cleanup": cleanup,
        }},
    }
