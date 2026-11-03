"""Exercise-family expectations on the reference anatomy, independent of visual rendering."""

import math
import unittest

from eml.data import ROOT, load
from eml.program import Program
from eml.kinematics import add, rotate
from eml.posture import segment_distance


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

    def test_barbell_pull_paths_remain_level_and_close_throughout_both_directions(self):
        for name in ("deadlift", "sumo-deadlift", "romanian-deadlift"):
            with self.subTest(name=name):
                p = program(name)
                item = p.equipment[0]["id"]
                samples = p.frames(24)
                depths, heights = [], []
                for f in samples:
                    self.assertFalse(f["diagnostics"], f["diagnostics"])
                    bar = f["equipment"][item]
                    depths.append(bar["position"][2])
                    heights.append(bar["position"][1])
                    self.assertLess(math.dist(rotate(bar["rotation"], (1, 0, 0)), (1, 0, 0)), 0.001)
                    for side in ("left", "right"):
                        self.assertLess(math.dist(f["landmarks"][side+"Grip"], bar["sockets"][side+"Grip"]), 0.001)
                self.assertLess(max(depths) - min(depths), 0.06)
                self.assertGreater(max(heights) - min(heights), 0.24)

    def test_trap_bar_palm_centres_on_raised_handles_and_plates_start_on_floor(self):
        p = program("trap-bar-deadlift")
        parts = p.kit["trap-bar"]["visual"]
        plates = [part for part in parts if part["dimensions"][1] > 0.30]
        self.assertEqual(len(plates), 2)
        setup = p.sample(0)["equipment"]["load"]
        for plate in plates:
            self.assertAlmostEqual(setup["position"][1] + plate["position"][1] - plate["dimensions"][1]/2, 0, places=4)
        for side, sign in (("left", 1), ("right", -1)):
            handle, = [part for part in parts if part["position"][0]*sign > 0 and
                       part["position"][1] > 0 and part["rotation"] == [0, 90, 0]]
            for f in p.frames(16):
                load = f["equipment"]["load"]
                actual = add(load["position"], rotate(load["rotation"], handle["position"]))
                self.assertLess(math.dist(f["landmarks"][side+"Grip"], actual), 0.001)

    def test_kettlebell_clears_legs_and_forearms_do_not_enter_trunk(self):
        for name in ("kettlebell-deadlift", "kettlebell-swing"):
            with self.subTest(name=name):
                p = program(name)
                visual = p.kit["kettlebell"]["visual"][0]
                radius = visual["dimensions"][2] / 2
                center = add(visual["position"], (0, -(1.55*radius + 0.02), 0))
                for f in p.frames(24):
                    self.assertFalse(f["diagnostics"], f["diagnostics"])
                    parts = f["positions"]
                    bell = f["equipment"][p.equipment[0]["id"]]
                    ball = add(bell["position"], rotate(bell["rotation"], center))
                    for side in ("left", "right"):
                        self.assertGreater(segment_distance(parts[side+"Forearm"], parts[side+"Hand"],
                                                            parts["pelvis"], parts["chest"]), 0.105)
                        for start, end, body_radius in (("Thigh", "Shin", 0.05), ("Shin", "Foot", 0.04)):
                            gap = segment_distance(ball, ball, parts[side+start], parts[side+end]) - radius - body_radius
                            self.assertGreater(gap, 0.015)
                        self.assertLess(math.dist(f["landmarks"][side+"Grip"], bell["sockets"][side+"Grip"]), 0.001)

    def test_hip_thrust_sleeve_and_bar_ride_together_clear_of_both_thighs(self):
        p = program("hip-thrust")
        self.assertEqual(p.kit["bar-pad"]["visual"][0]["shape"], "rod")
        for f in p.frames(24):
            self.assertFalse(f["diagnostics"], f["diagnostics"])
            pos = f["positions"]
            pad, bar = (f["equipment"][name] for name in ("pad", "load"))
            self.assertEqual(pad["position"], bar["position"])
            self.assertEqual(pad["rotation"], bar["rotation"])
            self.assertLess(abs(bar["position"][2] - pos["pelvis"][2]), 0.05)
            for side in ("left", "right"):
                distance = segment_distance(
                    bar["sockets"]["leftGrip"], bar["sockets"]["rightGrip"],
                    pos[side + "Thigh"], pos[side + "Shin"],
                )
                self.assertGreater(distance, 0.06)

    def test_kettlebell_clean_racks_on_the_outside_of_the_working_forearm(self):
        p = program("kettlebell-clean")
        for f in p.frames(24):
            self.assertFalse(f["diagnostics"], f["diagnostics"])
            handle = f["equipment"]["bell"]["sockets"]["handle"]
            self.assertLess(math.dist(f["landmarks"]["leftGrip"], handle), 0.001)
        rack = next(i for i, phase in enumerate(p.doc["phases"]) if phase["id"] == "rack")
        f = p.segment(rack, 1)
        bell = f["equipment"]["bell"]
        ball = add(bell["position"], rotate(bell["rotation"], (0, -0.06175, 0)))
        arm = f["positions"]
        self.assertGreater(ball[0], arm["leftHand"][0])
        sleeve_gap = segment_distance(ball, ball, arm["leftForearm"], arm["leftHand"]) - 0.085
        self.assertLess(sleeve_gap, 0.055)
        self.assertGreater(sleeve_gap, 0.020)

    def test_crawling_and_burpee_knees_hover_above_the_floor(self):
        for name in ("bear-crawl", "burpee", "mountain-climber"):
            with self.subTest(name=name):
                p = program(name)
                for f in p.frames(24):
                    for side in ("left", "right"):
                        self.assertGreater(f["positions"][side+"Shin"][1], 0.045)
                if name == "burpee":
                    for t in (0, p.duration):
                        f = p.sample(t)
                        for side in ("left", "right"):
                            for landmark in ("Ball", "Heel"):
                                self.assertLess(abs(f["landmarks"][side+landmark][1]), 0.006)

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

    def test_squat_knees_follow_the_feet_across_stance_parameters(self):
        for name in ("bodyweight-squat", "squat", "front-squat", "goblet-squat", "smith-machine-squat"):
            recipe = load(ROOT / "exercises" / f"{name}.json")
            variants = [{}]
            if recipe.get("parameters"):
                variants += [
                    {"stance-width-m": width, "toe-out-deg": toe, "depth": depth}
                    for width in (0.21, 0.49)
                    for toe in (0, 23)
                    for depth in (0.55, 1.12)
                ]
            for params in variants:
                with self.subTest(name=name, parameters=params):
                    p = Program(recipe, params)
                    setup, deep = p.segment(0, 0), p.segment(0, 1)
                    self.assertFalse(deep["diagnostics"], deep["diagnostics"])
                    for side, sign in (("left", 1), ("right", -1)):
                        hip = deep["positions"][side+"Thigh"]
                        knee = deep["positions"][side+"Shin"]
                        ankle = deep["positions"][side+"Foot"]
                        self.assertLess(knee[1], hip[1])
                        direction = math.degrees(math.atan2(sign*(knee[0] - ankle[0]), knee[2] - ankle[2]))
                        self.assertLess(abs(direction - p.doc["start"]["stance"]["toeOut"]), 9)
                        for landmark in ("Ball", "Heel"):
                            key = side + landmark
                            self.assertLess(math.dist(setup["landmarks"][key], deep["landmarks"][key]), 0.002)

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
