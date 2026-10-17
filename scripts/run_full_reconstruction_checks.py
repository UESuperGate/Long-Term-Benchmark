#!/usr/bin/env python3
"""Run reproducible build and parity gates for the full Harmony reconstruction."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "elementx_harmony_full"
VERIFICATION = PROJECT / "verification"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_step(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> dict:
    started_at = now()
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "started_at": started_at,
        "finished_at": now(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "exit_code": completed.returncode,
        "output": completed.stdout,
    }


def markdown(report: dict) -> str:
    lines = [
        "# Full Reconstruction Check Run",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Build status: **{report['build_status']}**",
        f"- Parity status: **{report['parity_status']}**",
        "",
        "| Step | Exit | Duration (s) |",
        "|---|---:|---:|",
    ]
    for step in report["steps"]:
        lines.append(f"| {step['name']} | {step['exit_code']} | {step['duration_seconds']:.3f} |")
    lines.extend(["", "## Interpretation", ""])
    if report["build_status"] != "PASS":
        lines.append("The reconstruction cannot currently be built or checked reproducibly.")
    elif report["parity_status"] != "PASS":
        lines.append("The project builds, but the strict full-client parity gate still has blocking gaps.")
    else:
        lines.append("The reproducible build and strict full-client parity gates both pass.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="fail when parity is incomplete")
    parser.add_argument("--skip-native", action="store_true")
    parser.add_argument("--skip-hap", action="store_true")
    parser.add_argument("--skip-test-hap", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    env.setdefault("DEVECO_HOME", "/Applications/DevEco-Studio.app/Contents")
    env.setdefault("DEVECO_SDK_HOME", str(Path.home() / "Library" / "OpenHarmony" / "Sdk"))
    env.setdefault("OHOS_BASE_SDK_HOME", env["DEVECO_SDK_HOME"])
    env.setdefault("OHOS_SDK_ROOT", str(Path.home() / "Library" / "OpenHarmony" / "Sdk" / "23"))
    env.setdefault("JAVA_HOME", "/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home")
    tool_paths = [
        "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin",
        "/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin",
        "/Applications/DevEco-Studio.app/Contents/tools/node/bin",
    ]
    env["PATH"] = os.pathsep.join(tool_paths + [env.get("PATH", "")])

    steps: list[dict] = []
    steps.append(
        run_step(
            "Android production-module inventory",
            ["python3", "scripts/generate_full_migration_inventory.py"],
            ROOT,
            env,
        )
    )
    steps.append(
        run_step(
            "Reviewed partial migration evidence",
            ["python3", "scripts/record_reconstruction_progress.py"],
            ROOT,
            env,
        )
    )
    steps.append(
        run_step(
            "Reconstruction harness unit tests",
            [
                "python3",
                "-m",
                "unittest",
                "scripts.test_generate_full_migration_inventory",
                "scripts.test_full_reconstruction_audit",
            ],
            ROOT,
            env,
        )
    )
    if not args.skip_native:
        steps.append(
            run_step(
                "Matrix bridge host and OHOS build",
                ["bash", "scripts/build_matrix_bridge_macos.sh"],
                ROOT,
                env,
            )
        )
    if not args.skip_hap:
        steps.append(run_step("OHPM install", ["ohpm", "install"], PROJECT, env))
        steps.append(
            run_step(
                "OpenHarmony SDK 23 HAP build",
                ["hvigorw", "assembleHap", "--no-daemon"],
                PROJECT,
                env,
            )
        )
    if not args.skip_test_hap:
        steps.append(
            run_step(
                "OpenHarmony SDK 23 ohosTest HAP compile",
                [
                    "hvigorw",
                    "assembleHap",
                    "--no-daemon",
                    "--mode",
                    "module",
                    "-p",
                    "module=entry@ohosTest",
                    "-p",
                    "product=default",
                    "-p",
                    "buildMode=debug",
                ],
                PROJECT,
                env,
            )
        )
    steps.append(
        run_step(
            "Strict full reconstruction audit",
            ["python3", "scripts/audit_full_reconstruction.py", "--allow-incomplete"],
            ROOT,
            env,
        )
    )

    build_steps = [step for step in steps if step["name"] != "Strict full reconstruction audit"]
    build_status = "PASS" if all(step["exit_code"] == 0 for step in build_steps) else "FAIL"
    audit = {}
    audit_path = VERIFICATION / "full-reconstruction-audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    parity_status = str(audit.get("status", "FAIL"))
    report = {
        "generated_at": now(),
        "build_status": build_status,
        "parity_status": parity_status,
        "strict": args.strict,
        "steps": steps,
    }
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION / "full-reconstruction-check-run.json"
    markdown_path = VERIFICATION / "full-reconstruction-check-run.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    if build_status != "PASS":
        return 1
    if args.strict and parity_status != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
