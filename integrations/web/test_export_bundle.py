import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from export_bundle import DEFAULT_ROOT, compiler, export_bundle, mapping_entries, source_path


class EMLWebExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.root = Path(cls.workspace.name)
        cls.mapping = cls.root / "mapping.json"
        cls.mapping.write_text(json.dumps({"format": "eml-web-map-v1", "entries": [
            {"exercise_id": "0017", "recipe": "examples/diagonal-reach.json"},
            {"exercise_id": "host:plank", "recipe": "exercises/plank.json",
             "parameters": {"hold-seconds": 0.5}},
        ]}), encoding="utf-8")
        cls.output = cls.root / "actual-bundle"
        # Exercise the public CLI and real reference compiler, including both versions.
        subprocess.run([sys.executable, str(Path(__file__).with_name("export_bundle.py")),
                        "--mapping", str(cls.mapping), "--out", str(cls.output), "--fps", "1"],
                       check=True, capture_output=True, text=True)
        cls.manifest = json.loads((cls.output / "manifest.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def test_real_cli_preserves_identity_source_and_parameterized_clip(self):
        entries = self.manifest["entries"]
        self.assertEqual([item["exercise_id"] for item in entries], ["0017", "host:plank"])
        for entry, source in zip(entries, ["examples/diagonal-reach.json", "exercises/plank.json"]):
            self.assertEqual((self.output / entry["recipe"]).read_bytes(),
                             (DEFAULT_ROOT / source).read_bytes())
            clip = json.loads((self.output / entry["clip"]).read_text())
            self.assertEqual(clip["id"], entry["eml_id"])
            self.assertEqual(clip["eml"], entry["eml_version"])
            self.assertTrue(clip["frames"])
            self.assertEqual(clip["frames"][0]["time"], 0)
            self.assertEqual(clip["frames"][-1]["time"], clip["duration"])
            self.assertTrue(all(not frame["diagnostics"] for frame in clip["frames"]))
            self.assertEqual(hashlib.sha256((self.output / entry["clip"]).read_bytes()).hexdigest(),
                             entry["clip_sha256"])
        hold = json.loads((self.output / entries[1]["clip"]).read_text())
        self.assertEqual(hold["duration"], 0.5)
        self.assertEqual(hold["repeat"], {"mode": "hold", "count": 1})
        self.assertEqual(entries[1]["parameters"], {"hold-seconds": 0.5})

    def test_versioned_equipment_and_asset_notices_are_copied_unchanged(self):
        assets = self.manifest["assets"]
        self.assertEqual(set(assets["equipment"]), {"1.0", "1.1"})
        for version, source in [("1.0", "compat/1.0/library/equipment.json"),
                                ("1.1", "library/equipment.json")]:
            self.assertEqual((self.output / assets["equipment"][version]).read_bytes(),
                             (DEFAULT_ROOT / source).read_bytes())
        for key, source in [("license", "LICENSE"), ("attribution", "anatomy/ATTRIBUTION.md")]:
            self.assertEqual((self.output / assets[key]).read_bytes(), (DEFAULT_ROOT / source).read_bytes())
        for name, digest in self.manifest["asset_sha256"].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), digest)

    def test_existing_output_is_not_modified(self):
        before = (self.output / "manifest.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            export_bundle(self.mapping, self.output)
        self.assertEqual((self.output / "manifest.json").read_bytes(), before)

    def test_compile_is_strict_and_failure_never_publishes_partial_output(self):
        Program, _ = compiler(DEFAULT_ROOT)
        output = self.root / "rejected-compile"
        with patch.object(Program, "compile", side_effect=ValueError("diagnostic rejection")) as compile_call:
            with self.assertRaisesRegex(ValueError, "diagnostic rejection"):
                export_bundle(self.mapping, output)
        compile_call.assert_called_once_with(12, strict=True)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob(".eml-web-*")))

    def test_source_edit_during_compile_cannot_change_captured_recipe(self):
        Program, load = compiler(DEFAULT_ROOT)
        source = self.root / "editable-recipe.json"
        original_bytes = (DEFAULT_ROOT / "exercises/plank.json").read_bytes()
        source.write_bytes(original_bytes)
        expected_clip = Program(load(source)).compile(1, strict=True)
        changed_recipe = load(source)
        changed_recipe["id"] = "edited-plank"
        changed_recipe["parameters"]["hold-seconds"]["default"] = 9
        mapping = self.root / "editable-mapping.json"
        mapping.write_text(json.dumps({"format": "eml-web-map-v1", "entries": [{
            "exercise_id": "host:editable", "recipe": "exercises/plank.json"}]}))
        output = self.root / "captured-source-bundle"
        compile_program = Program.compile

        def compile_while_source_changes(program, fps, strict=True):
            source.write_text(json.dumps(changed_recipe), encoding="utf-8")
            return compile_program(program, fps, strict=strict)

        # Use a temporary editable source; never mutate the vendored catalogue.
        with patch("export_bundle.source_path", return_value=source), \
                patch.object(Program, "compile", new=compile_while_source_changes):
            manifest = export_bundle(mapping, output, fps=1)

        entry = manifest["entries"][0]
        self.assertNotEqual(source.read_bytes(), original_bytes)
        self.assertEqual((output / entry["recipe"]).read_bytes(), original_bytes)
        self.assertEqual(entry["source_sha256"], hashlib.sha256(original_bytes).hexdigest())
        self.assertEqual(json.loads((output / entry["clip"]).read_text()), expected_clip)
        self.assertEqual(entry["eml_id"], "plank")

    def test_duplicate_keys_and_unknown_parameters_are_rejected_without_output(self):
        invalid = self.root / "invalid.json"
        cases = [
            ('{"format":"eml-web-map-v1","format":"eml-web-map-v1","entries":[]}', "duplicate-key"),
            (json.dumps({"format": "eml-web-map-v1", "entries": [{
                "exercise_id": "host", "recipe": "exercises/plank.json",
                "parameters": {"invented": 2}}]}), "unknown-parameter"),
        ]
        for index, (content, error) in enumerate(cases):
            with self.subTest(error=error):
                invalid.write_text(content, encoding="utf-8")
                output = self.root / f"invalid-output-{index}"
                with self.assertRaisesRegex(ValueError, error):
                    export_bundle(invalid, output)
                self.assertFalse(output.exists())

    def test_mapping_rejects_duplicate_ids_and_non_numeric_parameters(self):
        entry = {"exercise_id": "0017", "recipe": "exercises/plank.json"}
        with self.assertRaisesRegex(ValueError, "unique"):
            mapping_entries({"format": "eml-web-map-v1", "entries": [entry, entry]})
        for value in [True, "5", float("inf")]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite numbers"):
                mapping_entries({"format": "eml-web-map-v1", "entries": [
                    dict(entry, parameters={"hold-seconds": value})]})

    def test_recipe_paths_cannot_escape_source_root(self):
        for path in ["../outside.json", "/tmp/outside.json", "exercises/plank.txt"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                source_path(DEFAULT_ROOT.resolve(), path)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inside").mkdir()
            (root / "outside.json").write_text("{}")
            (root / "inside/link.json").symlink_to(root / "outside.json")
            with self.assertRaisesRegex(ValueError, "inside"):
                source_path((root / "inside").resolve(), "link.json")

    def test_frame_budget_rejects_without_truncation(self):
        mapping = self.root / "long-hold.json"
        mapping.write_text(json.dumps({"format": "eml-web-map-v1", "entries": [{
            "exercise_id": "host:long-hold", "recipe": "exercises/plank.json",
            "parameters": {"hold-seconds": 120}}]}))
        output = self.root / "oversized-bundle"
        with self.assertRaisesRegex(ValueError, "lower fps"):
            export_bundle(mapping, output, fps=120)
        self.assertFalse(output.exists())

    def test_discovery_index_references_are_present_in_vendored_standard(self):
        interface = json.loads((DEFAULT_ROOT / "interface.json").read_text())
        for key in ["schema", "semantics", "producerGuide", "catalog", "example",
                    "equipmentSchema", "librarySchema", "conformanceVector", "legacySchema",
                    "postureGuide", "compatibleSetups"]:
            with self.subTest(key=key):
                self.assertTrue((DEFAULT_ROOT / interface[key]).exists(), interface[key])


if __name__ == "__main__":
    unittest.main()
