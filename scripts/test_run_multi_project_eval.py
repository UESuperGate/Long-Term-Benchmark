from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import run_multi_project_eval as runner


class MultiProjectEvalTest(unittest.TestCase):
    def test_public_contract_removes_expected_and_digest(self) -> None:
        public = runner.public_transitions({
            "taskId": "task",
            "cases": [{"caseId": "case", "functionalArea": "flow", "given": {"a": 1},
                       "event": {"name": "go"}, "expected": {"secret": True},
                       "invariants": ["stable"], "traceDigest": "hidden"}],
        })
        encoded = json.dumps(public)
        self.assertNotIn("secret", encoded)
        self.assertNotIn("traceDigest", encoded)
        self.assertEqual(["stable"], public["cases"][0]["invariants"])

    def test_expand_replaces_execution_placeholders(self) -> None:
        command = runner.expand(["tool", "--project", "{project}", "--role={role}"],
                                {"project": Path("/tmp/candidate"), "role": "agent"})
        self.assertEqual(["tool", "--project", "/tmp/candidate", "--role=agent"], command)

    def test_opencode_config_keeps_public_scaffold_read_only(self) -> None:
        candidate = Path("/tmp/candidate")
        config = runner.opencode_config(candidate, ["true"])
        edit = config["permission"]["edit"]
        self.assertEqual("deny", edit[".benchmark-scaffold/**"])
        self.assertEqual("deny", edit[f"{candidate.resolve()}/.benchmark-scaffold/**"])

    def test_runtime_report_requires_real_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text(json.dumps({
                "taskId": "task", "platform": "android", "role": "base",
                "observationMode": "runtime_state_transition",
                "semantic": {"cases": [{"caseId": "case", "status": "fail", "checkpoints": []}]},
            }))
            checked = runner.validate_report(report, "task", "android", "base")
            self.assertFalse(checked["valid"])
            self.assertTrue(any("checkpoints" in error for error in checked["errors"]))

    def test_archive_candidate_keeps_patch_then_candidate_can_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidates" / "task" / "android"
            candidate.mkdir(parents=True)
            source = candidate / "Feature.kt"
            source.write_text("const val value = 1\n")
            subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
            subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-qm", "base"],
                cwd=candidate,
                check=True,
            )
            source.write_text("const val value = 2\n")
            (candidate / "Added.kt").write_text("const val added = true\n")
            output = root / "results"

            runner.archive_candidate(candidate, output, ["Feature.kt", "Added.kt"], "android")
            runner.remove_candidate(candidate, root / "candidates")

            patch = (output / "android-agent.patch").read_text()
            self.assertIn("value = 2", patch)
            self.assertIn("Added.kt", patch)
            self.assertTrue((output / "android-agent-generated-files.json").is_file())
            self.assertFalse(candidate.exists())

    def test_copy_candidate_excludes_evaluator_owned_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            (source / "src").mkdir(parents=True)
            (source / "src/Feature.kt").write_text("class Feature\n")
            for name in ("evaluator", "evaluator-src", "results", "provenance", "verification"):
                (source / name).mkdir()
                (source / name / "secret.json").write_text('{"expected": true}\n')
            destination = root / "candidate"

            runner.copy_candidate(source, destination)

            self.assertTrue((destination / "src/Feature.kt").is_file())
            for name in ("evaluator", "evaluator-src", "results", "provenance", "verification"):
                self.assertFalse((destination / name).exists())

    def test_sanitize_candidate_removes_visible_arkts_probe_wiring(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp)
            entry = candidate / "entry/src/main/ets/entryability/EntryAbility.ets"
            entry.parent.mkdir(parents=True)
            entry.write_text("import { runSemanticCase } from '../evaluator/SemanticProbe';\n// LTB_RUNTIME\n")

            runner.sanitize_candidate(candidate, "arkts")

            text = entry.read_text()
            self.assertNotIn("SemanticProbe", text)
            self.assertNotIn("LTB_RUNTIME", text)
            self.assertIn("loadContent('pages/Index')", text)

    def test_prepare_agent_applies_scaffold_before_clean_room_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "base"
            source.mkdir()
            (source / "Feature.kt").write_text("const val base = true\n")
            task = root / "task"
            task.mkdir()
            (task / "requirement.md").write_text("Implement the feature.\n")
            (task / "integration_contract.md").write_text("# Public integration\n")
            (task / "transitions.json").write_text(json.dumps({"taskId": "task", "cases": []}))
            scaffold = root / "scaffold.py"
            scaffold.write_text(
                "from pathlib import Path\nimport sys\n"
                "Path(sys.argv[1], 'PublicScaffold.kt').write_text('interface PublicScaffold\\n')\n"
            )
            candidate = root / "candidate"
            runner.prepare_agent(
                task,
                source,
                candidate,
                ["true"],
                "android",
                scaffold_command=["python3", str(scaffold), str(candidate)],
                scaffold_cwd=root,
                scaffold_log=root / "scaffold.log",
            )
            committed = subprocess.check_output(
                ["git", "show", "HEAD:PublicScaffold.kt"], cwd=candidate, text=True
            )
            self.assertIn("PublicScaffold", committed)
            contract = subprocess.check_output(
                ["git", "show", "HEAD:_benchmark_inputs/integration_contract.md"], cwd=candidate, text=True
            )
            self.assertIn("Public integration", contract)

    def test_generated_production_audit_rejects_probe_paths_and_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp)
            good = candidate / "src/main/Feature.kt"
            bad = candidate / "src/main/probe/CaseProbe.kt"
            marker = candidate / "src/main/Runtime.kt"
            for path in (good, bad, marker):
                path.parent.mkdir(parents=True, exist_ok=True)
            good.write_text("class Feature\n")
            bad.write_text("class CaseProbe\n")
            marker.write_text("const val value = \"LTB_RUNTIME\"\n")

            clean = runner.audit_generated_production(candidate, ["src/main/Feature.kt"])
            dirty = runner.audit_generated_production(
                candidate,
                ["src/main/Feature.kt", "src/main/probe/CaseProbe.kt", "src/main/Runtime.kt"],
            )

            self.assertTrue(clean["passed"])
            self.assertFalse(dirty["passed"])
            self.assertEqual(2, len(dirty["issues"]))


if __name__ == "__main__":
    unittest.main()
