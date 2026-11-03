"""EML 1.1 assertions measure the solved pose. They do not alter IK or clamp authored motion."""

from math import acos, asin, atan2, degrees, hypot

from .data import Error
from .kinematics import (
    AXES,
    IDENTITY,
    ZERO,
    add,
    cross,
    dot,
    inverse,
    multiply,
    quaternion,
    rotate,
    scale,
    sub,
    unit,
)


def clamp(value, low, high):
    return min(high, max(low, value))


def segment_distance(a, b, c, d):
    """Shortest Euclidean distance between two closed segments (also handles points/parallel lines)."""
    u, v, w = sub(b, a), sub(d, c), sub(a, c)
    aa, bb, cc, dd, ee = dot(u, u), dot(u, v), dot(v, v), dot(u, w), dot(v, w)
    if aa <= 1e-16:
        s = 0.0
        t = clamp(ee / cc, 0, 1) if cc > 1e-16 else 0.0
    elif cc <= 1e-16:
        t, s = 0.0, clamp(-dd / aa, 0, 1)
    else:
        determinant = aa * cc - bb * bb
        s = (
            clamp((bb * ee - cc * dd) / determinant, 0, 1)
            if determinant > aa * cc * 1e-12
            else 0.0
        )
        t = (bb * s + ee) / cc
        if t < 0:
            t, s = 0.0, clamp(-dd / aa, 0, 1)
        elif t > 1:
            t, s = 1.0, clamp((bb - dd) / aa, 0, 1)
    return hypot(*sub(add(a, scale(u, s)), add(c, scale(v, t))))


def bend(local, rest, axis):
    """Signed bend in the parent's hinge plane and deviation from the rest bone inclination.
    Rotating around the distal bone (e.g. pronating a forearm) does not by itself bend that bone.
    """
    rest = unit(rest)
    current = unit(rotate(local, rest))

    def planar(v):
        return sub(v, scale(axis, dot(v, axis)))

    r, c = planar(rest), planar(current)
    swing = degrees(
        asin(clamp(dot(current, axis), -1, 1)) - asin(clamp(dot(rest, axis), -1, 1))
    )
    if hypot(*r) < 1e-8 or hypot(*c) < 1e-8:
        return None, abs(swing)
    return degrees(atan2(dot(axis, cross(r, c)), dot(r, c))), abs(swing)


def angle(a, b):
    return degrees(atan2(hypot(*cross(a, b)), dot(a, b)))


def expand(name):
    return (
        ["left" + name[4:], "right" + name[4:]] if name.startswith("both") else [name]
    )


class SolvedFrame:
    def __init__(self, frame, rig):
        self.f, self.rig, self.worlds = frame, rig, {}

    def world(self, joint):
        if joint not in self.worlds:
            i = self.rig.index[joint]
            q = self.f["rotations"][joint]
            parent = self.rig.parents[i]
            self.worlds[joint] = (
                q if parent < 0 else multiply(self.world(self.rig.names[parent]), q)
            )
        return self.worlds[joint]

    def point(self, name, offset=ZERO):
        p = self.f["landmarks"].get(name)
        if p is None:
            p = self.f["positions"][name]
        if any(offset):
            joint, _ = self.rig.socket(name)
            p = add(p, rotate(self.world(joint), offset))
        return p

    def item_point(self, item, point):
        p = self.f["equipment"][item]
        return (
            p["sockets"][point]
            if isinstance(point, str)
            else add(p["position"], rotate(p["rotation"], point))
        )


# These deliberately broad animation envelopes belong to this rig's reference profile.
# They are not ranges of motion for people and aren't a substitute for checking form.
PROFILE = {
    "wristDeflection": 95.0,
    "wristRoll": 95.0,
    "elbow": (-165.0, 25.0, 55.0),
    "knee": (-12.0, 165.0, 45.0),
}
CORE = [("chest", "neck", 0.072), ("pelvis", "chest", 0.065), ("neck", "head", 0.045)]
for _side in ("left", "right"):
    CORE += [
        (_side + "Thigh", _side + "Shin", 0.042),
        (_side + "Shin", _side + "Foot", 0.027),
    ]


