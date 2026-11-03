"""Screen the full solved trajectory, including v1.0 recipes, without altering them.

Run from any directory: python tools/audit_posture.py -o /tmp/catalog-posture.json.
Results are geometric authoring evidence and review prompts, not clinical judgements.
"""

import argparse
import json
import sys
from collections import Counter
from math import asin, ceil, degrees, dist, hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eml import Error, Program, load
from eml.checks import differences
from eml.kinematics import dot, inverse, multiply, quaternion, rotate, sub, unit
from eml.posture import (
    CORE,
    Constraints,
    SolvedFrame,
    clamp,
    expand,
    segment_distance,
    speed_findings,
)


def rect_distance(a, b, x, z):
    """Exact segment distance to a finite rectangle in its local XZ plane (Y=0)."""
    y = a[1] - b[1]
    if y:
        t = a[1] / y
        if (
            0 <= t <= 1
            and abs(a[0] + t * (b[0] - a[0])) <= x
            and abs(a[2] + t * (b[2] - a[2])) <= z
        ):
            return 0.0

    def point(p):
        return hypot(max(0, abs(p[0]) - x), p[1], max(0, abs(p[2]) - z))

    corners = [(-x, 0, -z), (x, 0, -z), (x, 0, z), (-x, 0, z)]
    return min(
        point(a),
        point(b),
        *(segment_distance(a, b, corners[i - 1], corners[i]) for i in range(4)),
    )


def weight_bottom(spec, pose):
    """Lowest illustrated equipment primitive in world Y, including shaft and both plates."""
    lows = []
    for part in spec["visual"]:
        x, y, z = part["dimensions"]
        shape = part["shape"]
        center = pose["position"][1] + rotate(pose["rotation"], part["position"])[1]
        q = multiply(pose["rotation"], quaternion(part["rotation"]))
        up = rotate(inverse(q), (0, 1, 0))

        def cylinder(length, height, depth):
            return (length * abs(up[0]) + hypot(height * up[1], depth * up[2])) / 2

        if shape == "rod":
            low = -cylinder(x, y, z)
        elif shape in ("barbell", "dumbbell"):
            single = shape == "dumbbell"
            tip = x / 2 - (0.004 if single else 0.055)
            plate = 0.24 * x if single else min(0.12, 0.09 * x)
            low = min(
                -cylinder(x, 0.029, 0.029),
                -abs(up[0]) * (tip - plate / 2) - cylinder(plate, y, z),
            )
        elif shape == "ball":
            low = -hypot(*(size * n / 2 for size, n in zip((x, y, z), up)))
        elif shape == "box":
            low = -sum(abs(n) * size / 2 for size, n in zip((x, y, z), up))
        elif shape == "kettlebell":
            r, w = z / 2, x / 2
            cy = -(1.55 * r + 0.02)
            low = cy * up[1] - r

            # The example renderers construct the handle from closed cylinders.
            def link(a, b, radius):
                axial = dot(up, unit(sub(b, a)))
                return (
                    min(dot(up, a), dot(up, b))
                    - radius * max(0, 1 - axial * axial) ** 0.5
                )

            low = min(low, link((-0.74 * w, 0, 0), (0.74 * w, 0, 0), 0.0165))
            for sign in (-1, 1):
                shoulder = (sign * w, -0.04, 0)
                low = min(
                    low,
                    link((sign * w * 0.74, 0, 0), shoulder, 0.017),
                    link(shoulder, (sign * r * 0.55, cy + r * 0.65, 0), 0.017),
                )
        else:
            continue
        lows.append(center + low)
    return min(lows, default=float("inf"))


def support_geometry(name):
    if name == "pelvis":
        return name, name, 0.110
    if name == "chest":
        return name, "neck", 0.115
    if name == "spine":
        return name, "chest", 0.105
    for side in ("left", "right"):
        if name.startswith(side):
            regions = {
                "UpperArm": ("Forearm", 0.050),
                "Forearm": ("Hand", 0.038),
                "Hand": ("Grip", 0.032),
                "Thigh": ("Shin", 0.060),
                "Shin": ("Foot", 0.040),
                "Foot": ("Toe", 0.032),
            }
            suffix = name[len(side) :]
            if suffix in regions:
                to, r = regions[suffix]
                return name, side + to, r
    return None


