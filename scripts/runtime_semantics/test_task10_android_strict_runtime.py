import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from scripts.runtime_semantics import task10_11_android_strict_common as common
from scripts.runtime_semantics import task10_android_strict_runtime as runtime


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json").read_text())


class Task10AndroidStrictRuntimeTest(unittest.TestCase):
    def test_lock_wait_is_bounded_by_the_overall_cli_deadline(self):
        with self.assertRaisesRegex(TimeoutError, "single overall deadline"):
            with common.wall_deadline(0.01):
                time.sleep(0.1)

    def test_exact_rows_bind_all_nine_canonical_invariants(self):
        rows = []
        for spec in CONTRACT["cases"]:
            raw = {"status": "pass", "observed": spec["expected"],
                   "checkpoints": [{"name": "real-before"}, {"name": "real-after"}],
                   "invariantChecks": [{"description": text, "passed": True, "evidence": {"runtime": True}}
                                       for text in spec.get("invariants", [])]}
            rows.append(common.canonical_row(raw, spec, role="agent"))
        common.validate_rows(rows, CONTRACT)
        self.assertEqual(9, len(rows))
        self.assertTrue(all(row["transitionExecuted"] for row in rows))

    def test_expected_state_and_invariant_mutations_fail_closed(self):
        spec = CONTRACT["cases"][0]
        raw = {"status": "pass", "observed": {},
               "checkpoints": [{"name": "real-before"}, {"name": "real-after"}],
               "invariantChecks": [{"description": text, "passed": True, "evidence": {"runtime": True}}
                                   for text in spec.get("invariants", [])]}
        row = common.canonical_row(raw, spec, role="agent")
        rows = [row] + [{"caseId": item["caseId"], "traceDigest": item["traceDigest"],
                         "status": "fail", "observed": {}, "transitionExecuted": True,
                         "invariantChecks": [{"description": text, "passed": False}
                                             for text in item.get("invariants", [])]}
                        for item in CONTRACT["cases"][1:]]
        with self.assertRaisesRegex(RuntimeError, "passing row"):
            common.validate_rows(rows, CONTRACT)

    def test_snapshot_is_source_parameterized_and_does_not_mutate_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "candidate"
            source.mkdir()
            (source / "Feature.kt").write_text("class Feature\n", encoding="utf-8")
            before = common.source_inventory(source)
            with common.bound_git_snapshot(source, root / "temporary") as (control, provenance):
                self.assertEqual("class Feature", common._run_git(control, "show", ":Feature.kt"))
                self.assertTrue(provenance["sourceParameterized"])
                self.assertFalse(provenance["sourceObserverUsed"])
            self.assertEqual(before, common.source_inventory(source))
            self.assertFalse(control.exists())

    def test_lifetime_adapter_only_accepts_complete_runtime_before_stale_key_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "lifetime.json"
            output.write_text(json.dumps({
                "runtimeCompile": {"status": "passed"},
                "observations": [{"status": "pass", "checkpoints": [
                    {"name": "before_real_send"}, {"name": "actual_sdk_request"},
                    {"name": "dismissed_before_sdk_failure"},
                    {"name": "actual_production_cleanup"}, {"name": "after_sdk_failure"},
                ]}],
            }), encoding="utf-8")
            with mock.patch.object(runtime, "_run_owned", side_effect=StopIteration):
                runtime._run_lifetime(Path("probe.py"), [], output)
            output.write_text(json.dumps({
                "runtimeCompile": {"status": "passed"},
                "observations": [{"status": "pass", "checkpoints": []}],
            }), encoding="utf-8")
            with mock.patch.object(runtime, "_run_owned", side_effect=StopIteration):
                with self.assertRaises(RuntimeError):
                    runtime._run_lifetime(Path("probe.py"), [], output)

    def test_preview_adapter_requires_real_image_transition_before_stale_key_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "preview.json"
            output.write_text(json.dumps({
                "runtimeCompile": {"status": "passed"},
                "observations": [{"key": "image_optimization", "status": "pass",
                                  "checkpoints": [{"name": "before"}, {"name": "after"}]}],
            }), encoding="utf-8")
            with mock.patch.object(runtime, "_run_owned", side_effect=StopIteration):
                runtime._run_preview(Path("probe.py"), [], output)
            output.write_text(json.dumps({
                "runtimeCompile": {"status": "passed"},
                "observations": [{"key": "image_optimization", "status": "not_scored",
                                  "checkpoints": []}],
            }), encoding="utf-8")
            with mock.patch.object(runtime, "_run_owned", side_effect=StopIteration):
                with self.assertRaises(RuntimeError):
                    runtime._run_preview(Path("probe.py"), [], output)

if __name__ == "__main__":
    unittest.main()
