"""Assemble a disposable Xcode wrapper from an existing wrapper checkout and EML recipes."""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eml import Program, load
from eml.native import compile_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrapper", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--fps", type=int, default=18)
    parser.add_argument("recipe", nargs="*", type=Path)
    args = parser.parse_args()
    wrapper = args.wrapper.resolve()
    files = [
        wrapper / p
        for p in (
            "HumanExerciseModels.xcodeproj",
            "Revision/Package.swift",
            "Revision/Preview",
            "Revision/Sources/ExerciseDummy",
            "Revision/Tools/RenderBatch",
            "Revision/Tests/ExerciseDummyTests",
        )
    ]
    if not all(p.exists() for p in files):
        parser.error("Expected the anatomy Metal wrapper checkout")
    if args.out.exists():
        parser.error("--out must be a new directory")
    paths = args.recipe or sorted((ROOT / "exercises").glob("*.json"))
    import tempfile

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as t:
        project = Path(t) / "wrapper"
        project.mkdir()
        for file in files:
            dest = project / file.relative_to(wrapper)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if file.is_dir():
                shutil.copytree(
                    file,
                    dest,
                    ignore=shutil.ignore_patterns(
                        "Resources", "xcuserdata", "*.xcuserstate"
                    ),
                )
            else:
                shutil.copyfile(file, dest)
        compile_pack(
            [Program(load(p)) for p in paths],
            project / "Revision/Sources/ExerciseDummy/Resources",
            args.fps,
        )
        project.rename(args.out)
    print(args.out / "HumanExerciseModels.xcodeproj")


if __name__ == "__main__":
    main()