# A reference-player movement budget, in degrees per second. This covers
# major articulated joints; finger joints used to close a grip are separate.
MAJOR_JOINTS = (
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    *(
        side + joint
        for side in ("left", "right")
        for joint in (
            "Clavicle",
            "UpperArm",
            "Forearm",
            "Hand",
            "Thigh",
            "Shin",
            "Foot",
            "Toe",
        )
    ),
)
ANGULAR_SPEED = 720.0


def speed_findings(previous, current, cycle=0):
    if not previous:
        return []
    delta = current["time"] - previous["time"]
    if delta < 1e-7:
        return []
    findings = []
    for joint in MAJOR_JOINTS:
        start = previous["rotations"].get(joint)
        end = current["rotations"].get(joint)
        if start is None or end is None:
            continue
        arc = degrees(2 * acos(clamp(abs(dot(start, end)), 0.0, 1.0)))
        rate = arc / delta
        if arc > 0.02 and rate > ANGULAR_SPEED + 1e-5:
            findings.append(
                dict(
                    reason="fast-local-rotation",
                    effector=joint,
                    measured=rate,
                    limit=ANGULAR_SPEED,
                    residual=rate - ANGULAR_SPEED,
                    unit="deg/s",
                    phase=current["phase"],
                    time=current["time"],
                    cycle=cycle,
                    path="/eml",
                    message=f"{joint} turned at {rate:.1f} deg/s; the reference maximum is {ANGULAR_SPEED:g}. Lengthen this phase or reduce its movement.",
                )
            )
    return findings


def wrist(local, axis):
    # Measure local wrist contribution. Rotation inherited from the forearm does not appear here.
    deflection = angle(axis, rotate(local, axis))
    s = dot(local[:3], axis)
    if hypot(s, local[3]) < 1e-8:
        return (
            deflection,
            None,
        )  # 180-degree pure swing. Roll is undefined, deflection fails.
    roll = abs(degrees(2 * atan2(s, local[3]))) % 360
    return deflection, min(roll, 360 - roll)


def profile_rules(program):
    out = []
    for side in ("left", "right"):
        for part, label, child in (
            ("Forearm", "elbow", "Hand"),
            ("Shin", "knee", "Foot"),
        ):
            low, high, cross_limit = PROFILE[label]
            out.append(
                {
                    "kind": "hinge",
                    "joint": side + part,
                    "child": side + child,
                    "axis": AXES[0],
                    "min": low,
                    "max": high,
                    "maxSwing": cross_limit,
                    "path": "/eml",
                }
            )
        hand = side + "Hand"
        out.append(
            {
                "kind": "wrist",
                "joint": hand,
                "axis": unit(
                    program.solver.rig.offsets[program.solver.rig.index[hand]]
                ),
                "path": "/eml",
            }
        )
    out.append({"kind": "floor", "path": "/eml"})
    for item in program.equipment:
        spec = program.kit[item["kind"]]
        if spec["category"] != "free-weight":
            continue
        for part in spec.get("visual", []):
            shape = part["shape"]
            size = part["dimensions"]
            orient = quaternion(part["rotation"])

            def at(p, origin=part["position"], q=orient):
                return add(origin, rotate(q, p))

            # Inner proxies: do not extend rods past their flat caps. Plates and fixed stations
            # are outside this automatic rule; authors may identify extra geometry explicitly.
            if shape in ("barbell", "dumbbell", "rod"):
                radius = 0.0145 if shape in ("barbell", "dumbbell") else min(size) / 2
                extent = max(0, size[0] / 2 - radius)
                start, end = at((-extent, 0, 0)), at((extent, 0, 0))
            elif shape in ("ball", "kettlebell"):
                radius = min(size) / 2
                center = (
                    (0, -(1.55 * size[2] / 2 + 0.02), 0)
                    if shape == "kettlebell"
                    else ZERO
                )
                start = end = at(center)
            else:
                continue
            for a, b, r in CORE:
                out.append(
                    dict(
                        kind="clearance",
                        item=item["id"],
                        **{"from": start, "to": end},
                        radius=radius,
                        bodyFrom=a,
                        bodyTo=b,
                        bodyRadius=r,
                        min=-0.005,
                        path="/eml",
                    )
                )
    return out


