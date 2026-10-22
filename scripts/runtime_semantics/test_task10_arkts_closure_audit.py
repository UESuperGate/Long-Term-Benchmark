import copy
import json
from pathlib import Path
import unittest

from scripts.runtime_semantics import audit_task10_arkts_closure_guard as audit

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'experiment_results/runtime_transition_20261020/task10_arkts_closure_guard_v1'
CONTRACT = json.loads((ROOT / 'benchmark_tasks/10_media_upload_quality/transitions.json').read_text())


class ClosureAuditTest(unittest.TestCase):
    def test_hash_before_delete_receipts_are_required_not_just_cleanup_label(self):
        report = json.loads((RUN / 'controls/base/accepted.runtime.json').read_text())
        self.assertTrue(audit.audit_cleanup(report)['verified'])
        for mutation in ('hashes', 'retained', 'source'):
            changed = copy.deepcopy(report)
            if mutation == 'hashes':
                changed['diagnostics']['strictRuntime']['cleanup']['binaryHashes'] = []
            elif mutation == 'retained':
                changed['diagnostics']['strictRuntime']['cleanup']['binaryArtifactsRetained'] = True
            else:
                changed['target'] = str(ROOT)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.audit_cleanup(changed)

    def test_real_unknown_mutants_preserve_actual_rendered_controls_and_no_verdict(self):
        for name, identifier in (('renamed-control', 'renamed_upload_command'),
                                 ('extra-control', 'unreviewed_extra')):
            result = audit.audit_mutation(RUN / 'unknown-ui-smokes' / name / 'not-scored.runtime.json', CONTRACT)
            self.assertEqual(identifier, result['actualRenderedMutationId'])
            self.assertEqual({'passed': 0, 'failed': 0, 'notScored': 9}, result['semantic'])


if __name__ == '__main__':
    unittest.main()
