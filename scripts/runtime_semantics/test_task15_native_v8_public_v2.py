"""Offline-only compatibility regression; no SDK/device/model."""
import hashlib
import json
import unittest
from unittest.mock import patch

from . import task15_native_successor_v8_public_v2 as refresh


class PublicCompatibilityTests(unittest.TestCase):
    def test_old_source_and_pin_unchanged_new_public_matches_retained_lineage(self):
        self.assertEqual(refresh.OLD_PUBLIC_SHA,refresh.previous.old.PUBLIC_SHA)
        refresh.require_current_public()
        sources = refresh.archived_sources()
        self.assertEqual(refresh.OLD_PUBLIC_SHA,hashlib.sha256(sources['scripts/run_runtime_transition_matrix.py']).hexdigest())
        self.assertNotEqual(refresh.PUBLIC_SHA,refresh.OLD_PUBLIC_SHA)

    def test_unknown_next_public_revision_is_rejected(self):
        with patch.object(refresh,'PUBLIC_SHA','0'*64):
            with self.assertRaises(ValueError):refresh.require_current_public()
        self.assertEqual(refresh.OLD_PUBLIC_SHA,refresh.previous.old.PUBLIC_SHA)

    def test_current_public_still_admits_only_unavailable_report(self):
        from scripts.run_runtime_transition_matrix import validate_report
        report = refresh.previous.unavailable(refresh.TASK,'.','offline public compatibility only')
        validate_report(report,refresh.core.load(refresh.previous.producer.CONTRACT))
        self.assertEqual((0,0,10),tuple(report['semantic'][key] for key in ('passed','failed','notScored')))
        self.assertFalse(report['publication']['eligible'])
        self.assertEqual({},refresh.previous.guard.REVIEWED_PROFILES)


if __name__ == '__main__':unittest.main()
