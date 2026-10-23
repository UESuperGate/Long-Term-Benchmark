#!/usr/bin/env python3
"""Validate namespaced benchmark project and task catalogs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ALLOWED_PROJECT_STATUS = {"exploring", "calibrating", "ready"}
REQUIRED_HANDOFFS = {"requirement", "evidence"}
OPTIONAL_HANDOFFS = {"transitions", "observerRules"}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return value


def transition_digest(task_id: str, case: dict[str, Any]) -> str:
    version = case.get("traceSchemaVersion", 1)
    semantic: dict[str, Any] = {
        "taskId": task_id,
        "key": case["key"],
        "given": case["given"],
        "event": case["event"],
        "expected": case["expected"],
    }
    if "setup" in case:
        semantic["setup"] = case["setup"]
    if "setup" in case or version == 2:
        semantic["invariants"] = case["invariants"]
    if version == 2:
        semantic["traceSchemaVersion"] = 2
    encoded = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_transitions(path: Path, task_id: str, prefix: str) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    contract = load(path)
    if contract.get("taskId") != task_id:
        errors.append(f"{prefix}: transition taskId mismatch")
    if contract.get("owner") != "evaluator":
        errors.append(f"{prefix}: transition owner must be evaluator")
    cases = contract.get("cases")
    if not isinstance(cases, list) or len(cases) < 6:
        errors.append(f"{prefix}: at least six canonical transitions are required")
        return errors, contract
    case_ids: set[str] = set()
    keys: set[str] = set()
    has_recovery = False
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"{prefix}: transition {index} must be an object")
            continue
        missing = [key for key in ("caseId", "key", "given", "event", "expected", "invariants") if key not in case]
        if missing:
            errors.append(f"{prefix}: transition {index} missing {', '.join(missing)}")
            continue
        case_id = case["caseId"]
        key = case["key"]
        if case_id in case_ids or key in keys:
            errors.append(f"{prefix}: duplicate caseId or key at {case_id}")
        case_ids.add(case_id)
        keys.add(key)
        words = json.dumps({"key": key, "event": case["event"], "expected": case["expected"]}).lower()
        has_recovery = has_recovery or any(token in words for token in ("fail", "error", "retry", "recover", "offline"))
        try:
            computed = transition_digest(task_id, case)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{prefix}/{case_id}: cannot compute digest: {error}")
            continue
        if case.get("traceDigest") != computed:
            errors.append(f"{prefix}/{case_id}: traceDigest mismatch")
    if not has_recovery:
        errors.append(f"{prefix}: no explicit failure or recovery transition")
    return errors, contract


def validate_task(project_dir: Path, project: dict[str, Any], task_id: str) -> list[str]:
    errors: list[str] = []
    task_dir = project_dir / "tasks" / task_id
    task_path = task_dir / "task.json"
    if not task_path.is_file():
        return [f"{project['projectId']}/{task_id}: missing tasks/{task_id}/task.json"]
    task = load(task_path)
    prefix = f"{project['projectId']}/{task_id}"
    if task.get("taskId") != task_id:
        errors.append(f"{prefix}: taskId differs from catalog entry")
    if task.get("projectId") != project["projectId"]:
        errors.append(f"{prefix}: projectId differs from owning project")
    android = task.get("android", {})
    if android.get("repository") != project["source"]:
        errors.append(f"{prefix}: Android repository differs from project source")
    for key in ("baseRef", "baseCommit", "finalRef", "finalCommit"):
        if not isinstance(android.get(key), str) or not android[key]:
            errors.append(f"{prefix}: android.{key} is required")
    if android.get("baseCommit") == android.get("finalCommit"):
        errors.append(f"{prefix}: base and final commits must differ")
    handoff = task.get("handoff", {})
    missing = sorted(REQUIRED_HANDOFFS - set(handoff))
    if missing:
        errors.append(f"{prefix}: missing handoff entries: {', '.join(missing)}")
    for key in (REQUIRED_HANDOFFS | OPTIONAL_HANDOFFS) & set(handoff):
        if not (task_dir / handoff[key]).is_file():
            errors.append(f"{prefix}: handoff {key} does not exist: {handoff[key]}")
    transition_rel = handoff.get("transitions")
    migration_dir = project_dir / "migrations" / task_id
    if isinstance(transition_rel, str) and (task_dir / transition_rel).is_file():
        transition_errors, contract = validate_transitions(task_dir / transition_rel, task_id, prefix)
        errors.extend(transition_errors)
        migration_contract = migration_dir / "canonical" / "transitions.json"
        if not migration_contract.is_file():
            errors.append(f"{prefix}: missing migration canonical contract")
        elif load(migration_contract) != contract:
            errors.append(f"{prefix}: task and migration canonical contracts differ")
    execution_path = migration_dir / "execution.json"
    if not execution_path.is_file():
        errors.append(f"{prefix}: missing migration execution.json")
    else:
        execution = load(execution_path)
        for platform in ("android", "arkts"):
            config = execution.get(platform)
            # Early benchmark entries published one platform at a time. Validate
            # every declared platform while keeping those immutable manifests
            # readable by the current registry checker.
            if config is None:
                continue
            if not isinstance(config, dict):
                errors.append(f"{prefix}: execution.{platform} must be an object")
                continue
            for role in ("base", "final"):
                relative = config.get(f"{role}Project")
                if not isinstance(relative, str) or not relative:
                    errors.append(f"{prefix}: execution.{platform}.{role}Project is required")
                elif not (migration_dir / relative).is_dir():
                    errors.append(f"{prefix}: execution.{platform}.{role}Project does not exist")
            for command_name in ("buildCommand", "semanticCommand"):
                command = config.get(command_name)
                if command_name == "semanticCommand" and command is None:
                    command = config.get("semanticCommandDeferred")
                if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                    errors.append(f"{prefix}: execution.{platform}.{command_name} must be a non-empty argv list")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = root / "catalog.json"
    registry = load(registry_path)
    projects = registry.get("projects")
    if not isinstance(projects, list) or not projects:
        return ["catalog.json: projects must be a non-empty list"]

    project_ids: set[str] = set()
    sources: set[str] = set()
    for row in projects:
        if not isinstance(row, dict):
            errors.append("catalog.json: every project must be an object")
            continue
        project_id = row.get("projectId")
        source = row.get("source")
        if not isinstance(project_id, str) or not project_id:
            errors.append("catalog.json: projectId is required")
            continue
        if project_id in project_ids:
            errors.append(f"catalog.json: duplicate projectId {project_id}")
        project_ids.add(project_id)
        if not isinstance(source, str) or not source:
            errors.append(f"{project_id}: source is required")
        elif source in sources:
            errors.append(f"catalog.json: duplicate source {source}")
        sources.add(source)

        catalog_rel = row.get("catalog")
        if not isinstance(catalog_rel, str) or not catalog_rel:
            errors.append(f"{project_id}: catalog path is required")
            continue
        catalog_path = root / catalog_rel
        if not catalog_path.is_file():
            errors.append(f"{project_id}: missing catalog {catalog_rel}")
            continue
        project = load(catalog_path)
        project_dir = catalog_path.parent
        if project.get("projectId") != project_id:
            errors.append(f"{project_id}: nested catalog projectId mismatch")
        if project.get("source") != source:
            errors.append(f"{project_id}: nested catalog source mismatch")
        if project.get("status") not in ALLOWED_PROJECT_STATUS:
            errors.append(f"{project_id}: invalid status {project.get('status')!r}")
        accepted = project.get("acceptedTaskIds")
        excluded = project.get("excludedTaskIds")
        if not isinstance(accepted, list) or not all(isinstance(x, str) and x for x in accepted):
            errors.append(f"{project_id}: acceptedTaskIds must be a string list")
            continue
        if len(accepted) != len(set(accepted)):
            errors.append(f"{project_id}: duplicate accepted task id")
        if not isinstance(excluded, list) or not all(isinstance(x, str) and x for x in excluded):
            errors.append(f"{project_id}: excludedTaskIds must be a string list")
            excluded = []
        overlap = set(accepted) & set(excluded)
        if overlap:
            errors.append(f"{project_id}: accepted/excluded overlap: {', '.join(sorted(overlap))}")
        for task_id in accepted:
            errors.extend(validate_task(project_dir, project, task_id))
        if project.get("status") == "ready" and not accepted:
            errors.append(f"{project_id}: ready project must contain accepted tasks")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmark_projects",
    )
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

