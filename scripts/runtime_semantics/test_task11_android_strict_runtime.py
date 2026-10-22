import json
from contextlib import nullcontext
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.runtime_semantics import task10_11_android_strict_common as common
from scripts.runtime_semantics import task11_android_strict_runtime as runtime


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "benchmark_tasks/11_room_upgrade_navigation/transitions.json").read_text())


class Task11AndroidStrictRuntimeTest(unittest.TestCase):
    def test_real_semantic_failure_is_preserved_with_all_invariants(self):
        spec = CONTRACT["cases"][0]
        raw = {"status": "fail", "observed": {"composerVisible": True},
               "checkpoints": [{"name": "actual-before"}, {"name": "actual-after"}],
               "invariantChecks": [{"description": text, "passed": False, "evidence": {"actual": True}}
                                   for text in spec["invariants"]]}
        row = runtime._canonical_runtime_row(raw, spec, "agent")
        self.assertEqual("fail", row["status"])
        self.assertTrue(row["transitionExecuted"])
        self.assertEqual(len(spec["invariants"]), len(row["invariantChecks"]))
        for change in ({"status": "not_scored"}, {"checkpoints": []}, {"invariantChecks": []},
                       {"status": "pass"}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                runtime._canonical_runtime_row({**raw, **change}, spec, "agent")

    def test_semantic_fail_without_actual_mismatch_is_rejected(self):
        spec = CONTRACT["cases"][0]
        raw = {"status": "fail", "observed": spec["expected"],
               "checkpoints": [{"name": "actual-before"}, {"name": "actual-after"}],
               "invariantChecks": [{"description": text, "passed": True} for text in spec["invariants"]]}
        with self.assertRaisesRegex(RuntimeError, "no semantic mismatch"):
            runtime._canonical_runtime_row(raw, spec, "agent")

    def test_probe_failure_never_starts_or_removes_a_native_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(runtime, "bound_git_snapshot", return_value=nullcontext((root, {}))), \
                    mock.patch.object(runtime, "patched_candidate", return_value=nullcontext()), \
                    mock.patch.object(runtime, "probe_entry", side_effect=RuntimeError("entry probe failed")), \
                    mock.patch.object(runtime, "_prepare_native_dependencies") as native, \
                    mock.patch.object(runtime, "_cleanup_native_target") as cleanup:
                with self.assertRaisesRegex(RuntimeError, "entry probe failed"):
                    runtime.execute(root, "agent", root / "result.json", root / "artifacts", 3600)
                native.assert_not_called()
                cleanup.assert_not_called()

    def test_low_disk_guard_does_not_start_rust_and_uses_canonical_lock(self):
        prepare = mock.Mock()
        fake_module = SimpleNamespace(prepare=prepare)
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(runtime.importlib.util, "spec_from_file_location", return_value=fake_spec), \
                    mock.patch.object(runtime.importlib.util, "module_from_spec", return_value=fake_module), \
                    mock.patch.object(runtime, "NATIVE_ROOT", Path(temporary)), \
                    mock.patch.object(runtime.shutil, "disk_usage", return_value=SimpleNamespace(free=7 * 1024**3)), \
                    mock.patch.object(runtime.fcntl, "flock") as flock:
                with self.assertRaisesRegex(RuntimeError, "Environment unavailable"):
                    runtime._prepare_native_dependencies()
                self.assertEqual(runtime.fcntl.LOCK_EX, flock.call_args.args[1])
                prepare.assert_not_called()

    def test_native_dependency_disables_debug_intermediates_and_restores_environment(self):
        observed = {}
        def prepare():
            observed.update({key: runtime.os.environ[key] for key in (
                "CARGO_PROFILE_DEV_DEBUG", "CARGO_INCREMENTAL", "CARGO_BUILD_JOBS")})
            return {"immutableDependency": True}
        fake_module = SimpleNamespace(prepare=prepare)
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
        before = dict(runtime.os.environ)
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(runtime.importlib.util, "spec_from_file_location", return_value=fake_spec), \
                    mock.patch.object(runtime.importlib.util, "module_from_spec", return_value=fake_module), \
                    mock.patch.object(runtime, "NATIVE_ROOT", Path(temporary)), \
                    mock.patch.object(runtime.shutil, "disk_usage", return_value=SimpleNamespace(free=20 * 1024**3)), \
                    mock.patch.object(runtime.fcntl, "flock"):
                result = runtime._prepare_native_dependencies()
        self.assertEqual({"CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_INCREMENTAL": "0", "CARGO_BUILD_JOBS": "2"}, observed)
        self.assertEqual(observed, result["preparationEnvironment"])
        self.assertEqual(before, dict(runtime.os.environ))

    def test_base_requires_reachable_positive_control(self):
        spec = CONTRACT["cases"][0]
        raw = {"status": "fail", "observed": {"commonRoomVisible": True},
               "checkpoints": [{"name": "common_start"}, {"name": "post_event"}]}
        row = common.base_entry_failure(raw, spec, role="base")
        self.assertFalse(row["transitionExecuted"])
        self.assertTrue(row["entryFailureEvidence"]["positiveControlCompleted"])
        self.assertEqual([False], [item["passed"] for item in row["invariantChecks"]])

    def test_empty_or_unreachable_base_evidence_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "positive control"):
            common.base_entry_failure({"status": "fail", "observed": {}, "checkpoints": []},
                                      CONTRACT["cases"][0], role="base")

    def test_all_six_final_rows_require_exact_state_and_invariants(self):
        rows = []
        for spec in CONTRACT["cases"]:
            rows.append(common.canonical_row({
                "status": "pass", "observed": spec["expected"],
                "checkpoints": [{"name": "runtime-before"}, {"name": "runtime-after"}],
                "invariantChecks": [{"description": text, "passed": True, "evidence": {"runtime": True}}
                                    for text in spec.get("invariants", [])],
            }, spec, role="agent"))
        common.validate_rows(rows, CONTRACT)
        rows[-1]["invariantChecks"][0]["passed"] = False
        with self.assertRaisesRegex(RuntimeError, "passing row"):
            common.validate_rows(rows, CONTRACT)

    def test_native_target_is_hashed_then_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "target/debug/libuniffi_wysiwyg_composer.dylib"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"immutable-native-runtime")
            cleanup = runtime._cleanup_native_target(root)
            self.assertEqual(1, len(cleanup["binaryHashes"]))
            self.assertTrue(cleanup["targetRemoved"])
            self.assertFalse((root / "target").exists())

    def test_native_cleanup_persists_hash_manifest_before_deleting_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "target/debug/lib.dylib"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"runtime dependency")
            manifest = root / "native-cleanup.json"
            runtime._cleanup_native_target(root, manifest)
            evidence = json.loads(manifest.read_text())
            self.assertEqual("hash_recorded_before_delete", evidence["stage"])
            self.assertEqual(str(library.resolve()), evidence["binaryHashes"][0]["path"])
            self.assertFalse(library.exists())

    def test_rendered_banner_accepts_only_exact_pass_before_navigation_boundary_ns(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "rendered.json"
            spec = next(item for item in CONTRACT["cases"] if item["key"] == "predecessor_banner")
            output.write_text(json.dumps({
                "runtimeCompile": {"status": "passed"},
                "semantic": {"cases": [{"key": "predecessor_banner", "status": "pass",
                                          "observed": spec["expected"],
                                          "invariantChecks": [{"description": text, "passed": True}
                                                              for text in spec["invariants"]],
                                          "checkpoints": [{"name": "before"}, {"name": "after"}]}]},
            }), encoding="utf-8")
            error = RuntimeError("run.py returned 1")
            with mock.patch.object(runtime, "_run_owned", side_effect=error):
                runtime._run_rendered_banner(Path("run.py"), [], output)
            output.write_text(json.dumps({
                "runtimeCompile": {"status": "passed"},
                "semantic": {"cases": [{"key": "predecessor_banner", "status": "not_scored",
                                          "checkpoints": []}]},
            }), encoding="utf-8")
            with mock.patch.object(runtime, "_run_owned", side_effect=error):
                with self.assertRaises(RuntimeError):
                    runtime._run_rendered_banner(Path("run.py"), [], output)

    def test_rendered_banner_keeps_a_complete_real_semantic_failure(self):
        spec = next(item for item in CONTRACT["cases"] if item["key"] == "predecessor_banner")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "rendered.json"
            output.write_text(json.dumps({"runtimeCompile": {"status": "passed"}, "semantic": {"cases": [{
                "key": "predecessor_banner", "status": "fail", "observed": {},
                "invariantChecks": [{"description": text, "passed": False} for text in spec["invariants"]],
                "checkpoints": [{"name": "actual-before"}, {"name": "actual-after"}]}]}}))
            with mock.patch.object(runtime, "_run_owned", side_effect=RuntimeError("run.py returned 1")):
                runtime._run_rendered_banner(Path("run.py"), [], output)
            self.assertEqual("fail", json.loads(output.read_text())["semantic"]["cases"][0]["status"])


if __name__ == "__main__":
    unittest.main()
