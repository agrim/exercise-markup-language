"""Exercise-family expectations on the reference anatomy, independent of visual rendering."""

import math
import unittest

from eml.data import ROOT, load
from eml.program import Program


def program(name, parameters=None):
    return Program(load(ROOT / "exercises" / f"{name}.json"), parameters)


def corner(frame, side, joints):
    """The included angle at the middle joint (180 degrees is fully extended)."""
    a, b, c = [frame["positions"][side + joint] for joint in joints]
    u, v = ([x - y for x, y in zip(end, b)] for end in (a, c))
    cosine = sum(x * y for x, y in zip(u, v)) / (math.hypot(*u) * math.hypot(*v))
    return math.degrees(math.acos(max(-1, min(1, cosine))))


LEG = ("Thigh", "Shin", "Foot")
ARM = ("UpperArm", "Forearm", "Hand")


class LowerMechanics(unittest.TestCase):
    def test_loaded_pulls_extend_the_legs_without_curling_the_weight(self):
        for name in (
            "deadlift",
            "sumo-deadlift",
            "trap-bar-deadlift",
            "kettlebell-deadlift",
        ):
            with self.subTest(name=name):
                p = program(name)
                frames = [p.sample(p.duration * n / 24) for n in range(25)]
                self.assertGreater(
                    frames[12]["equipment"]["load"]["position"][1]
                    - frames[0]["equipment"]["load"]["position"][1],
                    0.50,
                )
                for side in ("left", "right"):
                    self.assertGreater(corner(frames[12], side, LEG), 156)
                    self.assertLess(corner(frames[0], side, LEG), 90)
                    for f in frames:
                        self.assertGreater(corner(f, side, ARM), 160)
                        self.assertLess(
                            math.dist(
                                f["landmarks"][side + "Grip"],
                                f["equipment"]["load"]["sockets"][side + "Grip"],
                            ),
                            0.001,
                        )
                        self.assertLess(
                            math.dist(
                                f["landmarks"][side + "Ball"],
                                frames[0]["landmarks"][side + "Ball"],
                            ),
                            0.001,
                        )
                    if name in ("deadlift", "sumo-deadlift"):
                        # The straight shaft must stay in front of the shin/thigh
                        # at the bar's height as it travels from floor to hip.
                        for f in frames:
                            _, height, z = f["equipment"]["load"]["position"]
                            hip, knee, ankle = [f["positions"][side + j] for j in LEG]
                            if height > hip[1]:
                                continue
                            a, b = (ankle, knee) if height < knee[1] else (knee, hip)
                            skin_axis = a[2] + (b[2] - a[2]) * (height - a[1]) / (
                                b[1] - a[1]
                            )
                            self.assertGreater(z - skin_axis, 0.035)

    def test_user_changes_goblet_squat_without_detaching_hands_or_feet(self):
        shallow = program(
            "goblet-squat", {"depth": 0.55, "stance-width-m": 0.21, "toe-out-deg": 0}
        )
        deep = program(
            "goblet-squat", {"depth": 1.12, "stance-width-m": 0.49, "toe-out-deg": 23}
        )

        def height_loss(p):
            return (
                p.segment(0, 0)["positions"]["pelvis"][1]
                - p.segment(0, 1)["positions"]["pelvis"][1]
            )

        self.assertGreater(height_loss(deep) - height_loss(shallow), 0.12)
        for p, width in ((shallow, 0.21), (deep, 0.49)):
            start = p.segment(0, 0)["landmarks"]
            self.assertAlmostEqual(
                start["leftHeel"][0] - start["rightHeel"][0], width, places=3
            )
            for n in range(13):
                f = p.sample(n * p.duration / 12)
                for side in ("left", "right"):
                    self.assertLess(
                        math.dist(f["landmarks"][side + "Heel"], start[side + "Heel"]),
                        0.002,
                    )
                    self.assertLess(
                        math.dist(
                            f["landmarks"][side + "Grip"],
                            f["equipment"]["bell"]["sockets"][side + "Grip"],
                        ),
                        0.001,
                    )

    def test_planting_a_step_or_sled_changes_knee_angle_and_retains_support(self):
        step = program("step-up")
        base = step.sample(0)
        top = step.segment(2, 1)
        self.assertLess(corner(base, "left", LEG), 85)
        self.assertGreater(corner(top, "left", LEG), 150)
        self.assertLess(
            math.dist(base["landmarks"]["leftBall"], top["landmarks"]["leftBall"]),
            0.002,
        )
        self.assertGreater(
            top["landmarks"]["rightBall"][1] - base["landmarks"]["rightBall"][1], 0.25
        )
        machine = program("leg-press")
        for side in ("left", "right"):
            self.assertGreater(corner(machine.segment(0, 0), side, LEG), 150)
            self.assertLess(corner(machine.segment(0, 1), side, LEG), 85)
            for n in range(9):
                f = machine.segment(0, n / 8)
                self.assertLess(
                    math.dist(
                        f["landmarks"][side + "Ball"],
                        f["equipment"]["sled"]["sockets"][side + "Foot"],
                    ),
                    0.002,
                )

    def test_plank_and_single_leg_hinge_keep_the_correct_supports(self):
        p = program("push-up")
        raised = p.segment(0, 0)
        for side in ("left", "right"):
            self.assertGreater(corner(raised, side, ARM), 149)
            self.assertLess(corner(p.segment(0, 1), side, ARM), 80)
            for n in range(9):
                f = p.segment(0, n / 8)
                self.assertGreater(corner(f, side, LEG), 163)
                for part in ("Palm", "Ball"):
                    self.assertLess(
                        math.dist(
                            f["landmarks"][side + part],
                            raised["landmarks"][side + part],
                        ),
                        0.004,
                    )
        p = program("single-leg-romanian-deadlift")
        stand, hinge = p.segment(0, 0), p.segment(0, 1)
        self.assertGreater(
            hinge["positions"]["rightFoot"][1] - stand["positions"]["rightFoot"][1],
            0.57,
        )
        self.assertGreater(corner(hinge, "left", LEG), 132)
        self.assertLess(
            math.dist(stand["landmarks"]["leftBall"], hinge["landmarks"]["leftBall"]),
            0.002,
        )
