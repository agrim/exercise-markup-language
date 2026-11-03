"""Contact fixtures use the shipped atlas rather than an idealized symmetric skeleton."""

import json
import math
import unittest
from pathlib import Path

from eml.kinematics import Kinematics

ROOT = Path(__file__).resolve().parents[1]
ZERO = [0, 0, 0]
MODEL = json.loads((ROOT / "anatomy/model.json").read_text())
PROPS = {"test-bar": {"sockets": {"left": [0.11, 0, 0], "right": [-0.11, 0, 0]}}}


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.rig = Kinematics(MODEL, PROPS)
        self.rest = self.rig.sample(ZERO, {}, [], [], None)

    def assertPoint(self, a, b, tol=1e-8):
        self.assertLess(math.dist(a, b), tol)

    def test_rig_preserves_bind_landmarks_and_rotates_children_about_the_parent(self):
        for name, point in MODEL["landmarks"].items():
            self.assertPoint(self.rest["landmarks"][name], point)
        pose = self.rig.sample([0.3, -0.1, 0.04], {"leftUpperArm": [90, 0, 0]}, [], [])
        shoulder = self.rest["positions"]["leftUpperArm"]
        elbow = self.rest["positions"]["leftForearm"]
        dx, dy, dz = (v - u for v, u in zip(elbow, shoulder))
        base = pose["positions"]["leftUpperArm"]
        self.assertPoint(
            pose["positions"]["leftForearm"], [base[0] + dx, base[1] - dz, base[2] + dy]
        )
        self.assertEqual(len(pose["rotations"]), 51)

    def test_chest_drives_one_rigid_bar_with_two_independent_grips(self):
        item = {
            "id": "load",
            "kind": "test-bar",
            "follow": {"joint": "chest", "offset": [0, 0.04, 0.20]},
        }
        contacts = [
            {"effector": side + "Grip", "target": {"item": "load", "socket": side}}
            for side in ("left", "right")
        ]
        sample = self.rig.sample(
            ZERO, {"spine": [8, 24, 0], "leftThumb1": [0, 0, 0]}, [item], contacts
        )
        self.assertEqual(sample["diagnostics"], [])
        for side in ("left", "right"):
            self.assertPoint(
                sample["landmarks"][side + "Grip"],
                sample["equipment"]["load"]["sockets"][side],
            )
        self.assertAlmostEqual(
            math.dist(*(sample["equipment"]["load"]["sockets"].values())), 0.22
        )
        self.assertEqual(sample["rotations"]["leftThumb1"], [0, 0, 0, 1])
        self.assertNotEqual(sample["rotations"]["rightThumb1"], [0, 0, 0, 1])

    def test_gripping_driver_curls_its_fingers_while_preserving_explicit_detail(self):
        held = {
            "id": "load",
            "kind": "test-bar",
            "follow": {"joint": "rightHand", "grip": True},
        }
        pose = self.rig.sample(ZERO, {"rightIndex1": [0, 0, 0]}, [held], [])
        self.assertFalse(pose["diagnostics"])
        self.assertNotEqual(pose["rotations"]["rightThumb1"], [0, 0, 0, 1])
        self.assertEqual(pose["rotations"]["rightIndex1"], [0, 0, 0, 1])
        self.assertEqual(pose["rotations"]["leftThumb1"], [0, 0, 0, 1])
        held["follow"]["joint"] = "pelvis"
        with self.assertRaisesRegex(ValueError, "gripping driver"):
            self.rig.sample(ZERO, {}, [held], [])

    def test_start_and_floor_anchors_do_not_move_when_root_or_knee_changes(self):
        anchors = self.rest["landmarks"]
        claims = [
            {"effector": "leftHeel", "target": "start", "rotation": [0, 12, 0]},
            {"effector": "rightHeel", "target": "floor"},
        ]
        pose = self.rig.sample(
            [0, -0.17, -0.03], {"leftShin": [30, 0, 0]}, [], claims, anchors
        )
        self.assertEqual(pose["diagnostics"], [])
        self.assertPoint(pose["landmarks"]["leftHeel"], anchors["leftHeel"])
        self.assertPoint(
            pose["landmarks"]["rightHeel"],
            [anchors["rightHeel"][0], 0, anchors["rightHeel"][2]],
        )
        self.assertNotEqual(pose["rotations"]["leftThigh"], [0, 0, 0, 1])

    def test_already_satisfied_grip_preserves_authored_elbow_and_twist(self):
        angles = {"leftUpperArm": [-45, 22, 17], "leftForearm": [-80, 0, 8]}
        fk = self.rig.sample(ZERO, angles, [], [])
        grip = fk["landmarks"]["leftGrip"]
        claims = [{"effector": "leftGrip", "target": {"point": grip}}]
        solved = self.rig.sample(ZERO, angles, [], claims)
        self.assertPoint(
            fk["positions"]["leftForearm"], solved["positions"]["leftForearm"]
        )
        for name in angles:
            self.assertPoint(fk["rotations"][name], solved["rotations"][name])
        # Changing a nearby target must perturb the elbow continuously.
        claims[0]["target"]["point"] = [grip[0] + 0.005, *grip[1:]]
        nearby = self.rig.sample(ZERO, angles, [], claims)
        self.assertLess(
            math.dist(
                fk["positions"]["leftForearm"], nearby["positions"]["leftForearm"]
            ),
            0.01,
        )

    def test_two_points_on_one_foot_share_one_rigid_solution(self):
        anchors = self.rest["landmarks"]
        claims = [
            {"effector": key, "target": "start"} for key in ("leftHeel", "leftBall")
        ]
        pose = self.rig.sample(
            [0, -0.15, 0.05], {"leftShin": [25, 0, 0]}, [], claims, anchors
        )
        self.assertEqual(pose["diagnostics"], [])
        for claim in claims:
            self.assertPoint(
                pose["landmarks"][claim["effector"]], anchors[claim["effector"]]
            )
        pose = self.rig.sample(
            ZERO,
            {},
            [],
            [claims[0], {"effector": "leftBall", "target": {"point": [0, 0, 2]}}],
            anchors,
        )
        self.assertTrue(any(d["residual"] > 1 for d in pose["diagnostics"]))

    def test_reach_limits_keep_both_segment_lengths_and_report_the_gap(self):
        side = ["leftUpperArm", "leftForearm", "leftHand"]
        for target in ([2, 3, 4], self.rest["positions"]["leftUpperArm"]):
            with self.subTest(target=target):
                pose = self.rig.sample(
                    ZERO,
                    {},
                    [],
                    [
                        {
                            "effector": "leftHand",
                            "target": {"point": target},
                            "pole": [1, 0, 0],
                        }
                    ],
                )
                issue = pose["diagnostics"][0]
                self.assertEqual(issue["reason"], "unreachable-contact")
                self.assertAlmostEqual(
                    issue["residual"], math.dist(target, pose["positions"]["leftHand"])
                )
                for a, b in zip(side, side[1:]):
                    self.assertAlmostEqual(
                        math.dist(pose["positions"][a], pose["positions"][b]),
                        math.dist(self.rest["positions"][a], self.rest["positions"][b]),
                    )
        # End nearly straight and pole parallel to the reach direction.
        start = self.rest["positions"]["leftUpperArm"]
        pose = self.rig.sample(
            ZERO,
            {},
            [],
            [
                {
                    "effector": "leftHand",
                    "target": {"point": [start[0] + 0.43, *start[1:]]},
                    "pole": [1, 0, 0],
                }
            ],
        )
        self.assertFalse(pose["diagnostics"])

    def test_following_an_already_solved_hand_is_valid_but_self_driving_is_a_cycle(
        self,
    ):
        # Hand drives this bar from its own centre; it is independently positioned by a world target.
        item = {
            "id": "load",
            "kind": "test-bar",
            "follow": {"joint": "leftHand", "offset": [0, 0, 0]},
            "sockets": {"right": [-0.22, 0, 0]},
        }
        claims = [
            {"effector": "rightGrip", "target": {"item": "load", "socket": "right"}},
            {"effector": "leftGrip", "target": {"point": [0.12, 1.16, 0.20]}},
        ]
        a = self.rig.sample(ZERO, {}, [item], claims)
        b = self.rig.sample(ZERO, {}, [item], claims[::-1])
        self.assertEqual(a, b)
        self.assertFalse(a["diagnostics"])
        self.assertPoint(
            a["landmarks"]["rightGrip"], a["equipment"]["load"]["sockets"]["right"]
        )
        self_target = {
            "effector": "leftGrip",
            "target": {"item": "load", "socket": "left"},
        }
        cycle = self.rig.sample(ZERO, {}, [item], [self_target])
        self.assertEqual(cycle["diagnostics"][0]["reason"], "cyclic-driver")

    def test_unreachable_rotated_socket_diagnostics_measure_the_socket_not_the_wrist(
        self,
    ):
        item = {
            "id": "load",
            "kind": "test-bar",
            "position": [0.2, 2.8, 0.04],
            "rotation": [0, 90, 0],
        }
        contact = {
            "effector": "rightGrip",
            "target": {"item": "load", "socket": "right"},
        }
        a = self.rig.sample(ZERO, {"rightHand": [35, -12, 4]}, [item], [contact])
        target = a["equipment"]["load"]["sockets"]["right"]
        self.assertPoint(target, [0.2, 2.8, 0.15])
        self.assertAlmostEqual(
            a["diagnostics"][0]["residual"],
            math.dist(a["landmarks"]["rightGrip"], target),
        )


if __name__ == "__main__":
    unittest.main()