class Constraints:
    def __init__(self, program):
        self.rig = program.solver.rig
        phase_ids = {p["id"] for p in program.doc["phases"]}
        self.phases = {name: [] for name in phase_ids}
        defaults = []
        for rule in profile_rules(program):
            if rule["kind"] in ("wrist", "floor", "clearance"):
                defaults.append(rule)
            else:
                defaults.extend(self.bind(rule, "/eml", program))
        for rules in self.phases.values():
            rules.extend(defaults)
        for index, rule in enumerate(program.doc.get("constraints", [])):
            base = "/constraints/" + str(index)
            phases = set(rule.get("phases", phase_ids))
            if not phases <= phase_ids:
                raise Error(
                    "unknown-phase",
                    base + "/phases",
                    ", ".join(sorted(phases - phase_ids)),
                )
            parsed = self.bind(rule, base, program)
            for phase in phases:
                self.phases[phase].extend(parsed)

    def bind(self, rule, base, program):
        kind = rule["kind"]

        def require(condition, field, message):
            if not condition:
                raise Error("invalid-constraint", base + "/" + field, message)

        def joint(name, field):
            require(name in self.rig.index, field, "Unknown joint " + name)
            return name

        def point(name, field):
            try:
                self.rig.socket(name)
            except ValueError as exc:
                raise Error("invalid-constraint", base + "/" + field, str(exc)) from exc

        def equipment(name, field):
            require(name in program.items, field, "Unknown equipment instance " + name)
            return program.kit[program.items[name]["kind"]]

        def direction(value, field):
            require(hypot(*value) > 1e-8, field, "A direction must be nonzero")
            return unit(value)

        r = dict(rule, path=base)
        if kind in ("hinge", "support"):
            require(r["min"] <= r["max"], "min", "Minimum must not exceed maximum")
        if kind == "clearance":
            kit = equipment(r["item"], "item")
            for key in ("from", "to"):
                if isinstance(r[key], str):
                    require(
                        r[key] in kit["sockets"],
                        key,
                        "Unknown equipment socket " + r[key],
                    )
            point(r["bodyFrom"], "bodyFrom")
            point(r["bodyTo"], "bodyTo")
            return [r]
        if kind == "support":
            point(r["landmark"], "landmark")
            surface = r["surface"]
            if surface != "floor":
                kit = equipment(surface["item"], "surface/item")
                parts = kit["visual"]
                index = surface["part"]
                require(
                    index < len(parts) and parts[index]["shape"] == "box",
                    "surface/part",
                    "Choose the index of a box component with a top face",
                )
                r["box"] = parts[index]
            return [r]
        r["axis"] = direction(r["axis"], "axis")
        if kind == "orientation":
            r["direction"] = direction(r["direction"], "direction")
            ref = r.get("relativeTo", {})
            if "joint" in ref:
                joint(ref["joint"], "relativeTo/joint")
            if "item" in ref:
                equipment(ref["item"], "relativeTo/item")
        result = []
        for target in expand(r["joint"]):
            joint(target, "joint")
            extra = {}
            if kind == "hinge":
                parent = self.rig.index[target]
                children = [i for i, p in enumerate(self.rig.parents) if p == parent]
                if "child" in r:
                    child = r["child"]
                    if child.startswith("both"):
                        side = "left" if target.startswith("left") else "right"
                        child = side + child[4:]
                    joint(child, "child")
                    idx = self.rig.index[child]
                    require(
                        idx in children, "child", "Expected a direct child of " + target
                    )
                else:
                    require(
                        len(children) == 1,
                        "child",
                        "Specify a direct child of " + target,
                    )
                    idx = children[0]
                rest = self.rig.offsets[idx]
                require(
                    hypot(*cross(r["axis"], rest)) > 1e-8,
                    "axis",
                    "The hinge axis must not be parallel to the measured bone",
                )
                extra["rest"] = rest
            result.append(dict(r, joint=target, **extra))
        return result

    def diagnose(self, frame, cycle=0):
        rules = self.phases.get(frame["phase"])
        if not rules:
            return []
        sample = SolvedFrame(frame, self.rig)
        result = []

        def measure(rule, subject, code, value, bounds, units):
            lower, upper = bounds
            limit = lower if lower is not None and value < lower else upper
            if limit is None or (
                (lower is None or value >= lower - 1e-7)
                and (upper is None or value <= upper + 1e-7)
            ):
                return
            result.append(
                {
                    "reason": code,
                    "effector": subject,
                    "residual": abs(value - limit),
                    "unit": units,
                    "measured": value,
                    "limit": limit,
                    "path": rule["path"],
                    "phase": frame["phase"],
                    "time": frame["time"],
                    "cycle": cycle,
                    "message": f"{subject}: {code}; measured {value:.4f} {units}, limit {limit:.4f} {units}",
                }
            )

        for r in rules:
            k = r["kind"]
            if k == "wrist":
                name = r["joint"]
                tilt, roll = wrist(frame["rotations"][name], r["axis"])
                measure(
                    r,
                    name,
                    "wrist-deflection",
                    tilt,
                    (None, PROFILE["wristDeflection"]),
                    "deg",
                )
                if roll is not None:
                    measure(
                        r, name, "wrist-roll", roll, (None, PROFILE["wristRoll"]), "deg"
                    )
            elif k == "floor":
                name, height = min(
                    (
                        (j, p[1])
                        for points in (frame["positions"], frame["landmarks"])
                        for j, p in points.items()
                    ),
                    key=lambda pair: pair[1],
                )
                measure(r, name, "below-floor", height, (-0.012, None), "m")
            elif k == "hinge":
                name = r["joint"]
                signed, swing = bend(frame["rotations"][name], r["rest"], r["axis"])
                measure(r, name, "hinge-off-axis", swing, (None, r["maxSwing"]), "deg")
                if signed is not None:
                    measure(r, name, "hinge-bend", signed, (r["min"], r["max"]), "deg")
                elif swing <= r["maxSwing"] and (r["min"] > -180 or r["max"] < 180):
                    # The distal bone points along the hinge axis; no signed in-plane angle exists.
                    result.append(
                        {
                            "reason": "undefined-hinge-bend",
                            "effector": name,
                            "residual": 0.0,
                            "unit": "deg",
                            "path": r["path"],
                            "phase": frame["phase"],
                            "time": frame["time"],
                            "cycle": cycle,
                            "message": f"{name}: signed bend is undefined on the hinge axis",
                        }
                    )
            elif k == "orientation":
                ref = r.get("relativeTo", {})
                reference = (
                    sample.world(ref["joint"])
                    if "joint" in ref
                    else (
                        frame["equipment"][ref["item"]]["rotation"]
                        if "item" in ref
                        else IDENTITY
                    )
                )
                measured = angle(
                    rotate(sample.world(r["joint"]), r["axis"]),
                    rotate(reference, r["direction"]),
                )
                measure(
                    r,
                    r["joint"],
                    "joint-direction",
                    measured,
                    (None, r["maxAngle"]),
                    "deg",
                )
            elif k == "clearance":
                dist = segment_distance(
                    sample.item_point(r["item"], r["from"]),
                    sample.item_point(r["item"], r["to"]),
                    sample.point(r["bodyFrom"]),
                    sample.point(r["bodyTo"]),
                )
                gap = dist - r["radius"] - r["bodyRadius"]
                measure(
                    r,
                    r["item"] + "/" + r["bodyFrom"] + "–" + r["bodyTo"],
                    "equipment-clearance",
                    gap,
                    (r.get("min", 0), None),
                    "m",
                )
            elif k == "support":
                p = sample.point(r["landmark"], r.get("offset", ZERO))
                if r["surface"] == "floor":
                    gap = p[1]
                else:
                    part = r["box"]
                    shape = frame["equipment"][r["surface"]["item"]]
                    local = rotate(
                        inverse(shape["rotation"]), sub(p, shape["position"])
                    )
                    u, v, w = rotate(
                        inverse(quaternion(part["rotation"])),
                        sub(local, part["position"]),
                    )
                    x, y, z = (n / 2 for n in part["dimensions"])
                    edge = hypot(max(abs(u) - x, 0), max(abs(w) - z, 0))
                    measure(
                        r,
                        r["landmark"],
                        "support-edge",
                        edge,
                        (None, r.get("edgeTolerance", 0)),
                        "m",
                    )
                    gap = v - y
                measure(r, r["landmark"], "support-gap", gap, (r["min"], r["max"]), "m")
        return result
