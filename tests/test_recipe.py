import json
import unittest

from eml import Error, Program, Recipe, load
from eml.data import ROOT


class RecipeTests(unittest.TestCase):
    def test_chain_matches_published_legacy_recipe_and_compiled_clip(self):
        document = load(ROOT / "examples/paused-goblet-look-left.json")
        depth = {"param": "depth"}
        recipe = (
            Recipe(document["id"], document["title"], version="1.0")
            .configure(
                instructions=document["instructions"],
                equipment=document["equipment"],
                contacts=document["contacts"],
                camera=document["camera"],
                parameters=document["parameters"],
            )
            .start("goblet-hold", stance=document["start"]["stance"])
            .move("squat-upright", 1.7, id="descend", amount=depth)
            .phase(
                {"param": "pause"},
                id="pause-and-look",
                detail={"joints": {"head": {"y": {"param": "turn"}}}},
            )
            .action("squat-upright", depth)
            .return_to_start(1.7, id="stand")
            .muscles(**document["muscles"])
            .repeat(5)
        )
        self.assertEqual(recipe.build(), document)
        self.assertEqual(json.loads(recipe.to_json()), document)
        overrides = {"depth": 0.66, "pause": 0.7, "turn": 25}
        program = Program(recipe, overrides)
        self.assertEqual(program.compile(12), Program(document, overrides).compile(12))
        self.assertEqual(recipe.build()["phases"][0]["actions"][0]["amount"], depth)

    def test_existing_document_can_be_extended_without_altering_source(self):
        document = load(ROOT / "examples/traveling-reach.json")
        recipe = Recipe.from_document(document)
        self.assertEqual(recipe.build(), document)
        self.assertEqual(Program(recipe).compile(6), Program(document).compile(6))

        recipe.move("glide", 0.5)
        extended = recipe.build()
        self.assertEqual(extended["phases"][:-1], document["phases"])
        self.assertEqual(len(document["phases"]), 1)
        document["definitions"]["motions"]["glide"]["root"][2] = 0.5
        self.assertEqual(recipe.build(), extended)

        with self.assertRaises(Error) as error:
            Recipe.from_document({**document, "phases": []})
        self.assertEqual(error.exception.code, "schema")
        self.assertEqual(error.exception.path, "/phases")

    def test_actions_compose_within_a_phase_and_moves_precede_next_endpoint(self):
        recipe = Recipe("curl-with-glance", "Curl with a glance")
        self.assertIs(recipe.move("bend-elbows", 1, id="phase-2", amount=0.8), recipe)
        recipe.phase(1).action("bend-elbows", 0.8).action("turn-head", 0.25)
        recipe.move("turn-head", 1, amount=0.25).return_to_start(1, id="stand")
        recipe.muscles("biceps", "forearms")

        program = Program(recipe)
        self.assertEqual(program.doc["start"], {"pose": "standing"})
        self.assertEqual(program.repeat, {"mode": "once", "count": 1})
        self.assertEqual(
            program.doc["muscles"], {"primary": ["biceps"], "secondary": ["forearms"]}
        )
        frames = [program.sample(t) for t in range(5)]
        self.assertEqual(len({frame["phase"] for frame in frames}), 4)
        setup, curl, combined, turn, stand = [frame["rotations"] for frame in frames]
        self.assertNotEqual(curl["leftForearm"], setup["leftForearm"])
        self.assertEqual(curl["leftForearm"], combined["leftForearm"])
        self.assertNotEqual(combined["head"], curl["head"])
        self.assertEqual(turn["head"], combined["head"])
        self.assertEqual(turn["leftForearm"], setup["leftForearm"])
        self.assertEqual(stand, setup)

    def test_fragments_are_copied_and_empty_phase_overrides_survive(self):
        contacts = [{"effector": "leftPalm", "target": "start"}]
        actions = [{"use": "bend-elbows", "amount": 0.5}]
        recipe = (
            Recipe("changing-contacts", "Changing contacts")
            .configure(
                contacts=contacts, rootAnchor={"joint": "pelvis", "target": "start"}
            )
            .phase(1, actions=actions)
            .return_to_start(1, ease="linear", contacts=[], rootAnchor=None)
        )
        contacts[0]["target"] = "floor"
        actions[0]["amount"] = 1
        document = recipe.build()
        self.assertEqual(document["contacts"][0]["target"], "start")
        self.assertEqual(document["phases"][0]["actions"][0]["amount"], 0.5)

        program = Program(recipe)
        inherited, released = program.doc["phases"]
        self.assertNotIn("contacts", inherited)
        self.assertEqual(program.effective_contacts(inherited), document["contacts"])
        self.assertEqual(program.effective_contacts(released), [])
        self.assertNotIn("rootAnchor", inherited)
        self.assertIsNone(released["rootAnchor"])
        self.assertEqual(released["ease"], "linear")

        document["phases"].clear()
        recipe.action("turn-head").return_to_start(0.5)
        self.assertEqual(released["actions"], [])
        self.assertEqual(len(program.doc["phases"]), 2)
        self.assertEqual(len(recipe.build()["phases"]), 3)

    def test_return_rejects_endpoint_overrides_without_appending_a_phase(self):
        recipe = Recipe("return-overrides", "Return overrides").move("bend-elbows", 1)
        document = recipe.build()
        for field, value in {"actions": [], "detail": {}}.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(Error, r"\.phase\(\)") as error:
                    recipe.return_to_start(1, **{field: value})
                self.assertEqual(error.exception.path, f"/phases/1/{field}")
                self.assertEqual(recipe.build(), document)

    def test_invalid_chains_get_builder_or_standard_diagnostics(self):
        recipe = Recipe("invalid-movement", "Invalid movement")
        with self.assertRaises(Error) as error:
            recipe.action("bend-elbows")
        self.assertEqual(error.exception.code, "no-phase")

        with self.assertRaisesRegex(Error, r"Add motions with \.action\(\)"):
            recipe.move("bend-elbows", 1, actions=[])
        recipe.move("unregistered-motion", 1)
        self.assertEqual(len(recipe.build()["phases"]), 1)
        with self.assertRaises(Error) as chained:
            Program(recipe)
        with self.assertRaises(Error) as plain:
            Program(recipe.build())
        self.assertEqual(chained.exception.as_dict(), plain.exception.as_dict())
        self.assertEqual(chained.exception.code, "unknown-motion")

    def test_python_fragments_must_serialize_as_portable_json(self):
        recipe = Recipe("duplicate-items", "Duplicate item keys").phase(
            1, items={1: {}, "1": {}}
        )
        with self.assertRaises(Error) as error:
            recipe.to_json()
        self.assertEqual(error.exception.code, "invalid-json")
        self.assertEqual(error.exception.path, "/phases/0/items")

        recipe = Recipe("invalid-timing", "Invalid timing").phase(float("nan"))
        with self.assertRaisesRegex(Error, "invalid-json"):
            Program(recipe)
