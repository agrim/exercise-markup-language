import tempfile
import unittest
from math import dist
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from eml import Error, Program, load
from eml.checks import check
from eml.data import ROOT
from eml.native import compile_pack


def minimal():
    return {
        "eml": "1.0",
        "id": "any-author-id",
        "title": "Test pose",
        "start": {"pose": "standing"},
        "phases": [
            {"id": "lift", "seconds": 1, "actions": [{"use": "bend-elbows"}]},
            {"id": "return", "seconds": 1, "actions": []},
        ],
        "repeat": {"mode": "loop", "count": 2},
        "muscles": {"primary": ["biceps"], "secondary": []},
    }


class StandardTests(unittest.TestCase):
    def test_schema_and_published_registries(self):
        refs = Registry()
        for path in (ROOT / "schema").glob("*.json"):
            spec = load(path)
            Draft202012Validator.check_schema(spec)
            refs = refs.with_resource(spec["$id"], Resource.from_contents(spec))
        for path in (ROOT / "library").glob("*.json"):
            name = "equipment" if path.stem == "equipment" else "library"
            version = "v1" if name == "equipment" else "v1.1"
            spec = load(ROOT / "schema" / f"{name}-{version}.schema.json")
            Draft202012Validator(spec, registry=refs).validate(load(path))
        p = Program(minimal())
        for pose in p.poses:
            p.pose(pose)
        for name in p.motions:
            p.action(name, 1, [[0, 0, 0], {}])

    def test_catalog_can_grow_while_preserving_original_108(self):
        original = load(ROOT / "tests/fixtures/catalog-baseline.json")["exercises"]
        self.assertEqual(len(original), 108)
        for id_, row in original.items():
            doc = load(ROOT / "exercises" / (id_ + ".json"))
            self.assertEqual(doc["id"], id_)
            self.assertEqual(doc["title"], row["title"])
            self.assertEqual(
                doc["muscles"], {k: row[k] for k in ("primary", "secondary")}
            )

    def test_portable_known_answer_vector(self):
        fixture = load(ROOT / "tests/fixtures/portable-vector.json")
        program = Program(fixture["document"])
        for row in fixture["expected"]:
            actual = program.sample(row["time"])["rotations"][row["joint"]]
            self.assertLess(
                min(
                    dist(actual, row["rotation"]),
                    dist(actual, [-x for x in row["rotation"]]),
                ),
                fixture["tolerance"],
            )

    def test_id_independence_and_known_quaternion(self):
        a = minimal()
        b = {**a, "id": "independent-new-exercise"}
        one, two = (Program(x).sample(1) for x in (a, b))
        self.assertEqual(one["positions"], two["positions"])
        self.assertLess(
            dist(one["rotations"]["leftForearm"], [-(2**-0.5), 0, 0, 2**-0.5]), 1e-8
        )
        self.assertLess(
            dist(one["rotations"]["rightForearm"], one["rotations"]["leftForearm"]),
            1e-8,
        )

    def test_partial_override_and_composition(self):
        a = minimal()
        a["definitions"] = {
            "motions": {
                "curl-and-turn": {
                    "actions": [
                        {"use": "bend-elbows", "amount": 0.5},
                        {"use": "turn-head"},
                    ]
                }
            }
        }
        a["phases"][0]["actions"] = [{"use": "curl-and-turn"}]
        a["phases"][0]["detail"] = {"joints": {"head": {"x": 12}}}
        p = Program(a)
        self.assertEqual(p.targets[1][1]["head"], [12, 45, 0])
        self.assertEqual(p.targets[1][1]["leftForearm"], [-45, 0, 0])
        self.assertEqual(p.targets[1][1]["rightForearm"], [-45, 0, 0])

    def test_relative_stance_matches_explicit_metric_stance(self):
        a = minimal()
        a["start"]["stance"] = {
            "width": {"of": "shoulder-width", "factor": 1.25},
            "toeOut": "slight-out",
        }
        metric = Program(a)
        b = {**a, "start": {"pose": "standing", "stance": {"width": 0.4, "toeOut": 12}}}
        self.assertLess(
            dist(
                metric.sample(0.4)["landmarks"]["leftHeel"],
                Program(b).sample(0.4)["landmarks"]["leftHeel"],
            ),
            1e-8,
        )

    def test_custom_parameters_modify_the_pose_and_timing(self):
        doc = load(ROOT / "examples/paused-goblet-look-left.json")
        a, b = (
            Program(doc, {"depth": 0.52}),
            Program(doc, {"depth": 0.92, "pause": 2, "turn": 25}),
        )
        self.assertAlmostEqual(b.duration - a.duration, 1)
        self.assertGreater(
            a.sample(1.7)["positions"]["pelvis"][1]
            - b.sample(1.7)["positions"]["pelvis"][1],
            0.05,
        )
        for p in (a, b):
            self.assertEqual(check(p)["issues"], [])
            f = p.segment(1, 1)
            self.assertLess(
                dist(
                    f["landmarks"]["leftGrip"],
                    f["equipment"]["bell"]["sockets"]["leftGrip"],
                ),
                0.012,
            )
        with self.assertRaisesRegex(Error, "parameter-range"):
            Program(doc, {"depth": 1.2})

    def test_contacts_must_be_possible_and_release_must_be_continuous(self):
        d = minimal()
        d["contacts"] = [{"effector": "leftPalm", "target": {"point": [0, 5, 0]}}]
        self.assertIn(
            "unreachable-contact", [x["code"] for x in check(Program(d))["issues"]]
        )
        d = minimal()
        d["phases"][1]["contacts"] = [
            {"effector": "rightPalm", "target": {"point": [-0.2, 1.3, 0.3]}}
        ]
        self.assertIn(
            "discontinuous-contact", [x["code"] for x in check(Program(d))["issues"]]
        )
        self.assertEqual(
            check(Program(load(ROOT / "examples/diagonal-reach.json")))["issues"], []
        )

    def test_root_anchor_retains_a_knee_pivot_through_interpolation(self):
        d = minimal()
        d["rootAnchor"] = {"joint": "leftShin", "target": "start"}
        d["phases"][0]["detail"] = {"joints": {"leftThigh": {"x": -30}}}
        p = Program(d)
        expected = p.sample(0)["positions"]["leftShin"]
        for t in (0.25, 0.5, 1, 1.3):
            self.assertLess(dist(p.sample(t)["positions"]["leftShin"], expected), 1e-7)
        self.assertGreater(dist(p.sample(1)["root"], [0, 0, 0]), 0.1)

    def test_repeat_travel_hold_and_once(self):
        p = Program(load(ROOT / "examples/traveling-reach.json"))
        self.assertAlmostEqual(p.playback(4)["root"][2], 1)
        self.assertEqual(p.playback(9)["root"], p.playback(4)["root"])
        d = minimal()
        d["repeat"]["mode"] = "hold"
        self.assertIn("moving-hold", [x["code"] for x in check(Program(d))["issues"]])
        d["phases"] = d["phases"][:1]
        d["repeat"] = {"mode": "once", "count": 1}
        self.assertEqual(check(Program(d))["issues"], [])

    def test_closed_symbols_version_cycles_fields_and_duplicate_json(self):
        d = minimal()
        for patch, code in [
            ({"eml": "2.0"}, "schema"),
            ({"notes_unrecognized": True}, "schema"),
            ({"start": {"pose": "phantom"}}, "unknown-pose"),
            (
                {"definitions": {"motions": {"spin": {"actions": [{"use": "spin"}]}}}},
                "cyclic-definition",
            ),
        ]:
            with self.subTest(code=code), self.assertRaisesRegex(Error, code):
                Program({**d, **patch})
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text('{"x":2,"x":3}')
            with self.assertRaisesRegex(Error, "duplicate-key"):
                load(path)

    def test_asset_licence_mesh_and_native_pack(self):
        r = ROOT / "anatomy"
        m = load(r / "model.json")
        self.assertEqual((r / "vertices.bin").stat().st_size, m["vertexCount"] * 40)
        self.assertEqual((r / "indices.bin").stat().st_size, m["indexCount"] * 4)
        self.assertIn("Attribution-ShareAlike", (r / "ATTRIBUTION.md").read_text())
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "pack"
            compile_pack([Program(minimal())], out, 4)
            data = (out / "tracks/any-author-id.bin").read_bytes()
            self.assertEqual(data[:4], b"EXM1")
            self.assertEqual(
                load(out / "motions.json")["exercises"][0]["id"], "any-author-id"
            )
            with self.assertRaisesRegex(Error, "output-exists"):
                compile_pack([Program(minimal())], out, 4)
