"""Conformance tests for recipes. Sample inside each phase and on both sides of transitions."""

from math import dist, radians, sin

from .data import Error


def differences(first, second, translation=(0, 0, 0)):
    target = lambda point: [x + d for x, d in zip(point, translation)]

    def angle_diff(a, b):
        # Unit-quaternion distance, accounting for the double-cover.
        return min(dist(a, b), dist(a, [-x for x in b]))

    joints = max(
        dist(target(v), second["positions"][joint])
        for joint, v in first["positions"].items()
    )
    turns = max(
        angle_diff(v, second["rotations"][joint])
        for joint, v in first["rotations"].items()
    )
    props = max(
        (
            max(
                dist(v["position"], second["equipment"][k]["position"]),
                angle_diff(v["rotation"], second["equipment"][k]["rotation"]),
            )
            for k, v in first["equipment"].items()
        ),
        default=0,
    )
    return joints, turns, props


def check(program, samples=9):
    problems = []

    def problem(code, path, detail):
        problems.append(Error(code, path, detail).as_dict())

    first = program.segment(0, 0)
    last = first
    sample_count = 0
    for i, phase in enumerate(program.doc["phases"]):
        prefix = f"/phases/{i}"
        begin = program.segment(i, 0)
        if i:
            a, b, c = differences(last, begin)
            if a > 0.015 or b > 2 * sin(radians(3) / 4) or c > 0.015:
                problem(
                    "discontinuous-contact",
                    prefix,
                    f"Boundary jumps {a:.4f} m / quaternion delta {b:.4f} / equipment delta {c:.4f}",
                )
        for tick in range(samples):
            frame = program.segment(i, tick / (samples - 1))
            sample_count += 1
            for d in frame["diagnostics"]:
                problem(
                    d["reason"],
                    prefix + "/contacts",
                    f"{d['effector']}: residual {d['residual']:.5f} m at {frame['time']:.4f} s",
                )
            if program.repeat["mode"] == "hold" and any(
                x > 1e-5 for x in differences(first, frame)
            ):
                problem(
                    "moving-hold",
                    prefix,
                    "A hold must retain the same body and equipment pose",
                )
            last = frame
    if program.repeat["mode"] == "loop":
        # Compare in world space at the seam; world-fixed anchors stay fixed.
        successor = program.segment(0, 0, 1)
        a, b, c = differences(successor, last)
        if a > 0.002 or b > 2 * sin(radians(0.5) / 4) or c > 0.002:
            problem(
                "open-loop",
                "/repeat",
                f"Loop seam {a:.4f} m / quaternion delta {b:.4f} / equipment delta {c:.4f}",
            )
    return {"id": program.doc["id"], "samples": sample_count, "issues": problems}
