"""Read-only preservation/coverage tests; no delegate/build/device execution."""
import unittest
from unittest import mock
from . import task14_actual_default_adoption_v1 as adoption


class AdoptionTests(unittest.TestCase):
    def test_plan_preserves_actual_model_result_and_does_not_mislabel_case001_as_full9(self):
        plan = adoption.plan()
        self.assertFalse(plan['fullNineDelegateImplemented'])
        self.assertTrue(plan['notAStraightFullNineDelegate'])
        self.assertEqual(['jr_state_001_entry_opens_address_flow'], plan['currentNativeSuiteCaseIds'])
        self.assertEqual(9, len(plan['caseRequirements']))
        self.assertEqual({'passed': 7, 'failed': 2, 'notScored': 0}, plan['historicalModelReassessment']['counts'])
        self.assertEqual(302.552, plan['historicalModelReassessment']['modelDurationSeconds'])
        self.assertFalse(plan['historicalModelReassessment']['revalidatedOrRelabeled'])

    def test_no_old_weak_domain_host_adoption_and_four_real_controls_required(self):
        plan = adoption.plan()
        self.assertEqual(3, len(plan['forbiddenWeakHostCases']))
        self.assertTrue(plan['noFallbackToOldFormalFinalPoles'])
        self.assertEqual([[0, 9, 0], [9, 0, 0], [0, 9, 0], [9, 0, 0]], plan['calibrationRequired']['expectedPFNS'])
        self.assertEqual(3600, plan['calibrationRequired']['oneOverallDeadlineSeconds'])
        self.assertFalse(plan['deviceStarted'])

    def test_mutated_historical_pin_is_rejected_not_rewritten(self):
        with mock.patch.object(adoption, 'PROOF_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'historical pins'):
                adoption.plan()


if __name__ == '__main__': unittest.main()
