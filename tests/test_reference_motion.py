import math
import unittest

from eml import Error, Program, load
from eml.checks import check
from eml.data import ROOT
from eml.kinematics import dot


class ReferenceMotionTests(unittest.TestCase):
    def test_new_id_reaches_both_palms_without_half_turn_wrist_flips(self):
        doc = load(ROOT / "exercises/push-up.json")
        doc["id"] = "personal-palm-test"
        program = Program(doc)
        frames = list(program.frames(30))
        for frame in frames:
            for side in ("left", "right"):
                hand = side + "Palm"
                target = next(
                    c["target"]["point"]
                    for c in doc["contacts"]
                    if c["effector"] == hand
                )
                self.assertLess(math.dist(frame["landmarks"][hand], target), 0.002)
                self.assertFalse(frame["diagnostics"])
        for a, b in zip(frames, frames[1:]):
            for side in ("left", "right"):
                for joint in ("UpperArm", "Forearm", "Hand"):
                    turn = abs(
                        dot(a["rotations"][side + joint], b["rotations"][side + joint])
                    )
                    self.assertLess(math.degrees(2 * math.acos(min(1, turn))), 12.0)

    def test_fast_custom_motion_is_reported_at_the_frame_and_rejected_on_export(self):
        doc = dict(
            eml="1.1",
            id="personal-fast-bend",
            title="Fast bend",
            start=dict(pose="standing"),
            muscles=dict(primary=["biceps"], secondary=[]),
            phases=[
                dict(
                    id="bend", seconds=0.05, actions=[dict(use="bend-elbows", amount=1)]
                )
            ],
            repeat={"mode": "once", "count": 1},
        )
        p = Program(doc)
        errors = check(p)["issues"]
        self.assertTrue(any(e["code"] == "fast-local-rotation" for e in errors))
        frame = next(
            f for f in p.compile(12, strict=False)["frames"] if f["diagnostics"]
        )
        issue = next(
            d for d in frame["diagnostics"] if d["reason"] == "fast-local-rotation"
        )
        self.assertEqual(issue["time"], frame["time"])
        self.assertGreater(issue["measured"], issue["limit"])
        self.assertEqual(issue["unit"], "deg/s")
        with self.assertRaises(Error):
            p.compile(12)
        doc["phases"][0]["seconds"] = 1
        self.assertEqual(check(Program(doc))["issues"], [])
