import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.runtime_semantics import task10_repository_prefix_policy as policy

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json").read_text())
SPEC = next(spec for spec in CONTRACT["cases"] if spec["caseId"] == policy.CASE)


def fixture():
    nonce = "a" * 32
    source = "/actual-app-cache/input.mp4"
    calls = [
        {"owner": "native_fs", "method": "original_input_established", "path": source, "exists": True, "bytes": 50000000},
        {"owner": "gateway", "method": "sendAsync", "request": {"caption": "demo", "quality": {"videoQuality": "standard"}, "attachments": [{"uri": source}]}},
        {"owner": "gateway", "method": "actual_stage_before_async_completion", "files": [{"path": source + ".standard.upload", "available": True, "exists": False}]},
        {"owner": "gateway", "method": "sendAsync_completed", "result": {"succeeded": False}},
    ]
    state = {"available": True, "view": {"caption": "demo", "plan": {"selectedPreset": "standard"},
        "previewVisible": True, "sendState": "failure"}, "calls": calls}
    controls = {key: {"id": "random-" + key, "present": True, "visible": True, "enabled": True} for key in ("caption", "send")}
    point = lambda label: {"label": label, "state": {"state": copy.deepcopy(state), "controls": copy.deepcopy(controls),
        "windowId": 42, "routeName": "pages/Index"}}
    native = {"taskId": "10_media_upload_quality", "role": "agent", "caseId": policy.CASE, "traceDigest": SPEC["traceDigest"],
        "nativeBridge": {"capabilities": {"execution": {"nonce": nonce}}},
        "productionSources": [{"path": "entry/src/main/ets/features/Renamed.ets", "sha256": "1"*64}],
        "checkpoints": [point("prefix:caption-and-quality"), point("after:event")],
        "calls": [{"module": "ArkUI", "observation": {"method": "Task11.uiAction", "kind": "input", "value": "demo", "target": {"id": "random-caption"}}},
                  {"module": "ArkUI", "observation": {"method": "Task11.uiAction", "kind": "click", "target": {"id": "random-send", "visible": True, "enabled": True}}}]}
    execution = {"taskId": native["taskId"], "role": "agent", "caseId": policy.CASE, "transportCompleted": True,
        "candidateAbsentBeforeInstall": True, "productionUnchanged": True, "cleanup": {"ownedAppUninstalled": True},
        "executionNonce": nonce, "deviceUserId": "100", "rowArtifact": {
            "sha256": "1"*64, "bytes": 100, "remote": "/data/app/el2/100/base/test.bundle/cache/ltb-native-result_123.json",
            "processLogMarker": {"taskId": native["taskId"], "role": "agent", "caseId": policy.CASE,
                "name": "ltb-native-result_123.json", "bytes": 100, "characters": 100, "executionNonce": nonce}}}
    return native, execution


def row_receipt(execution, native_path):
    execution["rowArtifact"].update(policy.evidence.record(native_path))
    marker = execution["rowArtifact"]["processLogMarker"]
    marker["bytes"] = native_path.stat().st_size
    marker["characters"] = len(native_path.read_text().encode("utf-16-le")) // 2


