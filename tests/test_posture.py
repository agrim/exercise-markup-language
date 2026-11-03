import math
import unittest

from eml import Error, Program
from eml.checks import check
from eml.kinematics import quaternion, rotate, unit
from eml.posture import bend, segment_distance, wrist


def recipe():
    return {
        "eml": "1.1",
        "id": "independent-stance",
        "title": "Independent",
        "start": {"pose": "standing"},
        "phases": [{"id": "move", "seconds": 1, "actions": []}],
        "repeat": {"mode": "once", "count": 1},
        "muscles": {"primary": [], "secondary": []},
    }


class SolvedConstraintTests(unittest.TestCase):
    def test_strict_absolute_wrist_and_legacy_dispatch(self):
        d = recipe()
        d["phases"][0]["detail"] = {"joints": {"leftHand": {"y": 170}}}
        p = Program(d)
        f = p.sample(1)
        issue = next(d for d in f["diagnostics"] if d["reason"] == "wrist-roll")
        self.assertEqual(
            (issue["phase"], issue["time"], issue["unit"], issue["effector"]),
            ("move", 1, "deg", "leftHand"),
        )
        self.assertGreater(issue["measured"], 160)
        self.assertAlmostEqual(issue["residual"], issue["measured"] - issue["limit"])
        self.assertRaisesRegex(Error, "wrist-roll", p.compile, 12)
        legacy = Program(dict(d, eml="1.0"))
        self.assertFalse(legacy.compile(12)["frames"][-1]["diagnostics"])
        d["constraints"] = []
        self.assertRaisesRegex(Error, "schema", Program, dict(d, eml="1.0"))

    def test_parent_roll_not_a_wrist_bend_and_forearm_pronation_not_elbow_bend(self):
        p = Program(recipe())
        r = p.solver.rig
        shaft = unit(r.offsets[r.index["leftHand"]])
        q = (*[v * math.sin(0.7) for v in shaft], math.cos(0.7))
        signed, swing = bend(q, r.offsets[r.index["leftHand"]], (1, 0, 0))
        self.assertAlmostEqual(signed, 0)
        self.assertAlmostEqual(swing, 0)
        tilt, roll = wrist(q, shaft)
        self.assertAlmostEqual(tilt, 0)
        self.assertAlmostEqual(roll, math.degrees(1.4))
        self.assertEqual(wrist(q, shaft)[1], wrist(tuple(-v for v in q), shaft)[1])
        d = recipe()
        d["phases"][0]["detail"] = {"joints": {"leftForearm": {"y": 65}}}
        self.assertFalse(
            [
                x
                for x in Program(d).sample(0.9)["diagnostics"]
                if x["reason"].startswith("wrist")
            ]
        )

    def test_backwards_knee_and_forearm_after_solving(self):
        d = recipe()
        d["phases"][0]["detail"] = {
            "joints": {"leftShin": {"x": -65}, "rightForearm": {"x": 85}}
        }
        f = Program(d).sample(1)
        ids = {x["effector"] for x in f["diagnostics"] if x["reason"] == "hinge-bend"}
        self.assertEqual(ids, {"leftShin", "rightForearm"})
        d["phases"][0]["detail"] = {
            "joints": {"leftShin": {"x": 60}, "rightForearm": {"x": -80}}
        }
        self.assertFalse(Program(d).sample(1)["diagnostics"])

    def test_orientation_in_world_or_another_joint_and_phase_selection(self):
        d = recipe()
        d["phases"].append(
            {"id": "look", "seconds": 1, "actions": [{"use": "turn-head"}]}
        )
        rule = {
            "kind": "orientation",
            "phases": ["look"],
            "joint": "head",
            "axis": [0, 0, 2],
            "direction": [0, 0, 1],
            "relativeTo": {"joint": "chest"},
            "maxAngle": 15,
        }
        d["constraints"] = [rule]
        p = Program(d)
        self.assertFalse(p.sample(0.5)["diagnostics"])
        issue = p.sample(2)["diagnostics"][0]
        self.assertEqual(issue["reason"], "joint-direction")
        self.assertAlmostEqual(issue["measured"], 45)
        rule.update(
            direction=list(rotate(quaternion([0, 45, 0]), [0, 0, 1])), maxAngle=0.1
        )
        self.assertFalse(Program(d).sample(2)["diagnostics"])
        rule["axis"] = [0, 0, 0]
        self.assertRaisesRegex(Error, "nonzero", Program, d)

    def test_item_direction_reference_and_unknown_references(self):
        d = recipe()
        d["equipment"] = [
            {
                "id": "marker",
                "kind": "flat-bench",
                "position": [1, 1, 1],
                "rotation": [0, 90, 0],
            }
        ]
        d["constraints"] = [
            {
                "kind": "orientation",
                "joint": "head",
                "axis": [0, 0, 1],
                "direction": [-1, 0, 0],
                "relativeTo": {"item": "marker"},
                "maxAngle": 0.01,
            }
        ]
        self.assertFalse(Program(d).sample(0)["diagnostics"])
        d["constraints"][0]["relativeTo"] = {"item": "absent"}
        self.assertRaisesRegex(Error, "Unknown equipment instance", Program, d)
        d["constraints"][0]["phases"] = ["missing"]
        self.assertRaisesRegex(Error, "unknown-phase", Program, d)

    def test_swept_shaft_crosses_body_despite_clear_endpoints(self):
        d = recipe()
        d["equipment"] = [{"id": "bar", "kind": "barbell", "position": [0, 1.05, 0.35]}]
        d["phases"][0]["items"] = {"bar": {"position": [0, 1.05, -0.35]}}
        d["constraints"] = [
            {
                "kind": "clearance",
                "item": "bar",
                "from": "leftGrip",
                "to": "rightGrip",
                "radius": 0.015,
                "bodyFrom": "pelvis",
                "bodyTo": "chest",
                "bodyRadius": 0.06,
            }
        ]
        p = Program(d)
        self.assertFalse(p.sample(0)["diagnostics"])
        self.assertFalse(p.sample(1)["diagnostics"])
        issues = p.sample(0.5)["diagnostics"]
        explicit = next(i for i in issues if i["path"] == "/constraints/0")
        self.assertEqual(explicit["reason"], "equipment-clearance")
        self.assertLess(explicit["measured"], -0.04)
        self.assertTrue(
            any(
                i["code"] == "equipment-clearance" and i["unit"] == "m"
                for i in check(p)["issues"]
            )
        )
        self.assertRaisesRegex(Error, "equipment-clearance", p.compile, 12)

    def test_support_uses_finite_rotated_face_not_unbounded_plane(self):
        d = recipe()
        heel = Program(d).sample(0)["landmarks"]["leftHeel"]
        turn = [0, 0, 25]
        local = rotate(quaternion(turn), [0, 0.44, 0])
        d["equipment"] = [
            {
                "id": "seat",
                "kind": "flat-bench",
                "position": [a - b for a, b in zip(heel, local)],
                "rotation": turn,
            }
        ]
        d["constraints"] = [
            {
                "kind": "support",
                "landmark": "leftHeel",
                "surface": {"item": "seat", "part": 0},
                "min": -0.003,
                "max": 0.003,
                "edgeTolerance": 0.005,
            }
        ]
        self.assertFalse(Program(d).compile(12)["frames"][0]["diagnostics"])
        d["equipment"][0]["position"] = [
            a + b
            for a, b in zip(
                d["equipment"][0]["position"], rotate(quaternion(turn), [1, 0, 0])
            )
        ]
        issues = Program(d).sample(0.5)["diagnostics"]
        self.assertEqual([i["reason"] for i in issues], ["support-edge"])
        d["constraints"][0]["surface"] = "floor"
        d["constraints"][0]["offset"] = [0, -0.025, 0]
        self.assertEqual(
            Program(d).sample(0)["diagnostics"][0]["reason"], "support-gap"
        )

    def test_unknown_socket_and_degenerate_segment_distance(self):
        self.assertAlmostEqual(
            segment_distance((0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 0, 0)), 1
        )
        self.assertAlmostEqual(
            segment_distance((0, 0, 0), (2, 0, 0), (1, -1, 0), (1, 1, 0)), 0
        )
        self.assertAlmostEqual(
            segment_distance((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)), 1
        )
        d = recipe()
        d["equipment"] = [{"id": "weight", "kind": "barbell"}]
        d["constraints"] = [
            {
                "kind": "clearance",
                "item": "weight",
                "from": "made-up",
                "to": [0, 0, 0],
                "radius": 0,
                "bodyFrom": "chest",
                "bodyTo": "head",
                "bodyRadius": 0,
            }
        ]
        self.assertRaisesRegex(Error, "Unknown equipment socket", Program, d)

    def test_travelling_repetition_checks_fixed_equipment_in_later_cycles(self):
        d = recipe()
        d["repeat"] = {"mode": "loop", "count": 3, "travel": [0, 0, 0.5]}
        d["phases"][0]["detail"] = {"root": [0, 0, 0.5]}
        d["equipment"] = [{"id": "bar", "kind": "barbell", "position": [0, 1.05, 1.12]}]
        p = Program(d)
        self.assertFalse(p.segment(0, 0.5)["diagnostics"])
        r = check(p)
        later = [i for i in r["issues"] if i["code"] == "equipment-clearance"]
        self.assertTrue(later)
        self.assertTrue(all(i["cycle"] > 0 for i in later))
        self.assertRaisesRegex(Error, "equipment-clearance", p.compile, 12)

    def test_parameters_bind_into_enforceable_constraints(self):
        d = recipe()
        d["parameters"] = {"cap": {"default": 40, "min": 5, "max": 90}}
        d["constraints"] = [
            {
                "kind": "hinge",
                "joint": "bothForearm",
                "axis": [1, 0, 0],
                "min": -180,
                "max": 180,
                "maxSwing": {"param": "cap"},
            }
        ]
        d["phases"][0]["detail"] = {"joints": {"leftForearm": {"z": 30}}}
        self.assertFalse(Program(d).sample(1)["diagnostics"])
        diagnostics = Program(d, {"cap": 5}).sample(1)["diagnostics"]
        self.assertTrue(
            any(
                x["reason"] == "hinge-off-axis" and x["path"] == "/constraints/0"
                for x in diagnostics
            )
        )

    def test_legacy_registry_resolves_published_pose_not_revised_definition(self):
        import json
        import shutil
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from eml import data

        old = recipe()
        old["eml"] = "1.0"
        old["phases"][0]["actions"] = [{"use": "turn-head"}]
        with TemporaryDirectory() as td:
            root = Path(td)
            for sub in ["schema", "anatomy", "compat/1.0/library", "library"]:
                # The test needs the rig metadata, not its mesh buffers.
                if sub == "anatomy":
                    (root / sub).mkdir()
                    shutil.copyfile(
                        data.ROOT / sub / "model.json", root / sub / "model.json"
                    )
                else:
                    shutil.copytree(data.ROOT / sub, root / sub)
            path = root / "library/base.json"
            current = json.loads(path.read_text())
            current["motions"]["turn-head"]["joints"]["head"] = [0, -25, 0]
            path.write_text(json.dumps(current))
            try:
                with patch.object(data, "ROOT", root):
                    data.registry.cache_clear()
                    legacy = Program(old).sample(1)["rotations"]["head"]
                    current = Program(dict(old, eml="1.1")).sample(1)["rotations"][
                        "head"
                    ]
                    self.assertAlmostEqual(legacy[1], math.sin(math.radians(45) / 2))
                    self.assertAlmostEqual(current[1], math.sin(math.radians(-25) / 2))
            finally:
                data.registry.cache_clear()

    def test_interface_exports_the_requested_vocabulary_and_version(self):
        from eml import interface

        current = interface()
        legacy = interface("1.0")
        self.assertEqual(current["eml"], "1.1")
        self.assertEqual(legacy["eml"], "1.0")
        self.assertIn("constraints", current["schema"]["properties"])
        self.assertNotIn("constraints", legacy["schema"]["properties"])
        self.assertIn("assistance-knee-pad", current["equipment"])
        self.assertNotIn("assistance-knee-pad", legacy["equipment"])
        self.assertNotIn("postureProfile", legacy)
        self.assertTrue(current["compatibleSetups"]["setups"])
        self.assertNotIn("compatibleSetups", legacy)
        self.assertRaisesRegex(Error, "Unsupported EML version", interface, "1")
