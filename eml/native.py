"""Write an independently loadable exercise pack for the model repository's Metal player."""

import json
import shutil
import struct
import tempfile
from math import hypot
from pathlib import Path

from .data import ROOT, Error, registry
from .kinematics import align, multiply, quaternion, rotate


def shape(part):
    x, y, z = part["dimensions"]
    return dict(
        kind=part["shape"],
        length=x,
        radius=max(y, z) / 2,
        size=[x, y, z],
        material=part["material"],
    )


def part_pose(item, part):
    local = rotate(item["rotation"], part["position"])
    position = [x + y for x, y in zip(item["position"], local)]
    rotation = multiply(item["rotation"], quaternion(part["rotation"]))
    return position, rotation, [1, 1, 1]


def compile_pack(programs, output, fps=24):
    if not programs:
        raise Error("empty-pack", "", "Supply at least one exercise")
    output = Path(output)
    if output.exists():
        raise Error("output-exists", "", str(output))
    ids = [p.doc["id"] for p in programs]
    if len(set(ids)) != len(ids):
        raise Error("duplicate-exercise", "", "IDs in a pack must be unique")
    _, _, kit, model = registry()
    joints = [j["name"] for j in model["joints"]]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        work = Path(tmp) / "pack"
        (work / "tracks").mkdir(parents=True)
        for name in ["model.json", "indices.bin", "vertices.bin", "ATTRIBUTION.md"]:
            shutil.copyfile(ROOT / "anatomy" / name, work / name)
        motions = []
        for program in programs:
            if program.repeat["mode"] == "once" or any(
                program.repeat.get("travel", [])
            ):
                raise Error(
                    "native-repeat",
                    "/repeat",
                    "This player previews stationary loops and holds",
                )
            try:
                clip = program.compile(fps)
            except Error as exc:
                raise Error(
                    exc.code, exc.path, f"{program.doc['id']}: {exc.message}"
                ) from exc
            # The v1 native player stores each muscle palette per clip, not per phase.
            if any(
                p.get("muscles", clip["muscles"]) != clip["muscles"]
                for p in program.doc["phases"]
            ):
                raise Error(
                    "native-muscle-roles",
                    "/phases",
                    "This player supports clip-level muscle roles only",
                )
            if not clip["muscles"]["primary"]:
                raise Error(
                    "native-muscle-roles",
                    "/muscles",
                    "This player requires at least one primary group",
                )
            parts = [
                (item["id"], part)
                for item in clip["equipment"]
                for part in kit[item["kind"]]["visual"]
            ]
            equipment = [shape(part) for _, part in parts]
            lines = clip["connections"]
            equipment += [
                {"kind": "rod", "length": 1, "radius": 0.012, "material": "steel"}
                for _ in lines
            ]
            frames = clip["frames"]
            # EXM1 phase is float32. Merge indistinguishably close grid/boundary samples.
            unique = {}
            for f in frames:
                phase = struct.unpack(
                    "<f", struct.pack("<f", f["time"] / clip["duration"])
                )[0]
                unique[phase] = f
            out = bytearray(
                struct.pack("<4sIHH", b"EXM1", len(unique), len(joints), len(equipment))
            )

            def q16(q):
                norm = hypot(*q)
                return struct.pack(
                    "<4h", *(round(max(-1, min(1, v / norm)) * 32767) for v in q)
                )

            for phase, f in sorted(unique.items()):
                out.extend(struct.pack("<4f", phase, *f["root"]))
                for joint in joints:
                    out.extend(q16(f["rotations"][joint]))
                props = [part_pose(f["equipment"][name], part) for name, part in parts]
                for line in lines:
                    a, b = (
                        f["equipment"][side["item"]]["sockets"][side["socket"]]
                        for side in (line["from"], line["to"])
                    )
                    delta = [y - x for x, y in zip(a, b)]
                    length = hypot(*delta)
                    rotation = (
                        align([1, 0, 0], delta) if length > 1e-9 else [0, 0, 0, 1]
                    )
                    props.append(
                        (
                            [(x + y) / 2 for x, y in zip(a, b)],
                            rotation,
                            [max(1e-6, length), 1, 1],
                        )
                    )
                for pos, rot, scale in props:
                    out.extend(
                        struct.pack("<3f", *pos) + q16(rot) + struct.pack("<3f", *scale)
                    )
            track = f"tracks/{clip['id']}.bin"
            (work / track).write_bytes(out)
            row = dict(
                id=clip["id"],
                title=clip["title"],
                seconds=clip["duration"],
                **clip["muscles"],
                camera=clip["camera"],
                equipment=equipment,
                track=track,
            )
            if "sideFocus" in clip:
                row["sideFocus"] = clip["sideFocus"]
            motions.append(row)
        (work / "motions.json").write_text(
            json.dumps({"version": 1, "joints": joints, "exercises": motions}, indent=1)
            + "\n"
        )
        work.rename(output)
