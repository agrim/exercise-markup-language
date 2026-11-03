"""Screen reference machine components and cable paths against the torso. Distances are metres.

This is a conservative review screen, not a mesh collision solver. A box is finite;
a circular rod is represented by its bounding capsule. Useful contacts on a support
pad should be checked against skinned tissue before changing its placement.
"""

import argparse
import json
import sys
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eml import Program, load
from eml.kinematics import add, inverse, multiply, quaternion, rotate, sub
from eml.posture import segment_distance

CORES = (
    ("spine", "pelvis", "chest", 0.055),
    ("chest", "chest", "neck", 0.063),
    ("head", "neck", "head", 0.038),
)


def segment_box(a, b, half):
    """Distance to an AABB. Squared distance is quadratic between face crossings."""
    d = sub(b, a)
    times = {0.0, 1.0}
    for i, step in enumerate(d):
        if step:
            for edge in (-half[i], half[i]):
                t = (edge - a[i]) / step
                if 0 < t < 1:
                    times.add(t)
    best = float("inf")
    points = sorted(times)
    for low, high in zip(points, points[1:]):
        midpoint = (low + high) / 2
        outside = [
            (i, min(half[i], max(-half[i], a[i] + d[i] * midpoint)))
            for i in range(3)
            if abs(a[i] + d[i] * midpoint) > half[i]
        ]
        if not outside:
            return 0.0
        denom = sum(d[i] ** 2 for i, _ in outside)
        t = (
            low
            if not denom
            else max(
                low, min(high, sum(d[i] * (edge - a[i]) for i, edge in outside) / denom)
            )
        )
        best = min(
            best, hypot(*(max(0.0, abs(a[i] + t * d[i]) - half[i]) for i in range(3)))
        )
    return best


def measure(program, frame):
    points = frame["positions"]
    cores = [(name, points[a], points[b], r) for name, a, b, r in CORES]
    for item in program.equipment:
        spec = program.kit[item["kind"]]
        if spec["category"] not in ("station", "support"):
            continue
        state = frame["equipment"][item["id"]]
        for i, part in enumerate(spec["visual"]):
            x, y, z = (v / 2 for v in part["dimensions"])
            shape = part["shape"]
            if not (
                shape in ("box", "bench") or shape == "rod" and abs(y - z) <= 0.0015
            ):
                continue
            origin = add(state["position"], rotate(state["rotation"], part["position"]))
            local = inverse(multiply(state["rotation"], quaternion(part["rotation"])))
            for name, a, b, radius in cores:
                a, b = rotate(local, sub(a, origin)), rotate(local, sub(b, origin))
                distance = (
                    segment_distance(a, b, (-x, 0, 0), (x, 0, 0)) - y
                    if shape == "rod"
                    else segment_box(a, b, (x, y, z))
                )
                yield (item["id"], str(i), part["material"], name), distance - radius
    for edge in program.doc.get("connections", []):

        def endpoint(ref):
            return frame["equipment"][ref["item"]]["sockets"][ref["socket"]]

        a, b = endpoint(edge["from"]), endpoint(edge["to"])
        for name, start, end, radius in cores:
            yield (
                ("connection", edge["kind"], edge["to"]["item"], name),
                segment_distance(start, end, a, b)
                - radius
                - (0.012 if edge["kind"] == "rope" else 0.006),
            )


def audit(directory, samples):
    results = []
    count = 0
    for path in sorted(directory.glob("*.json")):
        program = Program(load(path))
        hits = {}
        if program.equipment:
            for i in range(len(program.doc["phases"])):
                for j in range(samples):
                    frame = program.segment(i, j / (samples - 1))
                    count += 1
                    for key, gap in measure(program, frame):
                        if gap < -0.012 and gap < hits.get(key, {}).get("gap", 0):
                            hits[key] = dict(
                                component=list(key),
                                gap=gap,
                                phase=frame["phase"],
                                time=frame["time"],
                            )
        results.append(dict(id=program.doc["id"], findings=list(hits.values())))
    return dict(
        units="m",
        samples=count,
        exercises=len(results),
        exercisesWithFindings=sum(bool(r["findings"]) for r in results),
        results=results,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=ROOT / "exercises", type=Path)
    parser.add_argument("--samples", type=int, choices=range(2, 122), default=9)
    parser.add_argument("-o", "--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.directory, args.samples), indent=2, allow_nan=False)
        + "\n"
    )
