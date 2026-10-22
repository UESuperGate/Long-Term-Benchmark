import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.runtime_semantics import task11_plaintext_sdk as sdk
from scripts.runtime_semantics import task11_android_strict_runtime as runner


class PlainTextSdkTest(unittest.TestCase):
    def test_only_evaluator_annotation_changes_and_assertion_body_is_identical(self):
        original = sdk.ROOT / "state_tests/runtime/android/11_room_upgrade_navigation/messages/MessagesRenderedTest.kt"
        config = {"testClass": "runtime.MessagesRenderedTest", "evaluatorSources": [str(original)]}
        with tempfile.TemporaryDirectory() as temporary:
            result = sdk.configure(config, temporary)
            generated = Path(result["evaluatorSources"][0]).read_text()
            self.assertEqual(original.read_text(), generated.replace(sdk.REPLACEMENT, sdk.ANNOTATION))
            self.assertFalse(result["sdkBoundaryFixture"]["navigationReplaced"])
            self.assertEqual(config["evaluatorSources"], [str(original)])

    def test_unrelated_tests_are_not_rewritten(self):
        config = {"testClass": "runtime.RoomSummaryBasePrefixTest", "evaluatorSources": []}
        self.assertEqual(config, sdk.configure(config, Path("/not-used")))

    def test_missing_native_selects_only_external_sdk_switch_without_cargo(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(runner, "NATIVE_ROOT", Path(temporary)), \
                    mock.patch.object(runner, "_prepare_native_dependencies") as build:
                result = runner._select_runtime_dependency()
        build.assert_not_called()
        self.assertFalse(result["rustBuildStarted"])
        self.assertFalse(result["navigationReplaced"])

    def test_corrupted_or_wrong_abi_native_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "wrong.dylib"
            library.write_bytes(b"\x7fELFwrong-abi")
            item = sdk.record(library)
            (root / "provenance.json").write_text(json.dumps({"commit": "85035e2651fa9f41946455b391bb71950aeb7dc2",
                "library": item, "log": item, "cargoLock": item}))
            with mock.patch.object(runner, "NATIVE_ROOT", root):
                self.assertEqual("upstream_sdk_plain_text_switch", runner._select_runtime_dependency()["mode"])

    def test_sdk_fixture_rejects_mentions_and_calls_the_original_renderer(self):
        source = sdk.SDK_SOURCE.read_text()
        self.assertIn('!html.contains("<a"', source)
        self.assertIn('!html.contains("data-mention"', source)
        self.assertIn('view.isNativeCodeEnabled = false', source)
        self.assertIn('.updateStyle(style, handler)', source)
        self.assertIn('.setHtml(html)', source)
        for forbidden in ("navigateToRoom", "openRoom", "RoomGateway", "MessagesView", "return false"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
