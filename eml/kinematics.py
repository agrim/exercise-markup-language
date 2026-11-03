"""Forward kinematics and deterministic two-link contact solving for the reference rig.

Positions and offsets are metres in a right-handed frame (+X left, +Y up,
+Z forward). Unit quaternions use [x, y, z, w]. The bind orientations are
identity, so local axes coincide with world axes in the rest pose.
"""

from __future__ import annotations

from math import acos, atan2, cos, degrees, hypot, isfinite, radians, sin, sqrt

IDENTITY = (0.0, 0.0, 0.0, 1.0)
ZERO = (0.0, 0.0, 0.0)
AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
EPSILON = 1e-10


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def scale(a, value):
    return tuple(x * value for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def unit(a):
    norm = hypot(*a)
    if norm < EPSILON or not isfinite(norm):
        raise ValueError("undefined direction or rotation")
    return scale(a, 1.0 / norm)


def multiply(a, b):
    """Hamilton product. The b transformation happens first."""
    av, bv = a[:3], b[:3]
    xyz = add(add(scale(bv, a[3]), scale(av, b[3])), cross(av, bv))
    return (*xyz, a[3] * b[3] - dot(av, bv))


def inverse(q):
    return (-q[0], -q[1], -q[2], q[3])


def rotate(q, vector):
    twice = scale(cross(q[:3], vector), 2.0)
    return add(vector, add(scale(twice, q[3]), cross(q[:3], twice)))


def quaternion(degrees):
    """Right-handed rotations about fixed X, then Y, then Z."""
    x, y, z = (radians(a) / 2 for a in degrees)
    return multiply(
        (0, 0, sin(z), cos(z)), multiply((0, sin(y), 0, cos(y)), (sin(x), 0, 0, cos(x)))
    )


def align(a, b):
    u, v = unit(a), unit(b)
    d = max(-1.0, min(1.0, dot(u, v)))
    if d < -1.0 + EPSILON:
        axis = min(AXES, key=lambda candidate: abs(dot(candidate, u)))
        return (*unit(cross(u, axis)), 0.0)
    return unit((*cross(u, v), 1.0 + d))


def perpendicular(axis, preferred):
    """Resolve even parallel pole directions without changing limb lengths."""
    orthogonal = sub(preferred, scale(axis, dot(axis, preferred)))
    if hypot(*orthogonal) < EPSILON:
        fallback = min(AXES, key=lambda candidate: abs(dot(axis, candidate)))
        orthogonal = sub(fallback, scale(axis, dot(axis, fallback)))
    return unit(orthogonal)


class Rig:
    """A bind pose plus rigid landmarks. Joint names are the public address space."""

    def __init__(self, model):
        joints = model["joints"]
        self.names = [j["name"] for j in joints]
        self.index = {name: i for i, name in enumerate(self.names)}
        self.parents = [j["parent"] for j in joints]
        self.rest = [tuple(j["position"]) for j in joints]
        self.offsets = [
            rest if parent < 0 else sub(rest, self.rest[parent])
            for rest, parent in zip(self.rest, self.parents)
        ]
        self.landmarks = model.get("landmarks", {})
        self.bindings = model.get("handBindings", {})

    def socket(self, name):
        """Return the owning joint and point in that joint's local rest frame."""
        if name in self.index:
            return name, ZERO
        for side in ("left", "right"):
            for part, owner in (
                ("Palm", "Hand"),
                ("Grip", "Hand"),
                ("Heel", "Foot"),
                ("Ball", "Toe"),
            ):
                if name == side + part and name in self.landmarks:
                    joint = side + owner
                    return joint, sub(
                        self.landmarks[name], self.rest[self.index[joint]]
                    )
        raise ValueError(f"unknown rig socket {name!r}")


class Pose:
    def __init__(self, rig, root, local):
        self.rig = rig
        self.root = root
        self.local = list(local)
        self.positions = [ZERO] * len(rig.names)
        self.orientations = [IDENTITY] * len(rig.names)
        self.refresh()

    def refresh(self):
        for i, parent in enumerate(self.rig.parents):
            if parent < 0:
                self.positions[i] = add(self.root, self.rig.offsets[i])
                self.orientations[i] = self.local[i]
            else:
                self.positions[i] = add(
                    self.positions[parent],
                    rotate(self.orientations[parent], self.rig.offsets[i]),
                )
                self.orientations[i] = multiply(
                    self.orientations[parent], self.local[i]
                )

    def point(self, name):
        joint, offset = self.rig.socket(name)
        i = self.rig.index[joint]
        return add(self.positions[i], rotate(self.orientations[i], offset))

    def orient(self, i, target):
        parent = self.rig.parents[i]
        self.local[i] = unit(
            target
            if parent < 0
            else multiply(inverse(self.orientations[parent]), target)
        )

    def aim(self, i, child, direction):
        current = self.orientations[i]
        swing = align(rotate(current, self.rig.offsets[child]), direction)
        self.orient(i, multiply(swing, current))
        self.refresh()

    def endpoint(self, socket):
        """Name of IK tip and socket offset expressed in the tip's current frame."""
        joint, _ = self.rig.socket(socket)
        side = "left" if joint.startswith("left") else "right"
        part = joint[len(side) :]
        if part not in ("Hand", "Foot", "Toe"):
            raise ValueError(f"{socket!r} is not a two-link contact endpoint")
        tip = side + ("Foot" if part == "Toe" else part)
        i = self.rig.index[tip]
        offset = rotate(
            inverse(self.orientations[i]), sub(self.point(socket), self.positions[i])
        )
        return tip, offset

    def hinge_arm(
        self, upper, elbow, wrist, mid_vector, end_vector, end_rotation, pole
    ):
        """Reconstruct a flexing elbow from the solved triangle. Hand orientation remains exact.

        An unconstrained two-link IK has arbitrary roll about each link. The atlas elbow
        flexes towards negative local X. First place that plane, then rotate around the forearm shaft
        before assigning wrist orientation.
        """
        a, b = unit(self.rig.offsets[elbow]), unit(self.rig.offsets[wrist])
        u, v = unit(mid_vector), unit(end_vector)
        c = a[1] * b[1] + a[2] * b[2]
        s = a[2] * b[1] - a[1] * b[2]
        angle = atan2(s, c) - acos(
            max(-1.0, min(1.0, (dot(u, v) - a[0] * b[0]) / hypot(c, s)))
        )
        flex = (sin(angle / 2), 0.0, 0.0, cos(angle / 2))
        shoulder = align(a, u)
        predicted = rotate(shoulder, rotate(flex, b))
        across = sub(predicted, scale(u, dot(u, predicted)))
        desired = sub(v, scale(u, dot(u, v)))
        # At full reach the triangle provides no bend plane. The same elbow pole
        # continues it through extension instead of taking an arbitrary axial flip.
        if hypot(*desired) < 1e-6 and pole is not None:
            desired = scale(perpendicular(u, pole), -1.0)
        if hypot(*desired) < 1e-6 or hypot(*across) < 1e-6:
            prior = self.orientations[upper]
            shoulder = multiply(align(rotate(prior, a), u), prior)
        else:
            twist = atan2(dot(u, cross(across, desired)), dot(across, desired))
            shoulder = multiply((*scale(u, sin(twist / 2)), cos(twist / 2)), shoulder)
        forearm = multiply(shoulder, flex)
        forearm = multiply(align(rotate(forearm, b), v), forearm)
        rel = multiply(inverse(forearm), end_rotation)
        if rel[3] < 0:
            rel = scale(rel, -1)
        # The atlas binds with palms facing forward (supinated), not at midrange.
        # Choose the mirror-consistent pronation branch before limiting axial travel;
        # otherwise a target crossing +/-180 would snap between opposite limits.
        side = 1 if self.rig.names[wrist].startswith("left") else -1
        requested = side * degrees(2 * atan2(dot(rel[:3], b), rel[3]))
        requested = (requested + 110) % 360 - 110
        roll = radians(side * max(-20.0, min(165.0, requested)))
        forearm = multiply(forearm, (*scale(b, sin(roll / 2)), cos(roll / 2)))
        self.orient(upper, shoulder)
        self.local[elbow] = unit(multiply(inverse(shoulder), forearm))
        self.local[wrist] = unit(multiply(inverse(forearm), end_rotation))
        self.refresh()

    def reach(self, socket, target, pole=None, rotation=None, hinge_arms=False):
        joint, offset = self.endpoint(socket)
        side = "left" if joint.startswith("left") else "right"
        part = joint[len(side) :]
        upper, middle = ("UpperArm", "Forearm") if part == "Hand" else ("Thigh", "Shin")
        start, bend, end = (
            self.rig.index[side + label] for label in (upper, middle, part)
        )
        end_rotation = self.orientations[end] if rotation is None else rotation
        joint_target = sub(target, rotate(end_rotation, offset))
        ray = sub(joint_target, self.positions[start])
        length = hypot(*ray)
        if length < EPSILON:
            current = sub(self.positions[end], self.positions[start])
            ray = current if hypot(*current) >= EPSILON else (0.0, -1.0, 0.0)
        axis = unit(ray)
        a, b = hypot(*self.rig.offsets[bend]), hypot(*self.rig.offsets[end])
        d = max(abs(a - b), min(a + b, length), EPSILON)
        along = (a * a - b * b + d * d) / (2 * d)
        radial = sqrt(max(0.0, a * a - along * along))

        if pole is None:
            # If FK already matches, preserve its elbow/knee and all existing twist.
            if hypot(*sub(joint_target, self.positions[end])) < EPSILON and not (
                hinge_arms and socket.endswith("Palm")
            ):
                self.orient(end, end_rotation)
                self.refresh()
                return hypot(*sub(target, self.point(socket)))
            # Carry the authored bend plane onto the requested ray. Only a nearly
            # straight or fully folded limb needs a fallback anatomical guide.
            old_ray = sub(self.positions[end], self.positions[start])
            if hypot(*old_ray) > EPSILON:
                old_axis = unit(old_ray)
                mid = sub(self.positions[bend], self.positions[start])
                rejection = sub(mid, scale(old_axis, dot(mid, old_axis)))
                if hypot(*rejection) > 0.004:
                    pole = rotate(align(old_axis, axis), rejection)
            if pole is None:
                if part == "Foot":
                    pole = rotate(
                        self.orientations[self.rig.index["pelvis"]], (0, 0, 1)
                    )
                else:
                    pole = rotate(
                        self.orientations[self.rig.index["chest"]],
                        (1 if side == "left" else -1, -0.5, -0.5),
                    )
        mid_vector = add(scale(axis, along), scale(perpendicular(axis, pole), radial))
        end_vector = sub(scale(axis, d), mid_vector)
        if hinge_arms and socket.endswith("Palm"):
            self.hinge_arm(start, bend, end, mid_vector, end_vector, end_rotation, pole)
        else:
            self.aim(start, bend, mid_vector)
            self.aim(bend, end, end_vector)
            self.orient(end, end_rotation)
            self.refresh()
        return hypot(*sub(target, self.point(socket)))


class Kinematics:
    """Sample one pose. Object sockets are local to each rigid equipment item.

    A following object's offset and rotation are local to its driving joint.
    A stationary object's position and rotation are in world space. Contacts
    solve the arm or leg owning the requested hand or foot landmark. Keeping
    both contacts of one rigid limb uses their separation to orient that limb.
    """

    tolerance = 0.012

    def __init__(self, model, equipment_registry, *, hinge_arms=False):
        self.hinge_arms = hinge_arms
        self.rig = Rig(model)
        self.registry = equipment_registry

    def equipment_pose(self, pose, item):
        rotation = quaternion(item.get("rotation", ZERO))
        if "follow" in item:
            follow = item["follow"]
            joint = self.rig.index[follow["joint"]]
            driver = pose.orientations[joint]
            rotation = multiply(driver, rotation)
            position = add(
                pose.positions[joint], rotate(driver, follow.get("offset", ZERO))
            )
        else:
            position = item.get("position", ZERO)
        sockets = {**self.registry[item["kind"]]["sockets"], **item.get("sockets", {})}
        return {
            "position": list(position),
            "rotation": list(rotation),
            "sockets": {
                name: list(add(position, rotate(rotation, offset)))
                for name, offset in sockets.items()
            },
        }

    def target(self, contact, pose, items, anchors):
        value = contact["target"]
        if value == "start" or value == "floor":
            point = anchors[contact["effector"]]
            return (point[0], 0.0, point[2]) if value == "floor" else point
        if "point" in value:
            return value["point"]
        equipment = self.equipment_pose(pose, items[value["item"]])
        return equipment["sockets"][value["socket"]]

    def limb_of_joint(self, joint):
        """Any socket driven by this limb must be evaluated after its contacts."""
        i = self.rig.index[joint]
        while i >= 0:
            name = self.rig.names[i]
            for side in ("left", "right"):
                if name == side + "UpperArm":
                    return side + "Hand"
                if name == side + "Thigh":
                    return side + "Foot"
            i = self.rig.parents[i]
        return None

    def solve_group(self, pose, contacts, items, anchors):
        targets = [self.target(c, pose, items, anchors) for c in contacts]
        lead = contacts[0]
        tip, local_point = pose.endpoint(lead["effector"])
        prescribed = next((c["rotation"] for c in contacts if "rotation" in c), None)
        pole = next((c["pole"] for c in contacts if "pole" in c), None)
        if prescribed is not None:
            rotation = quaternion(prescribed)
        else:
            rotation = pose.orientations[self.rig.index[tip]]
            # One point can translate the tip, but two constrain its direction.
            for contact, target in zip(contacts[1:], targets[1:]):
                _, other_point = pose.endpoint(contact["effector"])
                source = rotate(rotation, sub(other_point, local_point))
                goal = sub(target, targets[0])
                if hypot(*source) > EPSILON and hypot(*goal) > EPSILON:
                    rotation = multiply(align(source, goal), rotation)
                    break
        pose.reach(
            lead["effector"], targets[0], pole, rotation, hinge_arms=self.hinge_arms
        )

    def sample(self, root, joints, equipment, contacts, start_anchors=None):
        """Return local quaternions, world joints and landmarks, props and residuals.

        start_anchors holds stable world landmarks sampled once at setup. If
        omitted (when establishing the start pose), use the input FK landmarks.
        IK is positional unless a contact supplies the tip's world rotation.
        Independent limbs are solved deterministically in dependency order.
        """
        rig = self.rig
        local = [IDENTITY] * len(rig.names)
        for name, angles in joints.items():
            local[rig.index[name]] = quaternion(angles)
        grip_sides = set()
        for item in equipment:
            driver = item.get("follow", {})
            if driver.get("grip"):
                if driver["joint"] not in ("leftHand", "rightHand"):
                    raise ValueError("a gripping driver must be leftHand or rightHand")
                grip_sides.add(driver["joint"][: -len("Hand")])
        for claim in contacts:
            target = claim["target"]
            effector = claim["effector"]
            if (
                effector.endswith("Grip")
                and isinstance(target, dict)
                and "item" in target
            ):
                grip_sides.add(effector[: -len("Grip")])
        for side in grip_sides:
            for name, binding in rig.bindings.get(side, {}).items():
                if name not in joints:
                    local[rig.index[name]] = unit(binding)
        pose = Pose(rig, root, local)
        items = {item["id"]: item for item in equipment}
        anchors = (
            {name: pose.point(name) for name in rig.landmarks}
            if start_anchors is None
            else start_anchors
        )
        groups = {}
        for contact in sorted(contacts, key=lambda c: c["effector"]):
            limb, _ = pose.endpoint(contact["effector"])
            groups.setdefault(limb, []).append(contact)
        dependencies = {limb: set() for limb in groups}
        for limb, claims in groups.items():
            for claim in claims:
                target = claim["target"]
                if not isinstance(target, dict) or "item" not in target:
                    continue
                follow = items[target["item"]].get("follow")
                if follow:
                    driver = self.limb_of_joint(follow["joint"])
                    if driver in groups:
                        dependencies[limb].add(driver)
        remaining = set(groups)
        while remaining:
            ready = sorted(
                limb for limb in remaining if not dependencies[limb] & remaining
            )
            if not ready:
                break  # A cycle (or its dependent); report it with the final residual.
            for limb in ready:
                self.solve_group(pose, groups[limb], items, anchors)
            remaining.difference_update(ready)

        diagnostics = []
        landmarks = {name: list(pose.point(name)) for name in rig.landmarks}
        for limb, claims in groups.items():
            for claim in claims:
                target = self.target(claim, pose, items, anchors)
                achieved = pose.point(claim["effector"])
                residual = hypot(*sub(target, achieved))
                orientation_error = 0.0
                if "rotation" in claim:
                    q = pose.orientations[rig.index[limb]]
                    orientation_error = degrees(
                        2 * acos(min(1.0, abs(dot(q, quaternion(claim["rotation"])))))
                    )
                if limb in remaining:
                    reason = "cyclic-driver"
                elif residual > self.tolerance:
                    reason = "unreachable-contact"
                elif orientation_error > 0.1:
                    reason = "inconsistent-orientation"
                else:
                    continue
                diagnostics.append(
                    {
                        "reason": reason,
                        "effector": claim["effector"],
                        "target": list(target),
                        "achieved": list(achieved),
                        "residual": residual,
                        "orientationErrorDegrees": orientation_error,
                    }
                )
        return {
            "root": list(root),
            "positions": {name: list(x) for name, x in zip(rig.names, pose.positions)},
            "rotations": {name: list(x) for name, x in zip(rig.names, pose.local)},
            "landmarks": landmarks,
            "equipment": {
                name: self.equipment_pose(pose, item) for name, item in items.items()
            },
            "diagnostics": diagnostics,
        }
