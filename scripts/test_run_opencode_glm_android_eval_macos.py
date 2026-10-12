#!/usr/bin/env python3
"""Regression tests for the Android OpenCode benchmark runner."""

from __future__ import annotations

import unittest
import json
import subprocess
import tempfile
from pathlib import Path

from run_opencode_glm_android_eval_macos import (
    TASKS,
    is_generated_product_code,
    opencode_config,
    prompt_for,
    provider_failure_from_log,
    render_android_spec,
    state_test_binding_changed,
)


class AndroidBenchmarkRunnerTest(unittest.TestCase):
    def test_android_specs_have_no_arkts_instructions(self) -> None:
        for task in TASKS:
            spec = render_android_spec(task)
            self.assertNotIn("ArkTS", spec, task["id"])
            self.assertIn("Android", spec, task["id"])

    def test_user_status_requires_android_production_changes(self) -> None:
        spec = render_android_spec(TASKS[0])
        self.assertIn("必须修改 Android production source", spec)
        self.assertNotIn("不改动 Android production source", spec)

    def test_code_generation_excludes_benchmark_scaffold(self) -> None:
        self.assertTrue(is_generated_product_code("features/foo/src/main/kotlin/Foo.kt"))
        self.assertTrue(is_generated_product_code("app/src/main/java/App.java"))
        self.assertFalse(is_generated_product_code("app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt"))
        self.assertFalse(is_generated_product_code("_benchmark_inputs/task.yaml"))
        self.assertFalse(is_generated_product_code("opencode.json"))

    def test_state_binding_requires_a_candidate_change(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            candidate = Path(value)
            binding = candidate / "app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt"
            binding.parent.mkdir(parents=True)
            binding.write_text("placeholder\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
            subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Benchmark Test",
                    "-c",
                    "user.email=benchmark@example.invalid",
                    "commit",
                    "-qm",
                    "baseline",
                ],
                cwd=candidate,
                check=True,
            )
            self.assertFalse(state_test_binding_changed(candidate))
            binding.write_text("implemented\n", encoding="utf-8")
            self.assertTrue(state_test_binding_changed(candidate))

    def test_provider_quota_error_invalidates_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            log = Path(value) / "agent.jsonl"
            log.write_text(
                json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "provider.quota",
                            "status": 402,
                            "message": "subscription request limit exhausted",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(provider_failure_from_log(log)["status"], 402)

    def test_agent_is_confined_to_candidate_workspace(self) -> None:
        config = opencode_config()
        permissions = config["permission"]
        self.assertEqual(permissions["*"], "deny")
        self.assertEqual(permissions["external_directory"], "deny")
        self.assertEqual(permissions["bash"]["*"], "deny")
        self.assertEqual(permissions["bash"]["./gradlew :app:assembleGplayDebug --no-daemon"], "allow")
        self.assertEqual(permissions["bash"]["git diff *"], "allow")
        self.assertEqual(permissions["shell"], permissions["bash"])
        self.assertNotIn("curl *", permissions["bash"])
        self.assertNotIn("find *", permissions["bash"])
        self.assertEqual(permissions["task"], "allow")
        for tool in ("read", "edit", "glob", "grep", "list"):
            self.assertEqual(permissions[tool], "allow")
        self.assertEqual(permissions["webfetch"], "deny")
        self.assertEqual(permissions["websearch"], "deny")
        self.assertEqual(config["agent"]["explore"]["steps"], 4)
        self.assertIn("under 2,000 tokens", config["agent"]["explore"]["prompt"])

    def test_prompt_excludes_external_build_inputs(self) -> None:
        task = TASKS[0] | {"spec": "android-spec.md"}
        prompt = prompt_for(task, Path("/candidate"), Path("/candidate/_benchmark_inputs"))
        self.assertIn("complete readable workspace", prompt)
        self.assertIn("Project-local shell access is limited", prompt)
        self.assertIn("Subagents are allowed", prompt)
        self.assertIn("at most one subagent", prompt)
        self.assertIn("Subagents are allowed but optional", prompt)
        self.assertIn("inspect no more than 5 production source files before editing", prompt)
        self.assertIn("allowed but optional after the first production edit", prompt)
        self.assertIn("Expected states and UI assertions are evaluator-private", prompt)
        self.assertNotIn("very next implementation step", prompt)
        self.assertIn("each write/edit tool payload under 4,000 tokens", prompt)
        self.assertIn("Do not add or modify debug-only benchmark harnesses", prompt)
        self.assertIn("Do not add case-id switches", prompt)
        self.assertNotIn("semantic_failures.json", prompt)
        self.assertIn("Do not use browser", prompt)
        self.assertIn("Run `./gradlew", prompt)


if __name__ == "__main__":
    unittest.main()
