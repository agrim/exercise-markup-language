"""Reference command line for exercise authors and consuming applications."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import Error, Program, interface, load
from .checks import check
from .data import ROOT
from .native import compile_pack


def emit(value, out=None):
    text = json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n"
    if not out:
        print(text, end="")
        return
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent) as f:
        f.write(text)
    os.replace(f.name, path)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m eml")
    subs = parser.add_subparsers(dest="command", required=True)
    inf = subs.add_parser(
        "interface",
        help="Machine-readable schema, poses, motions, equipment, rig and muscles",
    )
    inf.add_argument("-o", "--output")
    cat = subs.add_parser(
        "catalog", help="Check every catalog entry and any additional recipes"
    )
    cat.add_argument("--directory", type=Path, default=ROOT / "exercises")
    cat.add_argument("--samples", type=int, default=9)
    cat.add_argument("-o", "--output")
    for name in ("validate", "sample", "compile", "native"):
        sub = subs.add_parser(name)
        sub.add_argument("recipes", nargs="+" if name == "native" else 1)
        sub.add_argument("--set", action="append", default=[], metavar="NAME=NUMBER")
        sub.add_argument("-o", "--output", required=name == "native")
        if name in ("compile", "native"):
            sub.add_argument("--fps", type=int, default=24)
        if name == "sample":
            sub.add_argument("--seconds", type=float, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == "interface":
            emit(interface(), args.output)
            return 0
        if args.command == "catalog":
            if not 2 <= args.samples <= 121:
                raise Error("samples", "", "Expected 2 to 121")
            entries = []
            ids = set()
            for path in sorted(args.directory.glob("*.json")):
                try:
                    p = Program(load(path))
                    id_ = p.doc["id"]
                    if id_ != path.stem or id_ in ids:
                        raise Error(
                            "catalog-id", "/id", "ID must be unique and match filename"
                        )
                    ids.add(id_)
                    entries.append(check(p, args.samples))
                except Error as e:
                    entries.append(
                        {"id": path.stem, "samples": 0, "issues": [e.as_dict()]}
                    )
            if not entries:
                raise Error("empty-catalog", "", str(args.directory))
            issues = sum(len(x["issues"]) for x in entries)
            emit(
                {
                    "eml": "1.0",
                    "exercises": len(entries),
                    "samples": sum(x["samples"] for x in entries),
                    "issues": issues,
                    "results": entries,
                },
                args.output,
            )
            return 1 if issues else 0
        values = {}
        for item in args.set:
            key, sep, v = item.partition("=")
            if not sep or key in values:
                raise Error("parameter", "", item)
            values[key] = float(v)
        progs = [Program(load(p), values) for p in args.recipes]
        if args.command == "native":
            compile_pack(progs, args.output, args.fps)
            return 0
        p = progs[0]
        if args.command == "compile":
            emit(p.compile(args.fps), args.output)
            return 0
        audit = check(p)
        if args.command == "validate":
            emit(audit, args.output)
            return int(bool(audit["issues"]))
        if audit["issues"]:
            issue = audit["issues"][0]
            raise Error(issue["code"], issue["path"], issue["message"])
        frame = p.playback(args.seconds)
        if frame["diagnostics"]:
            raise Error("unresolved-contact", "/contacts", str(frame["diagnostics"]))
        emit(frame, args.output)
        return 0
    except (Error, OSError, ValueError) as exc:
        issue = (
            exc.as_dict()
            if isinstance(exc, Error)
            else {"code": "input", "path": "", "message": str(exc)}
        )
        print(json.dumps({"issues": [issue]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
