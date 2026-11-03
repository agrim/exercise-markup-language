"""Setup-position pins contributed by v1.1 poses and coordinated motion definitions."""

import math
import unittest

from eml import Error, Program
from eml.kinematics import rotate
from eml.posture import SolvedFrame


FEET = {"leftHeel", "leftBall", "rightHeel", "rightBall"}


def routine(motion="squat-down", amount=1):
    return {
        "eml": "1.1", "id": "my-standing-movement", "title": "Custom movement",
        "start": {"pose": "standing"},
        "phases": [
            {"id": "descend", "seconds": 1, "actions": [{"use": motion, "amount": amount}]},
            {"id": "return", "seconds": 1, "actions": []},
        ],
        "repeat": {"mode": "loop", "count": 1},
        "muscles": {"primary": ["quadriceps"], "secondary": ["glutes"]},
    }


def contacts(program, phase):
    return program.effective_contacts(program.doc["phases"][phase])


class FixedPointTests(unittest.TestCase):
    def test_new_squats_and_hinges_hold_the_feet_on_entry_and_return(self):
        for name in ("squat-down", "squat-upright", "hip-hinge"):
            for amount in (0.5, 1):
                with self.subTest(motion=name, amount=amount):
                    p = Program(routine(name, amount))
                    for f in p.compile(24)["frames"]:
                        for point in FEET:
                            self.assertLess(math.dist(f["landmarks"][point], p.anchors[point]), 0.001)
                        solved = SolvedFrame(f, p.solver.rig)
                        for side in ("left", "right"):
                            up = rotate(solved.world(side + "Foot"), (0, 1, 0))
                            self.assertLess(math.dist(up, (0, 1, 0)), 0.001)
                    start, low = p.segment(0, 0), p.segment(0, 1)
                    self.assertGreater(start["positions"]["pelvis"][1] - low["positions"]["pelvis"][1], 0.015)

    def test_pose_and_nested_motions_union_pins_and_ignore_zero_amounts(self):
        d = routine("combination")
        d["start"]["pose"] = "my-derived-pose"
        d["definitions"] = {
            "poses": {
                "my-pose": {"extends": "standing", "fixedPoints": ["leftHeel"]},
                "my-derived-pose": {"extends": "my-pose", "fixedPoints": ["leftBall"]},
            },
            "motions": {
                "repeat-pins": {"fixedPoints": ["leftHeel", "rightBall"]},
                "irrelevant": {"fixedPoints": ["leftGrip"]},
                "combination": {"actions": [
                    {"use": "repeat-pins"}, {"use": "squat-down"}, {"use": "irrelevant", "amount": 0},
                ]},
            },
        }
        d["phases"].append({"id": "hold-at-start", "seconds": 1, "actions": []})
        p = Program(d)
        for i in (0, 1):
            claims = contacts(p, i)
            self.assertEqual({c["effector"] for c in claims}, FEET)
            self.assertEqual(len(claims), 4)
        self.assertEqual({c["effector"] for c in contacts(p, 2)}, {"leftHeel", "leftBall"})

    def test_explicit_limb_targets_and_stance_take_priority(self):
        d = routine()
        left = {"effector": "leftBall", "target": {"point": [0.2, 0.012, 0.1]}}
        d["contacts"] = [left]
        p = Program(d)
        self.assertIn(left, contacts(p, 0))
        self.assertEqual({c["effector"] for c in contacts(p, 0)}, {"leftBall", "rightHeel", "rightBall"})
        d["start"]["stance"] = {"width": 0.38, "toeOut": 16}
        p = Program(d)
        self.assertEqual(contacts(p, 0), p.stance + [left])
        d["phases"][0]["contacts"] = []
        self.assertEqual(contacts(Program(d), 0), [])
        d["phases"][0]["contacts"] = [left]
        self.assertEqual(contacts(Program(d), 0), [left])

    def test_invalid_socket_and_conflicting_explicit_claims_are_rejected(self):
        d = routine()
        d["definitions"] = {"motions": {"unused": {"fixedPoints": ["leftEar"]}}}
        with self.assertRaises(Error) as invalid:
            Program(d)
        self.assertEqual(invalid.exception.path, "/definitions/motions/unused/fixedPoints/0")
        del d["definitions"]
        claim = {"effector": "leftBall", "target": "start"}
        d["contacts"] = [claim, {**claim, "target": "floor"}]
        with self.assertRaises(Error) as ambiguous:
            Program(d)
        self.assertEqual(ambiguous.exception.code, "duplicate-effector")

    def test_incompatible_inherited_pins_report_the_unsatisfied_contact(self):
        d = routine("incompatible")
        d["definitions"] = {"motions": {
            "fix-heel": {"fixedPoints": ["leftHeel"]},
            "flex-planted-toe": {"fixedPoints": ["leftBall"], "joints": {"leftToe": [90, 0, 0]}},
            "incompatible": {"actions": [{"use": "fix-heel"}, {"use": "flex-planted-toe"}]},
        }}
        p = Program(d)
        self.assertEqual({c["effector"] for c in contacts(p, 0)}, {"leftHeel", "leftBall"})
        with self.assertRaises(Error) as error:
            p.compile(24)
        self.assertEqual(error.exception.code, "unreachable-contact")

    def test_version_one_keeps_the_original_fk_and_rejects_new_definitions(self):
        d = routine()
        d["eml"] = "1.0"
        p = Program(d)
        self.assertEqual(contacts(p, 0), [])
        self.assertLess(p.sample(1 / 6)["landmarks"]["leftBall"][1], -0.012)
        d["definitions"] = {"poses": {"v11-only": {"fixedPoints": ["leftHeel"]}}}
        with self.assertRaises(Error) as unsupported:
            Program(d)
        self.assertEqual(unsupported.exception.code, "schema")
