import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("package_preview", HERE / "package_preview.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PackagePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.output = self.base / "preview"

    def source_copy(self):
        root = self.base / "source"
        for relative in [*packager.FILES.values(), "integrations/web/package_preview.py"]:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(packager.SOURCE_ROOT / relative, destination)
        return root

    def test_packages_only_runtime_with_exact_bytes_valid_imports_and_hashes(self):
        manifest = packager.package_preview(self.output)
        self.assertEqual(manifest["format"], "eml-web-preview-package-v1")
        self.assertRegex(manifest["source_revision"], r"^[0-9a-f]{40}$")
        self.assertIsInstance(manifest["source_modified"], bool)
        self.assertEqual(set(path.relative_to(self.output).as_posix()
                             for path in self.output.rglob("*") if path.is_file()),
                         set(packager.FILES) | {"provenance.json"})
        for destination, source in packager.FILES.items():
            data = (self.output / destination).read_bytes()
            original = (packager.SOURCE_ROOT / source).read_bytes()
            self.assertEqual(manifest["files"][destination]["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(manifest["files"][destination]["source_sha256"], hashlib.sha256(original).hexdigest())
            if destination != "preview.js":
                self.assertEqual(data, original)
        script = (self.output / "preview.js").read_text()
        self.assertNotIn("../../viewer/", script)
        for rewritten in packager.IMPORTS.values():
            self.assertEqual(script.count(rewritten), 1)
            module = rewritten[len("import('"):-2]
            self.assertTrue((self.output / module).is_file())
        self.assertIn("from './preview.js'", (self.output / "EMLPreview.jsx").read_text())
        self.assertIn("import './preview.css'", (self.output / "EMLPreview.jsx").read_text())
        self.assertEqual(json.loads((self.output / "provenance.json").read_text()), manifest)
        self.assertNotIn(str(packager.SOURCE_ROOT), json.dumps(manifest))
        self.assertNotIn(str(self.base), json.dumps(manifest))

    def test_repeated_packages_are_byte_identical(self):
        packager.package_preview(self.output)
        other = self.base / "again"
        packager.package_preview(other)
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (other / path.relative_to(self.output)).read_bytes())

    def test_existing_destination_file_directory_and_symlink_are_preserved(self):
        for kind in ["file", "directory", "symlink"]:
            with self.subTest(kind=kind):
                target = self.base / kind
                if kind == "file":
                    target.write_text("keep")
                elif kind == "directory":
                    target.mkdir()
                else:
                    target.symlink_to(self.base / "missing")
                with self.assertRaisesRegex(ValueError, "already exists"):
                    packager.package_preview(target)
                self.assertTrue(target.exists() or target.is_symlink())
                if kind == "file":
                    self.assertEqual(target.read_text(), "keep")
                if kind == "directory":
                    self.assertEqual(list(target.iterdir()), [])

    def test_concurrently_created_empty_destination_is_preserved(self):
        real_mkdir = Path.mkdir
        def mkdir(path, *args, **kwargs):
            if path == self.output:
                real_mkdir(path)
            return real_mkdir(path, *args, **kwargs)
        with patch.object(Path, "mkdir", mkdir):
            with self.assertRaises(FileExistsError):
                packager.package_preview(self.output)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.output.iterdir()), [])

    def test_missing_or_duplicate_renderer_import_rejects_without_partial_output(self):
        root = self.source_copy()
        source = root / "integrations/web/preview.js"
        original = source.read_text()
        old = next(iter(packager.IMPORTS))
        for value in [original.replace(old, "null"), original + "\n" + old]:
            source.write_text(value)
            with self.assertRaisesRegex(ValueError, "exactly one renderer import"):
                packager.package_preview(self.output, source_root=root)
            self.assertFalse(self.output.exists())

    def test_unrecognized_renderer_dependency_rejects(self):
        root = self.source_copy()
        source = root / "integrations/web/preview.js"
        source.write_text(source.read_text() + "\nimport('../../viewer/new.js');\n")
        with self.assertRaisesRegex(ValueError, "Unrecognized viewer dependency"):
            packager.package_preview(self.output, source_root=root)
        self.assertFalse(self.output.exists())

    def test_source_archive_has_explicit_unknown_revision_instead_of_claiming_git_identity(self):
        manifest = packager.package_preview(self.output, source_root=self.source_copy())
        self.assertIsNone(manifest["source_revision"])
        self.assertIsNone(manifest["source_modified"])

    def test_source_symlink_cannot_escape_checkout(self):
        root = self.source_copy()
        source = root / "viewer/mesh.js"
        external = self.base / "external.js"
        external.write_text("not the reviewed renderer")
        source.unlink()
        source.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "inside the EML root"):
            packager.package_preview(self.output, source_root=root)
        self.assertFalse(self.output.exists())

    def test_cli_packages_without_python_or_browser_dependencies(self):
        result = subprocess.run([sys.executable, str(HERE / "package_preview.py"), "--out", str(self.output)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / "provenance.json").is_file())
        again = subprocess.run([sys.executable, str(HERE / "package_preview.py"), "--out", str(self.output)],
                               capture_output=True, text=True, check=False)
        self.assertEqual(again.returncode, 1)
        self.assertIn("already exists", again.stderr)


if __name__ == "__main__":
    unittest.main()
