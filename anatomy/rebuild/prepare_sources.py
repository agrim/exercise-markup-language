"""Fetch verified archives and extract only the Z-Anatomy meshes used to build the dummy."""

import argparse
import hashlib
import shutil
import subprocess
import os
import urllib.request
import zipfile
from pathlib import Path

DBCLS = "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/"
ZA_COMMIT = "7b9197672eea2ed44ae238d3cfbf38e39b7586a9"
ZA = f"https://raw.githubusercontent.com/Z-Anatomy/Models-of-human-anatomy/{ZA_COMMIT}/"
FILES = {
    "isa_BP3D_4.0_obj_99.zip": (
        DBCLS,
        "40665852c49f218326590e204db91064a1ecfc3c6f8cbd7bbbcaac62c7cd409e",
    ),
    "isa_element_parts.txt": (
        DBCLS,
        "a3de74423f943b0d724ae8f59b3a817f87c423a544f8db98113b1980817cbeaf",
    ),
    "Z-Anatomy.zip": (
        ZA,
        "e029688545627bd0214b269e1063143abb580aad72b2c2445d6d8a9a0d9da736",
    ),
}


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    cache = parser.parse_args().cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    for filename, (base, sha) in FILES.items():
        path = cache / filename
        if path.exists() and digest(path) == sha:
            continue
        partial = path.with_suffix(path.suffix + ".partial")
        with (
            urllib.request.urlopen(base + filename, timeout=120) as response,
            partial.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        if digest(partial) != sha:
            raise ValueError(f"Upstream archive checksum changed: {filename}")
        partial.replace(path)
    with (
        zipfile.ZipFile(cache / "Z-Anatomy.zip") as source,
        source.open("Z-Anatomy/Startup.blend") as src,
        (cache / "Startup.blend").open("wb") as dst,
    ):
        shutil.copyfileobj(src, dst)
    here = Path(__file__).resolve().parent
    subprocess.run(
        [
            os.environ.get("BLENDER", "blender"),
            "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
            str(cache / "Startup.blend"),
            "--python",
            str(here / "extract_z.py"),
            "--",
            str(cache / "zparts"),
        ],
        check=True,
    )
