"""Conformance tests for recipes. Sample inside each phase and on both sides of transitions."""

from math import ceil, dist, radians, sin

from .data import Error
from .posture import speed_findings


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

    if not 2 <= samples <= 121:
        raise Error("samples", "", "Expected 2 to 121 samples per phase")
    # Subsequent travelling reps may move into fixed supports and fixed equipment. An ordinary
    # repeating cycle is identical for every rep and only needs one evaluation.
    count = (
        program.repeat["count"]
        if program.posture and any(program.repeat.get("travel", []))
        else 1
    )
    per_phase = [
        max(samples, ceil(24 * p["seconds"]) + 1) if program.posture else samples
        for p in program.doc["phases"]
    ]
    if program.posture and count * sum(per_phase) > 120_000:
        raise Error(
            "constraint-budget",
            "/repeat",
            "Shorten this travelling demonstration for validation",
        )
    sample_count = 0
    for cycle in range(count):
        first = program.segment(0, 0, cycle)
        last = first
        for i, phase in enumerate(program.doc["phases"]):
            prefix = f"/phases/{i}"
            begin = program.segment(i, 0, cycle)
            if i:
                a, b, c = differences(last, begin)
                if a > 0.015 or b > 2 * sin(radians(3) / 4) or c > 0.015:
                    problem(
                        "discontinuous-contact",
                        prefix,
                        f"Boundary jumps {a:.4f} m / quaternion delta {b:.4f} / equipment delta {c:.4f}",
                    )
            for tick in range(per_phase[i]):
                frame = program.segment(i, tick / (per_phase[i] - 1), cycle)
                sample_count += 1
                if program.posture and tick:
                    frame["diagnostics"].extend(speed_findings(last, frame, cycle))
                for d in frame["diagnostics"]:
                    if "unit" in d:  # v1.1 reports retain measured quantity and units
                        problems.append(
                            dict(
                                d,
                                code=d["reason"],
                                message=f"{d['message']} during {frame['phase']} at {frame['time']:.4f} s (rep {cycle + 1})",
                            )
                        )
                    else:
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
            successor = program.segment(0, 0, cycle + 1)
            a, b, c = differences(successor, last)
            if a > 0.002 or b > 2 * sin(radians(0.5) / 4) or c > 0.002:
                problem(
                    "open-loop",
                    "/repeat",
                    f"Loop seam {a:.4f} m / quaternion delta {b:.4f} / equipment delta {c:.4f}",
                )
    return {"id": program.doc["id"], "samples": sample_count, "issues": problems}
