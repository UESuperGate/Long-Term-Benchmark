import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import run_runtime_transition_matrix as matrix
from scripts.runtime_semantics import tasks10_11_runtime_evidence as evidence


ACCEPTED = evidence.ROOT / "experiment_results/runtime_transition_20261020/formal_tasks10_11_source_param_v1/public-audit-v6"
AVAILABLE = ((10, "android"), (10, "arkts"), (11, "android"))


def load(task, platform, role):
    control = "final-copy" if role == "agent" else role
    return json.loads((ACCEPTED / f"task{task}/{platform}/{control}.runtime.json").read_text())


def contract(report):
    return json.loads((evidence.ROOT / "benchmark_tasks" / report["taskId"] / "transitions.json").read_text())


class RuntimeEvidenceTest(unittest.TestCase):
    def test_slice_source_scan_retains_actual_snapshot_bytes_and_accepts_native_build_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "before-event.snapshot.json"
            snapshot.write_text(json.dumps({"state": {"state": {"actualRoomId": "!old:example.org"}}}))
            before = snapshot.read_bytes()
            manifest = root / "device-build-report.json"
            manifest.write_text(json.dumps({"runtimeCompile": {"passed": True},
                "production": [{"path": "entry/src/main/ets/features/Room.ets", "sha256": "1"*64}]}))
            sources = evidence.collect_slice_sources(root)
            self.assertEqual(1, len(sources))
            self.assertEqual(before, snapshot.read_bytes())
            self.assertEqual(str(manifest.resolve()), sources[0]["runtimeSlice"]["path"])

    def test_retained_source_bound_reports_pass_additional_evidence_checks(self):
        for task, platform in AVAILABLE:
            for role in ("base", "final", "agent"):
                with self.subTest(task=task, platform=platform, role=role):
                    report = load(task, platform, role)
                    evidence.validate_report(report, contract(report))

    def test_public_matrix_validator_accepts_real_parent_route_without_patching(self):
        for task, platform in AVAILABLE:
            for role in ("base", "final", "agent"):
                report = load(task, platform, role)
                matrix.validate_report(report, contract(report))

    def test_source_bound_base_copy_agent_negative_controls_pass_public_validator(self):
        for platform in ("android", "arkts"):
            report = load(10, platform, "base-copy")
            matrix.validate_report(report, contract(report))
            self.assertEqual("agent", report["role"])
            self.assertEqual(["fail"] * 9, [row["status"] for row in report["semantic"]["cases"]])

    def test_agent_and_final_need_no_entry_policy_route(self):
        for task, platform in AVAILABLE:
            for role in ("final", "agent"):
                report = load(task, platform, role)
                matrix.validate_report(report, contract(report))
                self.assertTrue(report["provenance"]["productionSources"])
                self.assertFalse(report["modelAgentResult"])

    def test_base_policy_rejects_binding_and_positive_control_mutations(self):
        mutations = {
            "role": lambda d: d.update(role="agent"),
            "contract": lambda d: d["semantic"]["cases"][0]["entryFailureEvidence"].update(contractSha256="0"*64),
            "commit": lambda d: d["provenance"].update(commit="0"*40),
            "tree": lambda d: d["provenance"].update(tree="0"*40),
            "inventory": lambda d: d["provenance"]["sourceSnapshot"]["sourceInventory"].update(sha256="0"*64),
            "raw control": lambda d: d["semantic"]["cases"][0]["entryFailureEvidence"]["raw"].update(checkpoints=[]),
            "poststate": lambda d: d["semantic"]["cases"][0].update(observed={}),
            "invariants": lambda d: d["semantic"]["cases"][0].update(invariantChecks=[{"passed":False}]),
            "source hash": lambda d: d["provenance"]["productionSources"][0].update(sha256="0"*64),
        }
        for task in (10, 11):
            original = load(task, "android", "base")
            for label, mutate in mutations.items():
                with self.subTest(task=task, mutation=label):
                    report = copy.deepcopy(original)
                    mutate(report)
                    with self.assertRaises(ValueError):
                        evidence.validate_report(report, contract(original))

    def test_entry_observations_cannot_be_reused(self):
        for task in (10, 11):
            report = load(task, "android", "base")
            row, used = report["semantic"]["cases"][0], set()
            evidence.validate_entry_failure(row, report, used, contract=contract(report))
            with self.assertRaisesRegex(ValueError, "reused"):
                evidence.validate_entry_failure(row, report, used, contract=contract(report))

    def test_arkts_base_requires_real_device_entry_and_uninvented_poststate(self):
        original = load(10, "arkts", "base")
        for label in ("role", "device hash", "poststate"):
            report = copy.deepcopy(original)
            if label == "role":
                report["role"] = "agent"
            elif label == "device hash":
                report["semantic"]["cases"][0]["entryFailureEvidence"]["device"]["sha256"] = "0"*64
            else:
                report["semantic"]["cases"][0]["observed"] = {}
            with self.subTest(mutation=label), self.assertRaises(ValueError):
                evidence.validate_report(report, contract(original))

    def test_archived_android_sources_are_confirmed_execution_subset(self):
        for task in (10, 11):
            report = load(task, "android", "final")
            self.assertEqual("confirmed_executed_compiler_warning_subset",
                             report["provenance"]["productionSourceCoverage"])
            self.assertTrue(all(source["compilerLog"] and source["sourceLine"]
                                for source in report["provenance"]["productionSources"]))

    def test_task11_historical_hash_only_compact_is_not_formal_evidence(self):
        path = ACCEPTED.parent / "handler-accepted-v5/task11/arkts/final.runtime.json"
        report = json.loads(path.read_text())
        with self.assertRaisesRegex(ValueError, "historical hash-only checkpoint is partial"):
            evidence.validate_report(report, contract(report))

    def test_new_task10_device_candidate_retains_readable_actual_snapshots(self):
        report = load(10, "arkts", "agent")
        for row in report["semantic"]["cases"]:
            for point in row["checkpoints"]:
                self.assertTrue(point["state"]["controls"])
                tree = json.loads(evidence.read_record(point["actualSnapshot"]))
                self.assertEqual(evidence._layout_nodes(tree), point["state"]["controls"])

    def test_current_task11_final_public_report_retains_actual_state_not_only_hashes(self):
        path = ACCEPTED.parent / "current-controls-v1/task11/arkts/final/accepted.runtime.json"
        report = json.loads(path.read_text())
        matrix.validate_report(report, contract(report))
        evidence.validate_report(report, contract(report))
        self.assertEqual(12, sum(bool(point.get("actualSnapshot")) for row in report["semantic"]["cases"]
                                 for point in row["checkpoints"]))
        damaged = copy.deepcopy(report)
        damaged["semantic"]["cases"][0]["checkpoints"][0]["state"]["production"] = {}
        with self.assertRaisesRegex(ValueError, "actual snapshot differs"):
            evidence.validate_report(damaged, contract(report))


if __name__ == "__main__":
    unittest.main()
