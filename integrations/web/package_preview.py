#!/usr/bin/env python3
"""Package the optional browser preview and matching renderer for a host app."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "preview.js": "integrations/web/preview.js",
    "preview.css": "integrations/web/preview.css",
    "EMLPreview.jsx": "integrations/web/EMLPreview.jsx",
    "renderer/mesh.js": "viewer/mesh.js",
    "renderer/camera-controls.js": "viewer/camera-controls.js",
    "LICENSE": "LICENSE",
}
IMPORTS = {
    "import('../../viewer/mesh.js')": "import('./renderer/mesh.js')",
    "import('../../viewer/camera-controls.js')": "import('./renderer/camera-controls.js')",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_state(root, captured):
    """Compare the captured inputs with HEAD, not a potentially later working copy."""
    try:
        top = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL,
            text=True).strip()
        if Path(top).resolve() != root:
            return None, None
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        modified = False
        for relative, data in captured.items():
            result = subprocess.run(
                ["git", "-C", str(root), "show", f"{revision}:{relative}"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
            modified |= result.returncode != 0 or result.stdout != data
        return revision, modified
    except (OSError, subprocess.CalledProcessError):
        # A source archive has no Git identity. Content hashes still identify it.
        return None, None


def package_preview(output, *, source_root=SOURCE_ROOT):
    root = Path(source_root).resolve(strict=True)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; choose a new directory")
    if not output.parent.is_dir():
        raise ValueError("Output parent directory must already exist")

    paths = [*FILES.values(), "integrations/web/package_preview.py"]
    captured = {}
    for relative in paths:
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Source must remain inside the EML root: {relative}")
        captured[relative] = path.read_bytes()
    original = captured[FILES["preview.js"]].decode("utf-8")
    adapted = original
    for old, new in IMPORTS.items():
        if adapted.count(old) != 1:
            raise ValueError(f"Expected exactly one renderer import: {old}")
        adapted = adapted.replace(old, new)
    if "../../viewer/" in adapted:
        raise ValueError("Unrecognized viewer dependency; update the package contract")

    revision, modified = source_state(root, captured)
    manifest = {
        "format": "eml-web-preview-package-v1",
        "source_revision": revision,
        "source_modified": modified,
        "source_modified_scope": "Captured runtime inputs and packager compared with source_revision; null when Git provenance is unavailable.",
        "packager": {"source": "integrations/web/package_preview.py",
                     "source_sha256": sha256(captured["integrations/web/package_preview.py"])},
        "files": {},
    }
    # Stage all bytes before reserving the output. mkdir is exclusive, so a
    # destination created concurrently is preserved, even when it is empty.
    with tempfile.TemporaryDirectory(prefix=".eml-preview-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for destination, source in FILES.items():
            data = adapted.encode("utf-8") if destination == "preview.js" else captured[source]
            path = stage / destination
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            manifest["files"][destination] = {
                "source": source, "source_sha256": sha256(captured[source]),
                "sha256": sha256(data),
                "transformation": "relative-renderer-imports" if destination == "preview.js" else "none",
            }
        (stage / "provenance.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        output.mkdir()
        try:
            for item in stage.iterdir():
                item.rename(output / item.name)
        except BaseException:
            shutil.rmtree(output)
            raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        package_preview(args.out)
    except (ValueError, OSError) as error:
        parser.exit(1, f"EML preview packaging failed: {error}\n")
    print(f"Packaged optional EML preview to {args.out}")


if __name__ == "__main__":
    main()
