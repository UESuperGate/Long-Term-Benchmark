#!/usr/bin/env python3
"""Focused isolation tests for the OpenCode benchmark runner."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run_new_tasks_opencode_eval_macos.py")
SPEC = importlib.util.spec_from_file_location("new_tasks_runner", SCRIPT)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class IsolationTest(unittest.TestCase):
    def test_android_java_home_uses_jdk17_for_legacy_gradle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            wrapper = candidate / "gradle/wrapper/gradle-wrapper.properties"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10-bin.zip\n")

            self.assertEqual(RUNNER.android_java_home(candidate), RUNNER.JAVA_HOME_17)

    def test_android_java_home_uses_jdk21_for_current_gradle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            wrapper = candidate / "gradle/wrapper/gradle-wrapper.properties"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("distributionUrl=https\\://services.gradle.org/distributions/gradle-8.12.1-bin.zip\n")

            self.assertEqual(RUNNER.android_java_home(candidate), RUNNER.JAVA_HOME_21)

    def test_shell_permissions_have_no_wildcard_allow_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            for platform in ("android", "arkts"):
                shell = RUNNER.opencode_config(platform, candidate)["permission"]["shell"]
                allowed = [pattern for pattern, decision in shell.items() if decision == "allow"]
                self.assertFalse(any("*" in pattern for pattern in allowed))
                self.assertIn(RUNNER.agent_build_command(platform), allowed)

    def test_file_tools_deny_external_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            permission = RUNNER.opencode_config("arkts", candidate)["permission"]
            for tool in ("read", "edit", "glob", "list"):
                rules = permission[tool]
                self.assertEqual(list(rules.items())[0], ("*", "allow"))
                self.assertEqual(list(rules.items())[1], ("/*", "deny"))
                self.assertEqual(list(rules.items())[2], (f"{candidate.resolve()}/*", "allow"))

    def test_candidate_paths_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            log = candidate / "agent.jsonl"
            event = {
                "type": "tool_use",
                "part": {"tool": "read", "state": {"status": "completed", "input": {"path": str(candidate / "src/Main.kt")}}},
            }
            log.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertEqual(RUNNER.audit_agent_log(log, candidate), [])

    def test_external_file_and_shell_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            events = [
                {"type": "tool_use", "part": {"tool": "read", "state": {"status": "completed", "input": {"path": "/tmp/oracle.json"}}}},
                {"type": "tool_use", "part": {"tool": "shell", "state": {"status": "completed", "input": {"command": "ls /Users/example/benchmark"}}}},
                {"type": "tool_use", "part": {"tool": "shell", "state": {"status": "completed", "input": {"command": "find ~/.gradle -name '*.jar'"}}}},
            ]
            log = candidate / "agent.jsonl"
            log.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
            violations = RUNNER.audit_agent_log(log, candidate)
            self.assertEqual(len(violations), 3)

    def test_dev_null_redirection_is_not_an_external_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            event = {
                "type": "tool_use",
                "part": {"tool": "shell", "state": {"status": "completed", "input": {"command": "find . -name '*.kt' 2>/dev/null"}}},
            }
            log = candidate / "agent.jsonl"
            log.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertEqual(RUNNER.audit_agent_log(log, candidate), [])

    def test_denied_external_shell_command_is_not_a_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            event = {
                "type": "tool_use",
                "part": {"tool": "shell", "state": {"status": "error", "input": {"command": "ls /Users/example/benchmark"}, "output": None}},
            }
            log = candidate / "agent.jsonl"
            log.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertEqual(RUNNER.audit_agent_log(log, candidate), [])


if __name__ == "__main__":
    unittest.main()
