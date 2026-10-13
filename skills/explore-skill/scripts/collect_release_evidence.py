#!/usr/bin/env python3
"""Collect deterministic release and diff evidence for long-task extraction."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


RELEASE_NAMES = ("changelog", "changes", "release", "releases", "whatsnew", "what's-new")


def git(repo: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def resolve(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def commits(repo: Path, base: str, final: str) -> list[dict[str, str]]:
    raw = git(repo, "log", "--reverse", "--format=%H%x00%aI%x00%s%x00%b%x1e", f"{base}..{final}")
    rows = []
    for record in raw.split("\x1e"):
        fields = record.strip("\n").split("\x00", 3)
        if len(fields) == 4:
            rows.append(dict(zip(("commit", "authoredAt", "subject", "body"), fields)))
    return rows


def changed_files(repo: Path, base: str, final: str) -> list[dict[str, str]]:
    rows = []
    for line in git(repo, "diff", "--name-status", "-M", base, final).splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        path = parts[-1]
        lowered = path.lower()
        kind = "test" if any(token in lowered for token in ("/test/", "/androidtest/", "test.kt", "test.java")) else "production"
        rows.append({"status": parts[0], "path": path, "kind": kind})
    return rows


def release_files(repo: Path, final: str, requested: list[str]) -> list[str]:
    if requested:
        return requested
    paths = git(repo, "ls-tree", "-r", "--name-only", final).splitlines()
    return [path for path in paths if any(name in Path(path).name.lower() for name in RELEASE_NAMES)][:40]


def release_diffs(repo: Path, base: str, final: str, paths: list[str], max_chars: int) -> list[dict[str, object]]:
    result = []
    for path in paths:
        diff = git(repo, "diff", "--unified=3", base, final, "--", path, check=False)
        if diff:
            result.append({"path": path, "diff": diff[:max_chars], "truncated": len(diff) > max_chars})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--final", required=True)
    parser.add_argument("--release-file", action="append", default=[])
    parser.add_argument("--max-release-diff-chars", type=int, default=50_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    base_commit = resolve(repo, args.base)
    final_commit = resolve(repo, args.final)
    ancestor = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base_commit, final_commit],
        check=False,
    ).returncode == 0
    paths = release_files(repo, final_commit, args.release_file)
    commit_rows = commits(repo, base_commit, final_commit)
    files = changed_files(repo, base_commit, final_commit)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "repository": str(repo),
        "remote": git(repo, "remote", "get-url", "origin", check=False).strip(),
        "baseRef": args.base,
        "baseCommit": base_commit,
        "finalRef": args.final,
        "finalCommit": final_commit,
        "baseIsAncestor": ancestor,
        "commits": commit_rows,
        "changedFiles": files,
        "counts": {
            "commits": len(commit_rows),
            "productionFiles": sum(row["kind"] == "production" for row in files),
            "testFiles": sum(row["kind"] == "test" for row in files),
        },
        "releaseNoteDiffs": release_diffs(repo, base_commit, final_commit, paths, args.max_release_diff_chars),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": payload["counts"], "baseIsAncestor": ancestor}))
    return 0 if ancestor else 2


if __name__ == "__main__":
    raise SystemExit(main())
