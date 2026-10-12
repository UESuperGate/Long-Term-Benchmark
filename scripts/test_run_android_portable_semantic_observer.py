import json
import tempfile
import unittest
from pathlib import Path

from run_android_portable_semantic_observer import CONTRACT, RULES, candidate_sources, option_matches, strip_comments


class AndroidPortableSemanticObserverTest(unittest.TestCase):
    def test_rules_exactly_cover_shared_contract(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(set(RULES), {case["caseId"] for case in contract["cases"]})
        self.assertEqual(len(RULES), 37)

    def test_option_requires_all_patterns_in_one_production_file(self):
        option = {"path": r"\.kt$", "patterns": ["State", "Event", "Effect"]}
        split = {"State.kt": "State Event", "Effect.kt": "Effect"}
        together = {"Transition.kt": "State Event Effect"}
        self.assertEqual(option_matches(option, split), (False, None))
        self.assertEqual(option_matches(option, together), (True, "Transition.kt"))

    def test_candidate_sources_stay_inside_task_roots(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            included = root / "features/messages/impl/src/main/kotlin/Included.kt"
            excluded = root / "features/home/impl/src/main/kotlin/Excluded.kt"
            included.parent.mkdir(parents=True)
            excluded.parent.mkdir(parents=True)
            included.write_text("class Included", encoding="utf-8")
            excluded.write_text("class Excluded", encoding="utf-8")
            sources = candidate_sources(root, ("features/messages/",))
        self.assertEqual(list(sources), ["features/messages/impl/src/main/kotlin/Included.kt"])

    def test_comments_do_not_count_as_transition_evidence(self):
        source = "// State Event Effect\nclass RealCode"
        self.assertNotIn("Effect", strip_comments(source))


if __name__ == "__main__":
    unittest.main()