def audit(program, fps, minimum):
    probe = program.posture or Constraints(program)
    slots = {}
    count = 0
    eligible = Counter()
    skipped = set()

    def record(code, subject, value, limit, unit, frame, cycle, path, excess=None):
        residual = abs(value - limit) if excess is None else excess
        key = (code, subject, path)
        row = slots.get(key)
        if row is None:
            row = slots[key] = {
                "code": code,
                "subject": subject,
                "path": path,
                "samples": 0,
                "first": {
                    "time": round(frame["time"], 5),
                    "phase": frame["phase"],
                    "cycle": cycle + 1,
                },
            }
        row["samples"] += 1
        if residual > row.get("_peak", -1):
            row.update(
                _peak=residual,
                value=round(value, 5),
                limit=round(limit, 5),
                excess=round(residual, 5),
                unit=unit,
                phase=frame["phase"],
                time=round(frame["time"], 5),
                cycle=cycle + 1,
            )

    rig = program.solver.rig
    pads = {
        item["id"]: [
            p
            for p in program.kit[item["kind"]].get("visual", [])
            if p["shape"] == "box" and p["material"] == "pad"
        ]
        for item in program.equipment
    }
    free = {
        i["id"]: program.kit[i["kind"]]
        for i in program.equipment
        if program.kit[i["kind"]]["category"] == "free-weight"
    }
    # A small sphere inside each carried load detects deep inter-implement overlap, without
    # treating touching plates or intentional grouped handles as broken motion.
    pairR = {
        i: min(spec["dimensions"]) / 2
        for i, spec in free.items()
        if spec["shape"] in ("dumbbell", "ball")
    }
    previous = None
    cycles = (
        range(program.repeat["count"]) if any(program.repeat.get("travel", [])) else [0]
    )
    total = sum(
        max(minimum - 1, ceil(phase["seconds"] * fps)) + 1
        for phase in program.doc["phases"]
    ) * len(cycles)
    if total > 240_000:
        raise Error(
            "audit-budget",
            "/repeat",
            "Reduce the number of travelling repetitions or sample rate",
        )
    for cycle in cycles:
        for i, phase in enumerate(program.doc["phases"]):
            steps = max(minimum - 1, ceil(phase["seconds"] * fps))
            path = f"/phases/{i}"
            pins = {
                c["effector"]: c["target"]
                for c in program.effective_contacts(phase)
                if c.get("engage", "pin") == "pin"
            }
            pinned = {}
            declared_support = {
                (
                    c["landmark"],
                    c["surface"]["item"] if isinstance(c["surface"], dict) else "floor",
                )
                for c in probe.phases[phase["id"]]
                if c["kind"] == "support"
            }
            for k in range(steps + 1):
                f = program.segment(i, k / steps, cycle)
                count += 1
                sample = SolvedFrame(f, rig)
                diagnostics = list(f["diagnostics"])
                if program.posture is None:
                    diagnostics.extend(probe.diagnose(f, cycle))
                for d in diagnostics:
                    if "unit" in d:
                        record(
                            d["reason"],
                            d["effector"],
                            d.get("measured", 0),
                            d.get("limit", 0),
                            d["unit"],
                            f,
                            cycle,
                            d["path"],
                            d["residual"],
                        )
                    else:
                        code = d["reason"]
                        if code == "inconsistent-orientation":
                            record(
                                code,
                                d["effector"],
                                d["orientationErrorDegrees"],
                                0.1,
                                "deg",
                                f,
                                cycle,
                                path + "/contacts",
                            )
                        else:
                            record(
                                code,
                                d["effector"],
                                d["residual"],
                                program.solver.tolerance,
                                "m",
                                f,
                                cycle,
                                path + "/contacts",
                            )
                if previous is not None:
                    prevC, prev = previous
                    delta = (
                        f["time"] - prev["time"]
                        if prevC == cycle
                        else f["time"] + program.duration - prev["time"]
                    )
                    if delta < 1e-8:
                        a, b, c = differences(prev, f)
                        for val, lim, code in [
                            (a, 0.015, "joint-boundary-jump"),
                            (c, 0.015, "equipment-boundary-jump"),
                        ]:
                            if val > lim:
                                record(
                                    code,
                                    "phase boundary",
                                    val,
                                    lim,
                                    "m",
                                    f,
                                    cycle,
                                    path,
                                )
                        deg = degrees(4 * asin(clamp(b / 2, 0, 1)))
                        if deg > 3:
                            record(
                                "rotation-boundary-jump",
                                "phase boundary",
                                deg,
                                3,
                                "deg",
                                f,
                                cycle,
                                path,
                            )
                    else:
                        # Same measured rate and threshold as the raw and strict compiler.
                        # Only travel-cycle crossings need a translated previous timestamp.
                        prior = (
                            prev
                            if prevC == cycle
                            else dict(prev, time=prev["time"] - program.duration)
                        )
                        for d in speed_findings(prior, f, cycle):
                            record(
                                d["reason"],
                                d["effector"],
                                d["measured"],
                                d["limit"],
                                d["unit"],
                                f,
                                cycle,
                                path,
                            )
                previous = (cycle, f)
                for name, target in pins.items():
                    observed = sample.point(name)
                    if isinstance(target, dict) and "item" in target:
                        item = f["equipment"][target["item"]]
                        observed = rotate(
                            inverse(item["rotation"]),
                            sub(observed, item["sockets"][target["socket"]]),
                        )
                    if name not in pinned:
                        pinned[name] = observed
                    drift = dist(pinned[name], observed)
                    if drift > 0.012:
                        record(
                            "pinned-contact-drift",
                            name,
                            drift,
                            0.012,
                            "m",
                            f,
                            cycle,
                            path + "/contacts",
                        )
                for support in f["supports"]:
                    body = expand(support["body"])
                    surface = support["surface"]
                    for name in body:
                        if (name, surface) in declared_support:
                            # The reference diagnostics already measure this authored point against the exact face.
                            eligible["support-distance"] += 1
                            continue
                        geom = support_geometry(name)
                        if not geom or (surface != "floor" and not pads[surface]):
                            skipped.add((name, surface))
                            continue
                        a, b, r = geom
                        a, b = sample.point(a), sample.point(b)
                        eligible["support-distance"] += 1
                        if surface == "floor":
                            gap = min(a[1], b[1]) - r
                        else:
                            item = f["equipment"][surface]
                            a, b = [
                                rotate(
                                    inverse(item["rotation"]), sub(v, item["position"])
                                )
                                for v in (a, b)
                            ]
                            distances = []
                            for pad in pads[surface]:
                                x, y, z = [d / 2 for d in pad["dimensions"]]
                                local = [
                                    rotate(
                                        inverse(quaternion(pad["rotation"])),
                                        sub(v, pad["position"]),
                                    )
                                    for v in (a, b)
                                ]
                                a1, b1 = [[v[0], v[1] - y, v[2]] for v in local]
                                distances.append(rect_distance(a1, b1, x, z))
                            gap = min(distances) - r
                        if gap > 0.06:
                            record(
                                "unsupported-body-gap",
                                name + "/" + surface,
                                gap,
                                0.06,
                                "m",
                                f,
                                cycle,
                                path + "/supports",
                            )
                # Deep forearm-through-trunk only. Hand-to-chest contact and upper arms close
                # to the shoulder joint are legitimate; this conservative inner core excludes those.
                for side in ("left", "right"):
                    a, b = sample.point(side + "Forearm"), sample.point(side + "Hand")
                    for c, e, radius in CORE[:2]:
                        gap = (
                            segment_distance(a, b, sample.point(c), sample.point(e))
                            - 0.022
                            - radius
                        )
                        if gap < -0.025:
                            record(
                                "forearm-through-trunk",
                                side + "Forearm/" + c,
                                gap,
                                -0.025,
                                "m",
                                f,
                                cycle,
                                path,
                            )
                for item, shape in free.items():
                    low = weight_bottom(shape, f["equipment"][item])
                    if low < -0.012:
                        record(
                            "equipment-below-floor",
                            item,
                            low,
                            -0.012,
                            "m",
                            f,
                            cycle,
                            path,
                        )
                for k1, first in enumerate(pairR):
                    for second in list(pairR)[k1 + 1 :]:
                        gap = (
                            dist(
                                f["equipment"][first]["position"],
                                f["equipment"][second]["position"],
                            )
                            - pairR[first]
                            - pairR[second]
                        )
                        if gap < -0.025:
                            record(
                                "paired-load-core-overlap",
                                first + "/" + second,
                                gap,
                                -0.025,
                                "m",
                                f,
                                cycle,
                                path,
                            )
    if program.repeat["mode"] == "loop":
        next_frame = program.segment(0, 0, len(cycles))
        a, b, c = differences(previous[1], next_frame)
        for val, lim, name in [
            (a, 0.002, "open-body-loop"),
            (c, 0.002, "open-equipment-loop"),
        ]:
            if val > lim:
                record(
                    name,
                    "cycle seam",
                    val,
                    lim,
                    "m",
                    previous[1],
                    len(cycles) - 1,
                    "/repeat",
                )
        deg = degrees(4 * asin(clamp(b / 2, 0, 1)))
        if deg > 0.5:
            record(
                "open-rotation-loop",
                "cycle seam",
                deg,
                0.5,
                "deg",
                previous[1],
                len(cycles) - 1,
                "/repeat",
            )
    rows = sorted(slots.values(), key=lambda r: (r["code"], -r["_peak"], r["subject"]))
    for r in rows:
        del r["_peak"]
    return {
        "samples": count,
        "repetitionsEvaluated": len(cycles),
        "issues": rows,
        "supportChecks": eligible["support-distance"],
        "unmeasuredSupports": [list(pair) for pair in sorted(skipped)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--directory", type=Path, default=ROOT / "exercises")
    parser.add_argument(
        "--fps", type=int, default=24, choices=range(1, 121), metavar="1..120"
    )
    parser.add_argument(
        "--samples", type=int, default=9, choices=range(2, 122), metavar="2..121"
    )
    parser.add_argument(
        "--parameter-limits",
        action="store_true",
        help="Also audit each nondefault min and max in isolation.",
    )
    args = parser.parse_args()
    results = []
    classified = Counter()
    for path in sorted(args.directory.glob("*.json")):
        doc = load(path)
        variants = [{}]
        if args.parameter_limits:
            for key, bounds in doc.get("parameters", {}).items():
                variants.extend(
                    {key: value}
                    for value in sorted(
                        {bounds["min"], bounds["max"]} - {bounds["default"]}
                    )
                )
        for params in variants:
            try:
                row = audit(Program(doc, params), args.fps, args.samples)
            except (Error, ValueError) as e:
                row = {
                    "samples": 0,
                    "issues": [
                        {"code": getattr(e, "code", "invalid-input"), "message": str(e)}
                    ],
                }
            row.update(id=doc["id"], eml=doc["eml"], parameters=params)
            results.append(row)
            classified.update({r["code"] for r in row["issues"]})
    report = {
        "profile": "studio-humanoid/1.1",
        "fps": args.fps,
        "minimumSamplesPerPhase": args.samples,
        "parameterLimits": args.parameter_limits,
        "programs": len(results),
        "exercises": len({r["id"] for r in results}),
        "samples": sum(r["samples"] for r in results),
        "programsWithFindings": sum(bool(r["issues"]) for r in results),
        "programsByFinding": dict(sorted(classified.items())),
        "results": results,
    }
    args.output.write_text(json.dumps(report, allow_nan=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
