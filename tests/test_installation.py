"""Installed catalogs follow the wheel's actual prefix, even when it differs from Python's."""
import tempfile
import unittest
from importlib.metadata import PathDistribution
from pathlib import Path
from unittest.mock import patch

from eml import data


class InstalledDataTests(unittest.TestCase):
    def test_user_prefix_and_flattened_target_data(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = Path(folder)
            site = prefix / "lib/python3.13/site-packages"
            metadata = site / "exercise_markup_language-1.1.0.dist-info"
            metadata.mkdir(parents=True)
            marker = Path("share/exercise-markup-language/interface.json")
            (prefix / marker).parent.mkdir(parents=True)
            (prefix / marker).write_text("{}")
            (metadata / "RECORD").write_text(f"../../../{marker.as_posix()},,\n")
            records = PathDistribution(metadata).files
            with patch.object(data, "__file__", str(site / "eml/data.py")), patch(
                "importlib.metadata.files", return_value=records
            ):
                self.assertEqual(data._resource_root(), (prefix / marker).resolve().parent)
                (site / marker).parent.mkdir(parents=True)
                (site / marker).write_text("{}")
                self.assertEqual(data._resource_root(), (site / marker).resolve().parent)
