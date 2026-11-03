"""Atlas coordinates in mm converted to right-handed Y-up, +Z-anterior meters."""

import numpy as np
from scipy.spatial.transform import Rotation


def world(raw):
    p = np.asarray(raw, dtype=float)
    return (p[..., [0, 2, 1]] * [1, 1, -1] + [0, 78.13, -80]) / 1000


def unit(v):
    return v / np.linalg.norm(v)


def make_rig(points):
    joints = []
    contacts = {}
    grips = {}
    digit_segments = {}

    def joint(name, parent, p):
        names = [j["name"] for j in joints]
        joints.append(
            {
                "name": name,
                "parent": names.index(parent) if parent else -1,
                "position": np.round(world(p), 7).tolist(),
            }
        )

    # Centers in the DBCLS scanner frame. The mirrored joints follow this atlas's
    # bilaterally mirrored long bones. The femoral pivot is inside the head.
    body = [
        ("pelvis", None, [0, -77, 793]),
        ("spine", "pelvis", [0, -72, 889]),
        ("chest", "spine", [0, -58, 1066]),
        ("neck", "chest", [0, -62, 1376]),
        ("head", "neck", [0, -69, 1471]),
    ]
    for args in body:
        joint(*args)
    locations = [
        ("Clavicle", "chest", [15, -135, 1321]),
        ("UpperArm", "Clavicle", [160, -80, 1315]),
        ("Forearm", "UpperArm", [213, -73, 1047]),
        ("Hand", "Forearm", [251, -117, 807]),
        ("Thigh", "pelvis", [80, -77, 812]),
        ("Shin", "Thigh", [75, -81, 374]),
        ("Foot", "Shin", [73, -78, 3]),
        ("Toe", "Foot", [118, -180, -60]),
    ]
    for side, sign in [("left", 1), ("right", -1)]:
        for name, parent, p in locations:
            joint(
                side + name,
                side + parent if parent[0].isupper() else parent,
                np.array(p) * [sign, 1, 1],
            )

    def endpoint(bone, proximal):
        # Hand phalanges are elongated in the vertical direction in atlas bind.
        v = points(bone)
        z = v[:, 2]
        band = (z.max() - z < 4) if proximal else (z - z.min() < 4)
        return v[band].mean(0)

    for side, sign in [("left", 1), ("right", -1)]:
        contacts.update(
            {
                side + k: world(np.array(p) * [sign, 1, 1]).round(6).tolist()
                for k, p in [
                    ("Heel", [64, -43, -74]),
                    ("Ball", [115, -183, -75]),
                    ("Palm", [261, -154, 753]),
                    ("Grip", [261, -167, 735]),
                ]
            }
        )
        grips[side] = {}
        for finger in ["Thumb", "Index", "Middle", "Ring", "Little"]:
            part = f"{side} {finger.lower()}" + (" finger" if finger != "Thumb" else "")
            types = (
                ["proximal", "middle", "distal"]
                if finger != "Thumb"
                else ["proximal", "distal"]
            )
            names = [f"{side}{finger}{i + 1}" for i in range(len(types))]
            if finger == "Thumb":
                types = ["metacarpal"] + types
                names = [side + "ThumbBase"] + names
            start = []
            end = []
            for t in types:
                bone = (
                    f"{t} phalanx of {part}"
                    if t != "metacarpal"
                    else f"{side} first metacarpal bone"
                )
                start.append(endpoint(bone, True))
                end.append(endpoint(bone, False))
            for i, name in enumerate(names):
                p = start[i] if i == 0 else (start[i] + end[i - 1]) * 0.5
                joint(name, names[i - 1] if i else side + "Hand", p)
                a, b = world(p), world(end[i])
                digit_segments[name] = (a, b)
                # The four long fingers fold toward the palmar (+Z) surface.
                # Thumb opposes them obliquely across the palm.
                aim = unit(
                    np.array([-sign * 0.88, -0.1, 0.42])
                    if finger == "Thumb"
                    else np.array([0.0, 0.20, 1.0])
                )
                axis = unit(np.cross(unit(b - a), aim))
                degrees = ([21, 34, 34] if finger == "Thumb" else [49, 64, 30])[i]
                grips[side][name] = (
                    Rotation.from_rotvec(axis * np.deg2rad(degrees))
                    .as_quat()
                    .round(7)
                    .tolist()
                )
    return {
        "joints": joints,
        "landmarks": contacts,
        "handBindings": grips,
    }, digit_segments
