#!/usr/bin/env python3
"""Run hidden agent adapters against untouched clean-room bases."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import run_multi_project_eval as runner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--build-timeout", type=int, default=3600)
    parser.add_argument("--platform", action="append", choices=("android", "arkts"))
    parser.add_argument("--min-free-bytes", type=int, default=runner.MIN_FREE_BYTES)
    args = parser.parse_args()

    if args.min_free_bytes <= 0:
        raise ValueError("--min-free-bytes must be positive")
    runner.MIN_FREE_BYTES = args.min_free_bytes

    project_dir, catalog = runner.project_entry(args.project)
    run_root = runner.ROOT / "eval_runs" / args.run_id / args.project
    candidate_stop = runner.ROOT.parent / f"{runner.ROOT.name}-multi-project-eval" / args.run_id
    candidate_root = candidate_stop / args.project
    summary = {"projectId": args.project, "classification": "no_change_control", "tasks": {}}
    overall_ok = True

    for task_id in catalog["acceptedTaskIds"]:
        task_dir = project_dir / "tasks" / task_id
        migration = project_dir / "migrations" / task_id
        execution = runner.load(migration / "execution.json")
        output = run_root / task_id
        output.mkdir(parents=True, exist_ok=True)
        task_result = {}
        for platform in (args.platform or ["android", "arkts"]):
            config = execution[platform]
            candidate = candidate_root / task_id / platform
            values = {
                "project": candidate,
                "candidate": candidate,
                "role": "agent",
                "output": output / f"{platform}-agent.json",
                "migration": migration,
            }
            try:
                visible = runner.expand(config.get("agentVisibleBuildCommand", config["buildCommand"]), values)
                scaffold = runner.expand(config["agentScaffoldCommand"], values) if config.get("agentScaffoldCommand") else None
                runner.prepare_agent(
                    task_dir,
                    (migration / config["baseProject"]).resolve(),
                    candidate,
                    visible,
                    platform,
                    scaffold_command=scaffold,
                    scaffold_cwd=migration,
                    scaffold_log=output / f"{platform}-control-scaffold.log",
                    scaffold_timeout=args.build_timeout,
                    scaffold_env=config.get("environment"),
                )
                preflight = runner.run_logged(
                    visible,
                    candidate,
                    output / f"{platform}-control-base-preflight.log",
                    args.build_timeout,
                    config.get("environment"),
                )
                if preflight != 0:
                    raise RuntimeError(f"clean base preflight failed with exit {preflight}")
                runner.cleanup_builds(candidate, output / f"{platform}-control-preflight-artifacts.json")
                prepare = runner.run_logged(
                    runner.expand(config["agentPrepareCommand"], values),
                    migration,
                    output / f"{platform}-control-prepare.log",
                    args.build_timeout,
                    config.get("environment"),
                )
                if prepare != 0:
                    raise RuntimeError(f"hidden adapter preparation failed with exit {prepare}")
                hidden_config = dict(config)
                hidden_config["buildCommand"] = config.get("agentBuildCommand", config["buildCommand"])
                hidden_config["semanticCommand"] = config.get("agentSemanticCommand", config["semanticCommand"])
                result = runner.execute_role(
                    migration,
                    task_id,
                    platform,
                    "agent",
                    candidate,
                    hidden_config,
                    output,
                    args.build_timeout,
                    [],
                )
                report_path = output / f"{platform}-agent.json"
                statuses = []
                if report_path.is_file():
                    report = runner.load(report_path)
                    report["control"] = "untouched_clean_room_base"
                    statuses = [case.get("status") for case in report.get("semantic", {}).get("cases", [])]
                    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                control_valid = result["validation"]["valid"] and bool(statuses) and all(status == "fail" for status in statuses)
                result.update({"basePreflightExit": preflight, "prepareExit": prepare, "controlValid": control_valid})
                task_result[platform] = result
                overall_ok = overall_ok and control_valid
            except Exception as error:
                task_result[platform] = {"controlValid": False, "error": str(error)}
                overall_ok = False
            finally:
                runner.remove_candidate(candidate, candidate_stop)
        summary["tasks"][task_id] = task_result

    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runRoot": str(run_root), "valid": overall_ok}))
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
