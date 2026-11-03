"""Measure moving station parts against the solved contact anatomy across the complete rep."""

import unittest
from math import dist
from eml import Program, load
from eml.data import ROOT
from eml.checks import check
from tools.audit_posture import audit, weight_bottom
from eml.kinematics import quaternion


def station(key):
    return load(ROOT / "exercises" / (key + ".json"))


class StationSupports(unittest.TestCase):
    def test_platforms_share_the_vertical_knee_travel_and_freezing_them_fails(self):
        for key, travel in [("assisted-pull-up", 0.4459), ("assisted-dip", -0.24)]:
            with self.subTest(exercise=key):
                doc = station(key)
                program = Program(doc)
                self.assertFalse(check(program)["issues"])
                start = program.segment(0, 0)["equipment"]["platform"]["position"]
                end = program.segment(0, 1)["equipment"]["platform"]["position"]
                self.assertAlmostEqual(end[1] - start[1], travel, places=3)
                del doc["phases"][0]["items"]["platform"]
                failures = Program(doc).segment(0, 0.5)["diagnostics"]
                self.assertEqual(
                    {d["effector"] for d in failures if d["reason"] == "support-gap"},
                    {"leftShin", "rightShin"},
                )

    def test_prone_curl_hinge_pivot_stays_seated_in_the_frame(self):
        program = Program(station("lying-leg-curl"))
        self.assertFalse(check(program)["issues"])
        y = []
        for i in range(2):
            for j in range(17):
                eq = program.segment(i, j / 16)["equipment"]
                roller = eq["roller"]["sockets"]
                self.assertLess(
                    dist(roller["axle"], eq["machine"]["sockets"]["pivot"]), 0.001
                )
                y.append(roller["roller"][1])
        self.assertGreater(max(y) - min(y), 0.21)

    def test_wall_support_checks_both_finite_face_contacts(self):
        doc = station("wall-sit")
        program = Program(doc)
        result = audit(program, 12, 3)
        self.assertFalse(result["issues"])
        self.assertFalse(result["unmeasuredSupports"])
        self.assertEqual(result["supportChecks"], 2 * result["samples"])
        doc["equipment"][0]["position"][2] -= 0.12
        d = Program(doc).segment(0, 0.5)["diagnostics"]
        self.assertEqual(
            {r["effector"] for r in d if r["reason"] == "support-gap"},
            {"chest", "pelvis"},
        )

    def test_weight_floor_includes_plate_extent_and_rotated_flat_caps(self):
        spec = {
            "visual": [
                dict(
                    shape="barbell",
                    dimensions=[2.2, 0.42, 0.42],
                    position=[0, 0, 0],
                    rotation=[0, 0, 0],
                )
            ]
        }
        p = {"position": [0, 0.211, 0], "rotation": quaternion([0, 0, 0])}
        self.assertAlmostEqual(weight_bottom(spec, p), 0.001)
        p["rotation"] = quaternion([0, 0, 90])
        self.assertAlmostEqual(weight_bottom(spec, p), 0.211 - 1.1)
