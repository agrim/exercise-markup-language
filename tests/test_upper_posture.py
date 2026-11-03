"""Solved trajectory invariants for weight-bearing arms and hand-driven dumbbells."""
import math
import unittest
from eml import Program, load
from eml.data import ROOT
from eml.kinematics import dot, multiply, rotate, sub, unit


def exercise(name, **params):
    return Program(load(ROOT / "exercises" / (name + ".json")), params)


def axis_in_world(program, frame, joint, axis):
    world = []
    for j in program.model["joints"]:
        q = frame["rotations"][j["name"]]
        world.append(q if j["parent"] < 0 else multiply(world[j["parent"]], q))
        if j["name"] == joint:
            return rotate(world[-1], axis)
    raise AssertionError(joint)


class UpperPostureTests(unittest.TestCase):
    def test_side_plank_supports_on_the_forearm_in_front_of_the_body(self):
        p = exercise("side-plank")
        for t in (0, .5, 1):
            f = p.sample(t * p.duration)
            position = f["positions"]
            elbow = position["leftForearm"]
            shoulder = position["leftUpperArm"]
            facing = axis_in_world(p, f, "chest", [0, 0, 1])
            forearm = unit(sub(position["leftHand"], elbow))
            self.assertGreater(dot(facing, forearm), .93)
            self.assertLess(math.hypot(shoulder[0] - elbow[0], shoulder[2] - elbow[2]), .045)
            self.assertGreater(position["rightFoot"][1] - position["leftFoot"][1], .04)
            self.assertLess(math.dist(position["rightFoot"], position["leftFoot"]), .11)
            self.assertFalse(f["diagnostics"])
        # Deliberately reverse the supporting elbow. The point, hinge or both must now fail.
        bad = load(ROOT / "exercises/side-plank.json")
        bad["start"]["joints"] = {"leftForearm": [100, 0, 0]}
        errors = Program(bad).sample(0)["diagnostics"]
        self.assertTrue(any(e["reason"] == "hinge-bend" for e in errors))

    def test_raises_and_presses_lift_a_gripped_level_load_without_breaking_the_wrist(self):
        for name, max_shaft_angle in [
            ("dumbbell-lateral-raise", 10), ("dumbbell-front-raise", 10),
            ("dumbbell-shoulder-press", 14), ("arnold-press", 26),
        ]:
            with self.subTest(exercise=name):
                p = exercise(name)
                frames = [p.sample(p.duration * i / 64) for i in range(65)]
                for side in ("left", "right"):
                    start = frames[0]["positions"][side+"Hand"]
                    self.assertGreater(frames[32]["positions"][side+"Hand"][1] - start[1], .39)
                    for f in frames:
                        item = f["equipment"][side+"-load"]
                        self.assertLess(math.dist(f["landmarks"][side+"Grip"], item["sockets"]["handle"]), .001)
                        vertical = abs(rotate(item["rotation"], (1, 0, 0))[1])
                        self.assertLess(vertical, math.sin(math.radians(max_shaft_angle)))
                        self.assertLess(sum(x*x for x in f["rotations"][side+"Hand"][:3]), .0001)
                        self.assertFalse(f["diagnostics"])

    def test_personal_excursion_shortens_the_neutral_grip_curl(self):
        full = exercise("hammer-curl")
        half = exercise("hammer-curl", excursion=.5)
        base, lower, higher = [p.sample(t*p.duration)["landmarks"]["leftGrip"]
                               for p,t in [(full,0),(half,.5),(full,.5)]]
        self.assertGreater(lower[1], base[1]+.06)
        self.assertGreater(higher[1], lower[1]+.08)

    def test_smith_bar_stays_on_the_rails_and_on_the_upper_back(self):
        p = exercise("smith-machine-squat")
        frames = [p.sample(p.duration*i/40) for i in range(41)]
        for f in frames:
            bar = f["equipment"]["bar"]["position"]
            chest = f["positions"]["chest"]
            off = axis_in_world(p, f, "chest", [0,.275,-.097])
            rack = [a+b for a,b in zip(chest,off)]
            self.assertLess(math.dist(bar, rack), .019)
            self.assertAlmostEqual(bar[2], frames[0]["equipment"]["bar"]["position"][2], places=5)
            self.assertFalse(f["diagnostics"])
