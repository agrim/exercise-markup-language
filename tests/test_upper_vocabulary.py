"""Registered macro/socket examples must work before adding recipe-specific compensation."""
import math
import unittest

from eml import Program, load
from eml.data import ROOT


class ReusableUpperVocabulary(unittest.TestCase):
    def test_documented_setup_motion_pairs_work_without_detail_or_contact_ik(self):
        pairs = load(ROOT / "docs/upper-motion-setups.json")["setups"]
        for pair in pairs:
            if "support" in pair:
                continue  # Ground vocabulary tests verify these planted and moving limbs.
            for motion in pair["motions"]:
                with self.subTest(pose=pair["pose"], action=motion):
                    p = Program({
                        "eml": "1.1", "id": "personal-arm-sequence", "title": "Personal movement",
                        "instructions": "Demonstrate the named motion from its compatible starting pose.",
                        "start": {"pose": pair["pose"]}, "muscles": {"primary": [], "secondary": []},
                        "phases": [{"id": "move", "seconds": 1, "actions": [{"use": motion}]},
                                   {"id": "return", "seconds": 1, "actions": []}],
                        "repeat": {"mode": "loop", "count": 1},
                    })
                    base = p.sample(0)
                    frames = [p.sample(i/20) for i in range(41)]
                    self.assertFalse([d for frame in frames for d in frame["diagnostics"]])
                    target = frames[20]
                    joints = ("leftForearm", "leftHand", "rightForearm", "rightHand", "pelvis")
                    self.assertGreater(max(math.dist(base["positions"][j], target["positions"][j]) for j in joints), .10)
                    self.assertLess(max(math.dist(base["positions"][j], frames[-1]["positions"][j]) for j in joints), .0001)

    def test_supine_setups_have_forward_bending_knees_without_foot_targets(self):
        for name in ("supine", "upper-floor-supine-grip-both"):
            d = {"eml": "1.1", "id": "personal-supine-start", "title": "Floor setup",
                 "instructions": "Hold in the resting floor setup.", "start": {"pose": name},
                 "muscles": {"primary": [], "secondary": []},
                 "phases": [{"id": "still", "seconds": 1, "actions": []}],
                 "repeat": {"mode": "hold", "count": 1}}
            f = Program(d).sample(0)
            self.assertFalse(f["diagnostics"])
            self.assertGreater(f["positions"]["leftShin"][0], 0)
            self.assertLess(f["positions"]["rightShin"][0], 0)
