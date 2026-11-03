"""Mechanical expectations that schema validity and frame-to-frame continuity cannot establish."""

import math
import unittest

from eml.data import ROOT, load
from eml.program import Program


def exercise(name, **parameters):
    return Program(load(ROOT / "exercises" / f"{name}.json"), parameters)


def elbow_bend(frame, side):
    joints = frame["positions"]
    a, b, c = [joints[side + name] for name in ("UpperArm", "Forearm", "Hand")]
    u = [tip - base for base, tip in zip(a, b)]
    v = [tip - base for base, tip in zip(b, c)]
    dot = sum(x * y for x, y in zip(u, v)) / (math.hypot(*u) * math.hypot(*v))
    return math.degrees(math.acos(max(-1.0, min(dot, 1.0))))


class UpperExamples(unittest.TestCase):
    def test_fly_raise_and_straight_arm_pull_keep_a_soft_elbow(self):
        for name in (
            "dumbbell-chest-fly",
            "pec-deck",
            "cable-chest-fly",
            "reverse-pec-deck",
            "straight-arm-pulldown",
            "dumbbell-lateral-raise",
            "dumbbell-front-raise",
            "cable-lateral-raise",
            "bent-over-rear-delt-fly",
        ):
            with self.subTest(exercise=name):
                program = exercise(name)
                frames = [program.sample(program.duration * i / 32) for i in range(33)]
                for side in ("left", "right"):
                    bends = [elbow_bend(f, side) for f in frames]
                    self.assertLess(max(bends), 45)
                    self.assertLess(max(bends) - min(bends), 23)
                grip = [f["landmarks"]["leftGrip"] for f in frames]
                self.assertGreater(max(math.dist(p, grip[0]) for p in grip), 0.20)
                self.assertFalse(any(f["diagnostics"] for f in frames))

    def test_vertical_body_pull_raises_the_body_while_both_grips_stay_on_the_bar(self):
        widths = {}
        for name in ("pull-up", "chin-up"):
            p = exercise(name)
            frames = [p.sample(i * p.duration / 12) for i in range(13)]
            start = frames[0]["landmarks"]
            widths[name] = math.dist(start["leftGrip"], start["rightGrip"])
            self.assertGreater(
                frames[6]["positions"]["pelvis"][1]
                - frames[0]["positions"]["pelvis"][1],
                0.25,
            )
            for side in ("left", "right"):
                self.assertLess(
                    max(
                        math.dist(f["landmarks"][side + "Grip"], start[side + "Grip"])
                        for f in frames
                    ),
                    0.005,
                )
        self.assertGreater(widths["pull-up"] - widths["chin-up"], 0.12)

    def test_bird_dog_alternates_opposite_limbs_and_replants_between_reaches(self):
        p = exercise("bird-dog")
        start = p.sample(0)
        for t, arm, leg in ((0.25, "left", "right"), (0.75, "right", "left")):
            peak = p.sample(p.duration * t)
            self.assertGreater(
                math.dist(
                    start["landmarks"][arm + "Palm"], peak["landmarks"][arm + "Palm"]
                ),
                0.40,
            )
            self.assertGreater(
                math.dist(
                    start["positions"][leg + "Shin"], peak["positions"][leg + "Shin"]
                ),
                0.35,
            )
            self.assertLess(
                math.dist(
                    start["landmarks"][leg + "Palm"], peak["landmarks"][leg + "Palm"]
                ),
                0.005,
            )
        center = p.sample(0.5 * p.duration)
        self.assertLess(
            max(
                math.dist(center["landmarks"][key], start["landmarks"][key])
                for key in ("leftPalm", "rightPalm")
            ),
            0.005,
        )

    def test_rollout_travels_on_its_axle_while_both_knees_stay_planted(self):
        program = exercise("ab-wheel-rollout")
        frames = [program.sample(program.duration * i / 24) for i in range(25)]
        for frame in frames:
            for side in ("left", "right"):
                self.assertLess(
                    math.dist(
                        frame["positions"][side + "Shin"],
                        frames[0]["positions"][side + "Shin"],
                    ),
                    0.001,
                )
                grip = frame["equipment"]["grip"]["sockets"][side + "Grip"]
                self.assertLess(
                    math.dist(frame["landmarks"][side + "Grip"], grip), 0.012
                )
            self.assertAlmostEqual(frame["equipment"]["grip"]["position"][1], 0.117)
            self.assertFalse(frame["diagnostics"])
        self.assertGreater(
            frames[12]["equipment"]["grip"]["position"][2]
            - frames[0]["equipment"]["grip"]["position"][2],
            0.65,
        )

    def test_shorter_raise_keeps_dumbbells_in_the_hands(self):
        full = exercise("dumbbell-lateral-raise")
        shortened = exercise("dumbbell-lateral-raise", excursion=0.45)
        base = full.sample(0)["landmarks"]["leftGrip"]
        max_height = full.sample(full.duration / 2)["landmarks"]["leftGrip"][1]
        frame = shortened.sample(shortened.duration / 2)
        self.assertTrue(base[1] < frame["landmarks"]["leftGrip"][1] < max_height - 0.20)
        for side in ("left", "right"):
            self.assertLess(
                math.dist(
                    frame["landmarks"][side + "Grip"],
                    frame["equipment"][side + "-load"]["position"],
                ),
                0.00001,
            )
