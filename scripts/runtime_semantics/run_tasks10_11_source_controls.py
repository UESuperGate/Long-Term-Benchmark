#!/usr/bin/env python3
"""Actual Task10/11 strict runtime controls, without full application builds."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from tasks10_11_formal_scorer import candidate_smoke, cleanup_evidence_artifacts, write
from tasks10_11_runtime_evidence import attach_child, record, validate_report


def extract_archive(stream, source):
    source = source.resolve()
    for member in stream.getmembers():
        target = (source / member.name).resolve()
        if not target.is_relative_to(source) or not (member.isfile() or member.isdir() or member.issym()):
            raise ValueError("Unsafe immutable archive member")
        if member.issym() and not (target.parent / member.linkname).resolve().is_relative_to(source):
            raise ValueError("Immutable archive link escapes candidate")
    stream.extractall(source)


def retain_diagnostics(artifacts, target):
    if not artifacts.exists():
        return
    for path in artifacts.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".log"} and not any(
                part in {"work", "build", ".gradle", ".git"} for part in path.relative_to(artifacts).parts):
            retained = target / "failed-runtime-evidence" / path.relative_to(artifacts)
            retained.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=("10_media_upload_quality", "11_room_upgrade_navigation"))
    parser.add_argument("--platform", required=True, choices=("android", "arkts"))
    parser.add_argument("--controls", nargs="+", choices=("base", "final", "base-copy", "final-copy"),
                        default=["base", "final", "base-copy", "final-copy"])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "migrations" / args.task / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    contract = json.loads((ROOT / "benchmark_tasks" / args.task / "transitions.json").read_text())
    reports = []
    for control in args.controls:
        role = "agent" if control.endswith("-copy") else control
        original = control.removesuffix("-copy")
        target = output / control
        target.mkdir(exist_ok=False)
        with tempfile.TemporaryDirectory(prefix="ltb-standalone-") as temporary:
            source = Path(temporary)
            binding = {"manifest": record(manifest_path), "originalRole": original,
                       "candidateCopy": role == "agent", "modelAgentResult": False}
            if args.platform == "android":
                repository = ROOT / "_sources/element-x-android"
                ref, commit = (manifest["android"][original + name] for name in ("Ref", "Commit"))
                actual = subprocess.check_output(["git", "-C", str(repository), "rev-parse", ref + "^{commit}"], text=True).strip()
                if actual != commit:
                    raise ValueError("Immutable Android ref/commit mismatch")
                archive = subprocess.check_output(["git", "-C", str(repository),
                    "-c", "filter.lfs.process=", "-c", "filter.lfs.smudge=cat",
                    "-c", "filter.lfs.required=false", "archive", commit])
                with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                    extract_archive(stream, source)
                binding.update(repository=str(repository), ref=ref, commit=commit,
                               tree=subprocess.check_output(["git", "-C", str(repository), "rev-parse", commit + "^{tree}"], text=True).strip())
            else:
                original_path = ROOT / manifest["arkts"][original + "Path"]
                shutil.copytree(original_path, source, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(".git", "build", ".hvigor", "oh_modules", "node_modules"))
                binding["originalSource"] = str(original_path)
            before = candidate_smoke(source, args.platform)
            write(target / "input.json", {**binding, "standaloneSource": str(source), "sourceInventory": before})
            runtime = HERE / f"task{args.task[:2]}_{args.platform}_strict_runtime.{'py' if args.platform == 'android' else 'cjs'}"
            interpreter = sys.executable if args.platform == "android" else shutil.which("node")
            raw = target / "raw.runtime.json"
            artifacts = target / "temporary"
            command = [interpreter, str(runtime), "--source", str(source), "--role", role,
                       "--platform", args.platform, "--timeout", "3600", "--output", str(raw),
                       "--artifact-root", str(artifacts)]
            entry = {"control": control, "role": role, "modelAgentResult": False,
                     "inputKind": "standalone_" + original + "_copy_sanity" if role == "agent" else "calibration",
                     "command": command, "accepted": False}
            run_start = time.monotonic()
            try:
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=3600)
                (target / "command.log").write_text(result.stdout + result.stderr)
                entry["returncode"] = result.returncode
                if result.returncode or not raw.is_file():
                    raise RuntimeError("Strict runner did not complete; no semantic failure inferred")
                original_report = json.loads(raw.read_text())
                if args.task == "10_media_upload_quality" and args.platform == "arkts":
                    from scripts.runtime_semantics import task10_repository_evidence as repository
                    attach = repository.attach_child if original_report["provenance"].get("runtimeBinding") == repository.BINDING else repository.attach_control
                    report = attach(original_report, contract, artifacts, target / "audit")
                else:
                    report = attach_child(original_report, contract, artifacts, target / "audit")
                report.update(modelAgentResult=False, inputKind=entry["inputKind"])
                validate_report(report, contract)
                from scripts.run_runtime_transition_matrix import validate_report as public_validate
                public_validate(report, contract)
                after = candidate_smoke(source, args.platform)
                if after["inventorySha256"] != before["inventorySha256"]:
                    raise ValueError("Runtime mutated candidate source")
                accepted = target / "accepted.runtime.json"
                write(accepted, report)
                entry.update(accepted=True, report=record(accepted), semantic=report["semantic"],
                             externalApplicationCompile=report.get("compile"), runtimeCompile=report["runtimeCompile"])
                entry["semantic"] = {name: sum(row["status"] == status for row in report["semantic"]["cases"])
                                     for name, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored"))}
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                entry.update(error=f"{type(error).__name__}: {error}",
                             semantic={"passed": 0, "failed": 0, "notScored": len(contract["cases"])})
            finally:
                if not entry["accepted"] and artifacts.exists():
                    retain_diagnostics(artifacts, target)
                cleanup = cleanup_evidence_artifacts(target, artifacts)
                write(target / "cleanup.json", cleanup)
                entry.update(cleanup=record(target / "cleanup.json"), elapsedSeconds=round(time.monotonic() - run_start, 3))
        entry["temporaryInputRemoved"] = not source.exists()
        reports.append(entry)
        write(output / "summary.json", {"taskId": args.task, "platform": args.platform, "reports": reports,
                                       "overallElapsedSeconds": round(time.monotonic() - started, 3),
                                       "fullApplicationBuildStarted": False})
        print(json.dumps({key: entry[key] for key in ("control", "accepted", "semantic", "elapsedSeconds")}), flush=True)
    return 0 if all(entry["accepted"] for entry in reports) else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
