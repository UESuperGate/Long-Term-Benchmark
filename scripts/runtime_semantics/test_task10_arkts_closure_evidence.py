import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.runtime_semantics import task10_arkts_closure_evidence as closure
from scripts.runtime_semantics.task10_native_artifacts import read_native_artifact, retain_pair

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'experiment_results/runtime_transition_20261020/task10_raw_retention_v1'
CONTRACT = json.loads((ROOT / 'benchmark_tasks/10_media_upload_quality/transitions.json').read_text())


class ClosureEligibilityTest(unittest.TestCase):
    def test_both_actual_negative_controls_have_full_reviewed_closure_and_actual_prefix(self):
        for control in ('base', 'base-copy'):
            report = json.loads((RUN / 'controls' / control / 'accepted.runtime.json').read_text())
            results = closure.validate_report(report, CONTRACT)
            self.assertEqual(9, sum(item.get('closureEligible') is True for item in results))

    def test_final_controls_and_real_native_candidate_are_not_missing_entry_whitelists(self):
        paths = [RUN / 'candidate/accepted/accepted.runtime.json'] + [
            RUN / 'controls' / control / 'accepted.runtime.json' for control in ('final', 'final-copy')]
        for path in paths:
            self.assertTrue(all(not item['applies'] for item in
                                closure.validate_report(json.loads(path.read_text()), CONTRACT)))

    def test_legal_role_metadata_does_not_change_reviewed_closure_eligibility(self):
        original = json.loads((RUN / 'controls/base-copy/accepted.runtime.json').read_text())
        results = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for role in ('base', 'final', 'agent'):
                # Unit-only metadata variants, never published as device executions.
                report = copy.deepcopy(original)
                report['role'] = role
                row = report['semantic']['cases'][0]
                row['role'] = row['entryFailureEvidence']['role'] = role
                bundle = row['nativeArtifacts']
                execution = json.loads(read_native_artifact(bundle['execution']))
                execution['role'] = role
                for raw in execution['semantic']['cases']:
                    raw['role'] = role
                path = root / f'{role}.unit-only-execution.json'
                path.write_text(json.dumps(execution))
                record = closure.shared.record(path)
                pair = retain_pair(record, root / 'retained')
                bundle['execution'] = bundle['nativeResult'] = pair
                report['provenance']['deviceReport'] = record
                results.append(closure.validate_entry_failure(row, report, contract=CONTRACT))
                self.assertEqual('fail', row['status'])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertTrue(results[0]['closureEligible'])

    def test_invalid_or_inconsistent_role_identity_still_rejects(self):
        original = json.loads((RUN / 'controls/base-copy/accepted.runtime.json').read_text())
        for report_role, row_role in (('invalid', 'invalid'), ('final', 'agent'), ('agent', 'final')):
            report = copy.deepcopy(original)
            report['role'] = report_role
            row = report['semantic']['cases'][0]
            row['role'] = row_role
            with self.subTest(report=report_role, row=row_role), self.assertRaisesRegex(ValueError, 'entry role changed'):
                closure.validate_entry_failure(row, report, contract=CONTRACT)

    def test_source_claim_common_preview_and_role_alone_cannot_establish_eligibility(self):
        original = json.loads((RUN / 'controls/base-copy/accepted.runtime.json').read_text())
        for change in ('source', 'role', 'raw'):
            report = copy.deepcopy(original)
            if change == 'source':
                report['provenance']['sourceInventory']['sha256'] = '0' * 64
            elif change == 'role':
                report['semantic']['cases'][0]['role'] = 'final'
            else:
                del report['semantic']['cases'][0]['nativeArtifacts']
            with self.subTest(change=change), self.assertRaises(ValueError):
                closure.validate_entry_failure(report['semantic']['cases'][0], report, contract=CONTRACT)

    def test_complete_actual_ui_unknown_and_renamed_controls_are_ineligible(self):
        report = json.loads((RUN / 'controls/base-copy/accepted.runtime.json').read_text())
        tree = json.loads(read_native_artifact(report['semantic']['cases'][0]['nativeArtifacts']['layouts'][0]))
        fixture = closure.load_fixture()
        closure.check_ui(tree, fixture)
        for mutation in ('extra', 'renamed', 'hidden'):
            changed = copy.deepcopy(tree)
            if mutation == 'renamed':
                for node in closure._attributes(closure.project_tree(changed)):
                    if node.get('id') == 'attachment_send':
                        # Mutate the actual recursive tree, not the projected copy.
                        def rename(item):
                            if item['attributes'].get('id') == 'attachment_send':
                                item['attributes']['id'] = 'renamed_send'
                            for child in item.get('children', []): rename(child)
                        rename(changed)
            else:
                changed.setdefault('children', []).append({'attributes': {
                    'id': 'unreviewed', 'type': 'Button', 'visible': 'false' if mutation == 'hidden' else 'true'}, 'children': []})
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'unknown/extra/renamed'):
                closure.check_ui(changed, fixture)

    def test_import_as_script_style_package_has_no_root_side_effect(self):
        code = (f"import sys;sys.path.insert(0,{str(ROOT / 'scripts')!r});" +
                "from runtime_semantics import task10_arkts_closure_evidence as module;" +
                f"assert {str(ROOT)!r} not in sys.path;assert callable(module.validate_entry_failure)")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-I', '-c', code], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