class PreparedPrefixPolicyTest(unittest.TestCase):
    def test_direct_script_import_without_repository_root_or_pythonpath(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"PYTHONPATH", "PYTHONHOME"}}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(Path(policy.__file__).resolve())],
                                    cwd=directory, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_script_style_package_import_has_no_validator_sys_path_side_effect(self):
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
            "from runtime_semantics import task10_repository_prefix_policy as module; "
            "assert module.evidence.__name__ == 'runtime_semantics.tasks10_11_runtime_evidence'; "
            f"assert {str(ROOT)!r} not in sys.path; "
            "assert callable(module.validate_entry_failure)"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", "-c", code], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_nonce_window_and_row_marker_mutations_are_rejected(self):
        mutations = {
            "missing_native_nonce": lambda n, e: n["nativeBridge"]["capabilities"]["execution"].clear(),
            "other_native_nonce": lambda n, e: n["nativeBridge"]["capabilities"]["execution"].update(nonce="b"*32),
            "missing_transport_nonce": lambda n, e: e.pop("executionNonce"),
            "malformed_nonce": lambda n, e: e.update(executionNonce="a"),
            "different_marker_nonce": lambda n, e: e["rowArtifact"]["processLogMarker"].update(executionNonce="b"*32),
            "different_marker_role": lambda n, e: e["rowArtifact"]["processLogMarker"].update(role="base"),
            "different_marker_case": lambda n, e: e["rowArtifact"]["processLogMarker"].update(caseId="other"),
            "missing_marker": lambda n, e: e["rowArtifact"].pop("processLogMarker"),
            "other_remote_filename": lambda n, e: e["rowArtifact"].update(remote="/other.json"),
            "nonpositive_marker_bytes": lambda n, e: e["rowArtifact"].update(bytes=0),
            "different_marker_bytes": lambda n, e: e["rowArtifact"]["processLogMarker"].update(bytes=101),
            "bool_window": lambda n, e: [p["state"].update(windowId=True) for p in n["checkpoints"]],
            "both_missing_window": lambda n, e: [p["state"].pop("windowId") for p in n["checkpoints"]],
            "both_string_window": lambda n, e: [p["state"].update(windowId="42") for p in n["checkpoints"]],
            "both_zero_window": lambda n, e: [p["state"].update(windowId=0) for p in n["checkpoints"]],
            "nonintegral_window": lambda n, e: [p["state"].update(windowId=42.5) for p in n["checkpoints"]],
            "other_window": lambda n, e: n["checkpoints"][1]["state"].update(windowId=43),
        }
        for name, mutate in mutations.items():
            native, execution = fixture()
            mutate(native, execution)
            with self.subTest(mutation=name), self.assertRaises(ValueError):
                policy.verify_native_prefix(native, execution)

    def test_state_and_real_input_receipts_not_private_selectors_decide_prefix(self):
        native, execution = fixture()
        result = policy.verify_native_prefix(native, execution)
        self.assertFalse(result["canonicalPreparedGivenReached"])
        self.assertFalse(result["originalAssertionsEvaluated"])

    def test_missing_givens_file_errors_fake_events_and_fabricated_prepared_media_are_rejected(self):
        mutations = [
            lambda n, e: n["checkpoints"][0]["state"]["state"]["view"].update(caption="wrong"),
            lambda n, e: n["checkpoints"][0]["state"]["controls"]["send"].update(enabled=False),
            lambda n, e: n["checkpoints"][1]["state"]["state"]["calls"][0].update(exists=False),
            lambda n, e: n["checkpoints"][1]["state"]["state"]["calls"][2]["files"][0].update(available=False),
            lambda n, e: n["checkpoints"][1]["state"]["state"]["calls"][2]["files"][0].update(exists=True),
            lambda n, e: n.update(calls=[]),
            lambda n, e: e.update(candidateAbsentBeforeInstall=False),
            lambda n, e: e.update(role="base"),
        ]
        for mutate in mutations:
            native, execution = fixture()
            mutate(native, execution)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                policy.verify_native_prefix(native, execution)

    def test_source_bound_policy_rejects_role_contract_inventory_and_reuse_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native, execution = fixture()
            native_path = root / "native.json"
            native_path.write_text(json.dumps(native))
            build = {"source": "/arbitrary/source", "role": "agent", "production": native["productionSources"],
                "task10SourceInventory": {"sha256": "a"*64}, "productionUnchanged": True,
                "copiedProductionUnchanged": True, "runtimeCompile": {"passed": True},
                "supportsExecutionNonce": True, "bundleName": "test.bundle"}
            build_path = root / "build.json"
            build_path.write_text(json.dumps(build))
            execution.update(buildReport=policy.evidence.record(build_path))
            row_receipt(execution, native_path)
            execution_path = root / "execution.json"
            execution_path.write_text(json.dumps(execution))
            report = {"taskId": "10_media_upload_quality", "platform": "arkts", "role": "agent", "provenance": {
                "productionSourceRoot": "/arbitrary/source", "sourceInventory": {"sha256": "a"*64},
                "productionSources": native["productionSources"]}}
            row = policy.bind({"caseId": policy.CASE, "role": "agent", "traceDigest": SPEC["traceDigest"]}, report,
                              CONTRACT, native_path, execution_path, root / "retained")
            used = set()
            policy.validate_entry_failure(row, report, used, contract=CONTRACT)
            with self.assertRaisesRegex(ValueError, "reused"):
                policy.validate_entry_failure(row, report, used, contract=CONTRACT)
            for key in ("source", "role", "contract", "fabricated"):
                r, candidate_report, contract = copy.deepcopy(row), copy.deepcopy(report), copy.deepcopy(CONTRACT)
                if key == "source":
                    candidate_report["provenance"]["sourceInventory"]["sha256"] = "b"*64
                elif key == "role":
                    candidate_report["role"] = "base"
                elif key == "contract":
                    contract["cases"][-1]["expected"]["attempts"] = 2
                else:
                    r["observed"] = {"preparedMediaExists": True}
                with self.subTest(mutation=key), self.assertRaises(ValueError):
                    policy.validate_entry_failure(r, candidate_report, set(), contract=contract)

            for key, value in (("sha256", "0"*64), ("bytes", 1), ("remote", "/data/app/el2/100/base/other.bundle/cache/ltb-native-result_123.json")):
                changed = copy.deepcopy(execution)
                changed["rowArtifact"][key] = value
                execution_path.write_text(json.dumps(changed))
                mutated = policy.bind({"caseId": policy.CASE, "role": "agent", "traceDigest": SPEC["traceDigest"]}, report,
                    CONTRACT, native_path, execution_path, root / ("artifact-mutation-" + key)) if key == "remote" else None
                # Mutated evidence has internally consistent container hashes, not merely a stale JSON pin.
                if key != "remote":
                    retained_execution = root / (key + ".execution.json")
                    summary = json.loads(policy.evidence.read_record(row["entryFailureEvidence"]["executionSummary"]))
                    summary["rowArtifact"][key] = value
                    retained_execution.write_text(json.dumps(summary))
                    mutated = copy.deepcopy(row)
                    mutated["entryFailureEvidence"]["executionSummary"] = policy.evidence.record(retained_execution)
                with self.subTest(rowArtifact=key), self.assertRaises(ValueError):
                    policy.validate_entry_failure(mutated, report, set(), contract=CONTRACT)
            summary = json.loads(policy.evidence.read_record(row["entryFailureEvidence"]["executionSummary"]))
            summary["rowArtifact"]["processLogMarker"]["characters"] -= 1
            wrong_count = root / "wrong-character-count.json"
            wrong_count.write_text(json.dumps(summary))
            mutated = copy.deepcopy(row)
            mutated["entryFailureEvidence"]["executionSummary"] = policy.evidence.record(wrong_count)
            with self.assertRaisesRegex(ValueError, "character count"):
                policy.validate_entry_failure(mutated, report, set(), contract=CONTRACT)


if __name__ == "__main__":
    unittest.main()
