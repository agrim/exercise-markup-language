#!/usr/bin/env python3
"""Compile an explicit host exercise mapping into an offline EML media bundle."""

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
MAX_FRAMES = 3600


def compiler(root):
    """Use one matching evaluator/resource tree, never an unrelated installed copy."""
    root = root.resolve(strict=True)
    if not (root / "eml/__init__.py").is_file():
        raise ValueError("--eml-root must contain the EML source package and interface.json")
    sys.path.insert(0, str(root))
    from eml import Program, load
    from eml.data import ROOT

    if ROOT.resolve() != root:
        raise ValueError("A different EML resource tree is already loaded; use a fresh process")
    return Program, load


def source_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("recipe must be a nonempty relative JSON path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise ValueError("recipe must be a relative .json path inside --eml-root")
    resolved = (root / path).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("recipe must remain inside --eml-root")
    return resolved


def mapping_entries(document):
    if not isinstance(document, dict) or set(document) != {"format", "entries"}:
        raise ValueError("mapping requires only format and entries")
    if document["format"] != "eml-web-map-v1":
        raise ValueError("Unsupported mapping format")
    entries = document["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("mapping entries must be a nonempty list")
    seen = set()
    for entry in entries:
        if (not isinstance(entry, dict) or not {"exercise_id", "recipe"} <= entry.keys()
                or entry.keys() - {"exercise_id", "recipe", "parameters"}):
            raise ValueError("Each entry requires exercise_id, recipe, and optional parameters")
        identity = entry["exercise_id"]
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise ValueError("exercise_id must be a nonempty, unique string; IDs are preserved exactly")
        seen.add(identity)
        parameters = entry.get("parameters", {})
        if not isinstance(parameters, dict) or any(
            not isinstance(key, str) or type(value) not in (int, float)
            or not math.isfinite(value) for key, value in parameters.items()
        ):
            raise ValueError("parameters must map names to finite numbers")
    return entries


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                    encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compiler_fingerprint(root):
    """Identify evaluator inputs without claiming a Git revision for a custom root."""
    paths = [root / "interface.json", root / "anatomy/model.json",
             root / "docs/upper-motion-setups.json"]
    for directory, pattern in (("eml", "*.py"), ("schema", "*.json"),
                               ("library", "*.json"), ("compat/1.0/library", "*.json")):
        paths.extend((root / directory).glob(pattern))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def export_bundle(mapping, output, *, eml_root=DEFAULT_ROOT, fps=12):
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError("fps must be an integer from 1 through 120")
    root = Path(eml_root).resolve(strict=True)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; choose a new directory")
    if not output.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    Program, load = compiler(root)
    entries = mapping_entries(load(mapping))
    manifest = {
        "format": "eml-web-bundle-v1", "fps": fps,
        "compiler_inputs_sha256": compiler_fingerprint(root),
        "entries": [], "assets": {
            "model": "anatomy/model.json", "vertices": "anatomy/vertices.bin",
            "indices": "anatomy/indices.bin", "equipment": {},
            "license": "LICENSE.eml", "attribution": "anatomy/ATTRIBUTION.md",
        }, "asset_sha256": {},
    }
    # Build beside the destination. A bad mapping/recipe leaves no partial bundle.
    with tempfile.TemporaryDirectory(prefix=".eml-web-", dir=output.parent) as temporary:
        stage = Path(temporary) / "bundle"
        stage.mkdir()
        versions = set()
        for index, entry in enumerate(entries, start=1):
            path = source_path(root, entry["recipe"])
            recipe_name, clip_name = f"recipes/{index:04d}.json", f"clips/{index:04d}.json"
            staged_recipe = stage / recipe_name
            staged_recipe.parent.mkdir(parents=True, exist_ok=True)
            # Compile the same captured bytes we publish, even if the author edits
            # the original recipe while the evaluator is running.
            shutil.copyfile(path, staged_recipe)
            program = Program(load(staged_recipe), entry.get("parameters", {}))
            if math.ceil(program.duration * fps) + 1 + len(program.end_times) > MAX_FRAMES:
                raise ValueError(f"{entry['exercise_id']}: lower fps or shorten the recipe; "
                                 f"this exporter allows at most {MAX_FRAMES} samples per cycle")
            clip = program.compile(fps, strict=True)
            write_json(stage / clip_name, clip)
            versions.add(clip["eml"])
            manifest["entries"].append({
                "exercise_id": entry["exercise_id"], "eml_id": clip["id"],
                "eml_version": clip["eml"], "parameters": program.values,
                "recipe": recipe_name, "clip": clip_name,
                "source_sha256": sha256(stage / recipe_name),
                "clip_sha256": sha256(stage / clip_name),
            })
        assets = [("LICENSE", "LICENSE.eml")]
        assets.extend((name, name) for name in (
            "anatomy/model.json", "anatomy/vertices.bin", "anatomy/indices.bin",
            "anatomy/ATTRIBUTION.md"))
        for version in sorted(versions):
            source = "compat/1.0/library/equipment.json" if version == "1.0" else "library/equipment.json"
            destination = f"equipment/{version}.json"
            assets.append((source, destination))
            manifest["assets"]["equipment"][version] = destination
        for source, destination in assets:
            path = stage / destination
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / source, path)
            manifest["asset_sha256"][destination] = sha256(path)
        write_json(stage / "manifest.json", manifest)
        if output.exists() or output.is_symlink():
            raise ValueError("Output appeared during export; choose a new directory")
        stage.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--eml-root", default=DEFAULT_ROOT, type=Path)
    parser.add_argument("--fps", default=12, type=int)
    args = parser.parse_args()
    try:
        manifest = export_bundle(args.mapping, args.out, eml_root=args.eml_root, fps=args.fps)
    except (ValueError, OSError, ImportError) as error:
        parser.exit(1, f"EML export failed: {error}\n")
    print(f"Exported {len(manifest['entries'])} exercises to {args.out / 'manifest.json'}")


if __name__ == "__main__":
    main()
