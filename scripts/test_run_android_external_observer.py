import tempfile
import unittest
import json
from pathlib import Path

from run_android_external_observer import (
    environment_failure,
    junit_results,
    parse_test_methods,
)


class AndroidExternalObserverTest(unittest.TestCase):
    def test_parse_backtick_test_methods_and_filter(self):
        source = """
class ProbeTest {
    @Test
    fun `gallery maps images`() { assertThat(true).isTrue() }

    @Test
    fun `other behavior`() { assertThat(true).isTrue() }
}
"""
        methods = parse_test_methods(source, "gallery")
        self.assertEqual([method.name for method in methods], ["gallery maps images"])
        self.assertIn("assertThat(true)", methods[0].body)

    def test_junit_results_requires_matching_class(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "TEST-Probe.xml").write_text(
                '<testsuite><testcase classname="Probe" name="passes"/>'
                '<testcase classname="Probe" name="fails"><failure/></testcase>'
                '<testcase classname="Other" name="ignored"/></testsuite>',
                encoding="utf-8",
            )
            self.assertEqual(junit_results(root, "Probe"), {"passes": "passed", "fails": "failed"})

    def test_environment_failure_is_not_semantic_failure(self):
        self.assertTrue(environment_failure("SDK location not found"))
        self.assertTrue(environment_failure("TIMEOUT after 1800s"))
        self.assertFalse(environment_failure("Unresolved reference UserStatusPresenter"))

    def test_manifest_is_valid_json(self):
        manifest = Path(__file__).resolve().parents[1] / "state_tests" / "android_observer" / "probes.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(set(data["tasks"]), {
            "01_user_status",
            "02_gallery_messages",
            "03_timeline_protection_rich_events",
            "04_live_location",
            "05_link_new_device",
        })


if __name__ == "__main__":
    unittest.main()
