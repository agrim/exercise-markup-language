import unittest
from math import dist

from eml import Error, Program, Recipe, load
from eml.data import ROOT
from examples.fluent_incline_push_up import recipe as incline_push_up


class AdvancedRecipeTests(unittest.TestCase):
    def test_fluent_incline_push_up_recreates_catalog_motion(self):
        recipe = incline_push_up()
        document = load(ROOT / "exercises/incline-push-up.json")
        self.assertEqual(recipe.build(), document)
        clip = Program(recipe).compile(12)
        self.assertEqual(clip, Program(document).compile(12))
        for frame in clip["frames"]:
            for palm in ("leftPalm", "rightPalm"):
                socket = frame["equipment"]["platform"]["sockets"][palm]
                self.assertLess(dist(frame["landmarks"][palm], socket), 0.002)

    def test_local_definitions_and_joint_axes_accept_parameter_references(self):
        uri = load(ROOT / "schema/exercise-v1.1.schema.json")["$id"]
        recipe = (
            Recipe("custom-curl", "Custom curl")
            .schema_uri(uri)
            .parameter("effort", default=0.7, minimum=0.5, maximum=1)
            .parameter("tempo", default=1, minimum=0.5, maximum=2)
            .define_pose("curl-setup", extends="standing", fixed_points=["leftHeel"])
            .pose_joint("curl-setup", "head", x=5)
            .pose_joint("curl-setup", "head", y=6)
            .define_motion("curl-and-turn", root=[0, 0, 0], fixed_points=["rightHeel"])
            .motion_action("curl-and-turn", "bend-elbows", Recipe.param("effort"))
            .motion_joint("curl-and-turn", "head", y=3)
            .start("curl-setup")
            .stance("shoulder-width", toe_out="forward", factor=1.1)
            .start_joint("head", angles=[1, 2, 3])
            .start_joint("head", y=4)
            .move("curl-and-turn", Recipe.param("tempo"), id="curl")
            .phase_joint("head", x=4)
            .phase_joint("head", z=-2)
            .return_to_start(1, id="return")
        )
        document = recipe.build()
        self.assertEqual(document["$schema"], uri)
        pose = document["definitions"]["poses"]["curl-setup"]
        self.assertEqual(pose["joints"]["head"], {"x": 5, "y": 6})
        self.assertEqual(document["phases"][0]["seconds"], {"param": "tempo"})
        self.assertEqual(
            document["start"]["stance"],
            {"width": {"of": "shoulder-width", "factor": 1.1}, "toeOut": "forward"},
        )
        program = Program(recipe, {"effort": 0.6, "tempo": 1.4})
        self.assertAlmostEqual(program.duration, 2.4)
        self.assertEqual(program.start[1]["head"], [1, 4, 3])
        self.assertEqual(program.targets[1][1]["head"], [4, 7, -2])
        self.assertAlmostEqual(program.targets[1][1]["leftForearm"][0], -54)

    def test_item_endpoint_fields_merge_and_connections_follow_both_drivers(self):
        recipe = (
            Recipe("cable-path", "Cable path")
            .equipment("marker", "secure-band-anchor", position=[2, 1, 0])
            .socket("marker", "anchor", [0, 0.1, 0])
            .equipment(
                "handle",
                "cable-handle",
                follow_joint="rightHand",
                grip=True,
                offset=[0, 0.02, 0.03],
                rotation=[0, 10, 0],
            )
            .connect("cable", "marker", "anchor", "handle", "center")
            .phase(1, id="arc")
            .ease("linear")
            .phase_item("marker", position=[2, 1, 0.4])
            .phase_item("marker", rotation=[0, 45, 0], control_position=[2, 1.4, 0.2])
            .phase_item("handle", offset=[0, 0.08, 0.03])
            .return_to_start(1)
        )
        program = Program(recipe)
        clip = program.compile(8)
        connection = {
            "kind": "cable",
            "from": {"item": "marker", "socket": "anchor"},
            "to": {"item": "handle", "socket": "center"},
        }
        self.assertEqual(clip["connections"], [connection])
        initial, middle, final = [program.sample(t)["equipment"] for t in (0, 0.5, 1)]
        self.assertLess(dist(initial["marker"]["sockets"]["anchor"], [2, 1.1, 0]), 1e-9)
        self.assertLess(dist(middle["marker"]["position"], [2, 1.2, 0.2]), 1e-9)
        self.assertNotEqual(initial["marker"]["rotation"], final["marker"]["rotation"])
        shift = dist(initial["handle"]["position"], final["handle"]["position"])
        self.assertAlmostEqual(shift, 0.06)
        self.assertEqual(program.sample(2)["equipment"], initial)

    def test_scoped_contacts_supports_and_anchor_can_replace_or_inherit(self):
        recipe = (
            Recipe("scoped-options", "Scoped options")
            .phase(1, id="pinned")
            .phase_root([0, 0, 0.04])
            .phase(1, id="released")
            .phase_root([0, 0, 0.04])
            .clear_contacts(phase=True)
            .clear_supports(phase=True)
            .clear_root_anchor(phase=True)
            .muscles("triceps", phase=True)
            .phase(1, id="other-support")
            .contact("rightHeel", "floor", phase=True)
            .support("rightFoot", "floor", phase=True)
            .phase(1, id="inherit")
            .contact("leftHeel")
            .support("bothFoot", "floor")
            .root_anchor("pelvis")
            .muscles("biceps", "forearms")
            .side_focus(["biceps"])
            .focus_interval("left", 0, 0.5)
            .focus_interval("right", 0.5, 1)
        )
        program = Program(recipe)
        effective = [program.effective_contacts(p) for p in program.doc["phases"]]
        self.assertEqual(
            effective,
            [
                [{"effector": "leftHeel", "target": "start"}],
                [],
                [{"effector": "rightHeel", "target": "floor"}],
                [{"effector": "leftHeel", "target": "start"}],
            ],
        )
        self.assertAlmostEqual(program.sample(1)["root"][2], 0)
        frame = program.sample(2)
        self.assertAlmostEqual(frame["root"][2], 0.04)
        self.assertEqual(frame["supports"], [])
        self.assertEqual(frame["muscles"], {"primary": ["triceps"], "secondary": []})
        self.assertEqual(
            program.sample(3)["supports"], [{"body": "rightFoot", "surface": "floor"}]
        )
        self.assertEqual(
            program.sample(4)["supports"], [{"body": "bothFoot", "surface": "floor"}]
        )
        self.assertEqual(program.focus["groups"], ["biceps"])
        self.assertEqual(
            program.focus["intervals"],
            [
                {"side": "left", "start": 0, "end": 0.5},
                {"side": "right", "start": 0.5, "end": 1},
            ],
        )

    def test_named_constraint_methods_feed_strict_compile_and_diagnostics(self):
        recipe = (
            Recipe("measured-turn", "Measured turn")
            .equipment("marker", "secure-band-anchor", position=[2, 1, 0])
            .parameter("view-cap", default=50, minimum=10, maximum=90)
            .hinge_constraint(
                "bothForearm",
                [1, 0, 0],
                child="bothHand",
                minimum=-160,
                maximum=20,
                max_swing=20,
            )
            .orientation_constraint(
                "head",
                [0, 0, 1],
                [0, 0, 1],
                relative_joint="chest",
                max_angle=Recipe.param("view-cap"),
                phases="look",
            )
            .clearance_constraint(
                "marker",
                "anchor",
                [0, 0, 0],
                radius=0.01,
                body_from="pelvis",
                body_to="chest",
                body_radius=0.06,
                minimum=0.02,
            )
            .support_constraint(
                "leftHeel", minimum=-0.03, maximum=0.03, edge_tolerance=0.02
            )
            .phase(1, id="setup")
            .move("turn-head", 1, id="look")
        )
        constraints = recipe.build()["constraints"]
        kinds = [rule["kind"] for rule in constraints]
        self.assertEqual(kinds, ["hinge", "orientation", "clearance", "support"])
        self.assertEqual(constraints[1]["phases"], ["look"])
        self.assertEqual(len(Program(recipe).compile(8)["frames"]), 17)
        limited = Program(recipe, {"view-cap": 15})
        self.assertFalse(limited.sample(0.5)["diagnostics"])
        with self.assertRaisesRegex(Error, "joint-direction") as error:
            limited.compile(8)
        self.assertEqual(error.exception.path, "/constraints/1")

    def test_scope_errors_and_version_restrictions_use_eml_diagnostics(self):
        recipe = Recipe("legacy-example", "Legacy example", version="1.0")
        with self.assertRaisesRegex(Error, "no-phase"):
            recipe.contact("leftHeel", phase=True)

        recipe.phase(1).support_constraint("leftHeel", minimum=-0.03, maximum=0.03)
        with self.assertRaisesRegex(Error, "schema"):
            Program(recipe)
