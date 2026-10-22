import unittest

from scripts.runtime_semantics.audit_task10_agent_entry_binding import common_prefix_binding


class Task10BindingAuditTest(unittest.TestCase):
    def setUp(self):
        self.common = [{"id": "attachment_caption", "type": "TextInput", "visible": "true", "clickable": "true"},
                       {"id": "attachment_send", "type": "Button", "visible": "true", "clickable": "true"}]

    def test_original_common_only_shape_is_not_flagged(self):
        result = common_prefix_binding(self.common)
        self.assertTrue(result["exactCommonOnlyBinding"])
        self.assertFalse(result["semanticFeaturePresenceInferred"])

    def test_unknown_selector_is_not_silently_classified_as_absent_feature(self):
        for selector in ("video_quality_button", "arbitrary-id", ""):
            for enabled in ("true", "false"):
                with self.subTest(selector=selector, enabled=enabled):
                    result = common_prefix_binding(self.common + [{"id": selector, "type": "Button",
                        "text": "Change", "visible": "true", "enabled": enabled}])
                    self.assertFalse(result["exactCommonOnlyBinding"])
                    self.assertEqual(1, len(result["additionalInteractiveControls"]))

    def test_missing_common_inputs_is_unbound_not_semantic_failure(self):
        result = common_prefix_binding([])
        self.assertFalse(result["exactCommonOnlyBinding"])
        self.assertFalse(result["semanticFeaturePresenceInferred"])


if __name__ == "__main__":
    unittest.main()
