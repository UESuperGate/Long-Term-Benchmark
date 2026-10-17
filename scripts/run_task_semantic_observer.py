#!/usr/bin/env python3
"""Score one extracted task with its evaluator-owned conformance rules."""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANDROID_REPO = ROOT / "_sources/element-x-android"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_comments(text: str) -> str:
    """Remove source comments without corrupting string literals such as file:// URIs."""
    output: list[str] = []
    index = 0
    quote = ""
    escaped = False
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if quote:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            output.append(char)
            index += 1
            continue
        if char == "/" and following == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and following == "*":
            index += 2
            while index + 1 < len(text) and text[index : index + 2] != "*/":
                if text[index] in "\r\n":
                    output.append(text[index])
                index += 1
            index = min(index + 2, len(text))
            continue
        output.append(char)
        index += 1
    return "".join(output)


def android_tag_sources(ref: str, roots: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    names = subprocess.check_output(
        ["git", "-C", str(ANDROID_REPO), "ls-tree", "-r", "--name-only", ref],
        text=True,
    ).splitlines()
    existing_roots = [root for root in roots if any(name.startswith(root.rstrip("/") + "/") or name == root for name in names)]
    if not existing_roots:
        return result
    archive = subprocess.check_output(["git", "-C", str(ANDROID_REPO), "archive", "--format=tar", ref, *existing_roots])
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
        for member in stream.getmembers():
            if not member.isfile() or Path(member.name).suffix not in {".kt", ".kts", ".java", ".xml"}:
                continue
            extracted = stream.extractfile(member)
            if extracted is not None:
                result[member.name] = strip_comments(extracted.read().decode("utf-8", errors="replace"))
    return result


def directory_sources(root: Path, roots: list[str], suffixes: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    resolved_root = root.resolve()
    for source_root in roots:
        candidate = (resolved_root / source_root).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            continue
        if not candidate.exists():
            continue
        paths = [candidate] if candidate.is_file() else candidate.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if {"build", ".gradle", ".hvigor", "oh_modules", "node_modules"}.intersection(path.parts):
                continue
            result[str(path.relative_to(resolved_root))] = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    return result


def agent_source_roots(configured_roots: list[str], changed_files: list[str], suffixes: set[str]) -> list[str]:
    """Include generated production files even when an agent chooses a valid new module layout."""
    roots = list(configured_roots)
    seen = set(roots)
    for changed_file in changed_files:
        path = Path(changed_file)
        if path.is_absolute() or ".." in path.parts or path.suffix not in suffixes:
            continue
        normalized = path.as_posix()
        if normalized not in seen:
            roots.append(normalized)
            seen.add(normalized)
    return roots


def match_option(option: dict[str, Any], sources: dict[str, str]) -> tuple[bool, str]:
    path_pattern = str(option.get("path", ""))
    patterns = [str(pattern) for pattern in option.get("patterns", [])]
    forbidden = [str(pattern) for pattern in option.get("forbid", [])]
    for path, source in sources.items():
        if not re.search(path_pattern, path):
            continue
        missing = [pattern for pattern in patterns if not re.search(pattern, source, flags=re.MULTILINE)]
        present_forbidden = [pattern for pattern in forbidden if re.search(pattern, source, flags=re.MULTILINE)]
        if not missing and not present_forbidden:
            return True, path
    return False, path_pattern


def score_case(case: dict[str, Any], clauses: list[dict[str, Any]], sources: dict[str, str]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    evidence: list[str] = []
    for index, clause in enumerate(clauses):
        options = clause.get("options", [])
        matched = [match_option(option, sources) for option in options]
        winner = next((path for passed, path in matched if passed), None)
        if winner is None:
            failures.append({"clause": index + 1, "options": [path for _, path in matched]})
        else:
            evidence.append(winner)
    passed = not failures
    return {
        "caseId": case["caseId"],
        "traceDigest": case["traceDigest"],
        "status": "pass" if passed else "fail",
        "evidencePaths": sorted(set(evidence)),
        "failedClauses": failures,
    }


def boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "passed", "pass"}:
        return True
    if normalized in {"0", "false", "no", "failed", "fail"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean: {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--platform", required=True, choices=("android", "arkts"))
    parser.add_argument("--role", required=True, choices=("base", "final", "agent"))
    parser.add_argument("--source", type=Path, help="Required for agent; optional override for ArkTS base/final")
    parser.add_argument("--code-generated", type=boolean, default=False)
    parser.add_argument("--changed-production-file", action="append", default=[])
    parser.add_argument("--compile-passed", type=boolean, default=True)
    parser.add_argument("--compile-command", default="not recorded")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    task_dir = ROOT / "benchmark_tasks" / args.task
    task = load(task_dir / "task.json")
    contract = load(task_dir / "transitions.json")
    rules = load(task_dir / "observer_rules.json")
    if task.get("taskId") != args.task or contract.get("taskId") != args.task or rules.get("taskId") != args.task:
        raise SystemExit("task IDs differ across task, contract, and rules")

    platform_rules = rules[args.platform]
    roots = [str(root) for root in platform_rules["roots"]]
    if args.platform == "android" and args.role in {"base", "final"} and args.source is None:
        ref = task["android"]["baseRef" if args.role == "base" else "finalRef"]
        sources = android_tag_sources(ref, roots)
        target = f"git:{ref}"
    else:
        source = args.source
        if source is None:
            key = "basePath" if args.role == "base" else "finalPath"
            source = ROOT / task["arkts"][key]
        source = source.expanduser().resolve()
        suffixes = {".kt", ".kts", ".java", ".xml"} if args.platform == "android" else {".ets", ".ts", ".json5"}
        if args.role == "agent":
            roots = agent_source_roots(roots, args.changed_production_file, suffixes)
        sources = directory_sources(source, roots, suffixes)
        target = str(source)

    indexed_rules = platform_rules["cases"]
    contract_ids = [case["caseId"] for case in contract["cases"]]
    if set(indexed_rules) != set(contract_ids):
        missing = sorted(set(contract_ids) - set(indexed_rules))
        extra = sorted(set(indexed_rules) - set(contract_ids))
        raise SystemExit(f"rule/contract case mismatch missing={missing} extra={extra}")
    if sources:
        rows = [score_case(case, indexed_rules[case["caseId"]], sources) for case in contract["cases"]]
        adapter_status = "ready"
        adapter_reason = None
    else:
        rows = [
            {
                "caseId": case["caseId"],
                "traceDigest": case["traceDigest"],
                "status": "not_scored",
                "evidencePaths": [],
                "failedClauses": [],
            }
            for case in contract["cases"]
        ]
        adapter_status = "failed"
        adapter_reason = "no production source files were found in configured or changed-file roots"
    counts = Counter(row["status"] for row in rows)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "taskId": args.task,
        "platform": args.platform,
        "role": args.role,
        "target": target,
        "observationMode": "source_transition_conformance",
        "codeGeneration": {"passed": args.code_generated, "changedProductionFiles": args.changed_production_file},
        "compile": {"passed": args.compile_passed, "command": args.compile_command},
        "semantic": {
            "passed": counts["pass"],
            "failed": counts["fail"],
            "total": len(rows),
            "cases": rows,
        },
        "diagnostics": {
            "adapter": adapter_status,
            "adapterReason": adapter_reason,
            "transport": "ready",
            "sourceFilesScanned": len(sources),
            "sourceRoots": roots,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "taskId": args.task, "platform": args.platform, "role": args.role, "semantic": payload["semantic"] | {"cases": len(rows)}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
