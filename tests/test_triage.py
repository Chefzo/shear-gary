import unittest

from gary.models import CLASS_EMERGENCY, CLASS_NEEDS_REVIEW, CLASS_ROUTINE, ESCALATE, NO_ESCALATION
from gary.triage import classify


class TriageTests(unittest.TestCase):
    def test_mind_map_examples(self) -> None:
        emergency_pipe = classify("Burst pipe in the bathroom")
        self.assertEqual(emergency_pipe.classification, CLASS_EMERGENCY)
        self.assertEqual(emergency_pipe.matched_rule, "burst_pipe")
        self.assertEqual(emergency_pipe.escalation, ESCALATE)

        emergency_hvac = classify("HVAC down on the second floor")
        self.assertEqual(emergency_hvac.classification, CLASS_EMERGENCY)
        self.assertEqual(emergency_hvac.matched_rule, "hvac_down")

        flickering = classify("Flickering light in studio 3")
        self.assertEqual(flickering.classification, CLASS_ROUTINE)
        self.assertEqual(flickering.matched_rule, "flickering_light")
        self.assertEqual(flickering.escalation, NO_ESCALATION)

        self.assertEqual(classify("the filter needs changing").classification, CLASS_ROUTINE)
        self.assertEqual(classify("bulb is out in the hall").matched_rule, "bulb")

    def test_hvac_filter_stays_routine(self) -> None:
        result = classify("Please replace the HVAC filter in studio 2")
        self.assertEqual(result.classification, CLASS_ROUTINE)
        self.assertEqual(result.matched_rule, "filter")

    def test_emergency_wins_when_both_match(self) -> None:
        result = classify("Burst pipe and a bulb is out")
        self.assertEqual(result.classification, CLASS_EMERGENCY)

    def test_paraphrase_and_bare_leak_need_a_person(self) -> None:
        paraphrase = classify("HVAC isn't working")
        self.assertEqual(paraphrase.classification, CLASS_NEEDS_REVIEW)
        self.assertEqual(paraphrase.escalation, ESCALATE)
        self.assertIsNone(paraphrase.matched_rule)

        leak = classify("there is a leak under the sink")
        self.assertEqual(leak.classification, CLASS_NEEDS_REVIEW)

    def test_limitation_is_on_every_result(self) -> None:
        for text in ("burst pipe", "flickering light", "hello"):
            limitation = classify(text).limitation
            self.assertIn("does not dispatch", limitation)
            self.assertIn("not a life-safety system", limitation)

    def test_word_boundaries(self) -> None:
        self.assertEqual(classify("no action items today").classification, CLASS_NEEDS_REVIEW)
        self.assertEqual(classify("the fireplace screen is loose").classification, CLASS_NEEDS_REVIEW)
        self.assertEqual(classify("flooding in the lobby").matched_rule, "flooding")


if __name__ == "__main__":
    unittest.main()
