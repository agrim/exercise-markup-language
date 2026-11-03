"""Bake the exercise atlas from the publisher archives; see README.md for commands."""

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh
from rig import make_rig, world
from surface import AnteriorFootprint, ambient_accessibility, recess_fascia, trunk_liner

GROUP_RULES = {
    "upperPectorals": "clavicular part of .*pectoralis major",
    "pectorals": "pectoralis",
    "anteriorDeltoids": "clavicular part of .*deltoid",
    "lateralDeltoids": "acromial part of .*deltoid",
    "posteriorDeltoids": "spinal part of .*deltoid",
    "biceps": "biceps brachii",
    "triceps": "triceps brachii|anconeus",
    "brachialis": r"\bbrachialis\b",
    "forearms": "brachioradialis|carpi|supinator|pronator|palmaris longus|pollicis longus|extensor digitorum(?! longus)|extensor indicis|extensor digiti minimi|flexor digitorum (superficialis|profundus)|extensor pollicis brevis",
    "quadriceps": "rectus femoris|vastus",
    "glutes": "gluteus maximus",
    "hipAbductors": "gluteus (medius|minimus)|tensor fasciae",
    "hamstrings": "biceps femoris|semitendinosus|semimembranosus",
    "adductors": "adductor (longus|magnus|brevis|minimus)|gracilis|pectineus",
    "footStabilizers": "fibularis|tibialis posterior|abductor hallucis$|abductor digiti minimi of .*foot",
    "gastrocnemius": "gastrocnemius",
    "soleus": "soleus",
    "tibialisAnterior": "tibialis anterior",
    "abdominals": "rectus abdominis|transversus abdominis",
    "obliques": "external oblique|internal abdominal oblique",
    "spinalErectors": "iliocostalis|spinalis|longissimus|quadratus lumborum",
    "lats": "latissimus dorsi",
    "upperTrapezius": "descending part of .*trapezius",
    "trapezius": "part of .*trapezius",
    "rhomboids": "rhomboid",
    "serratusAnterior": "serratus anterior",
    "rotatorCuff": "supraspinatus|infraspinatus|teres minor|subscapularis",
    "hipFlexors": "iliacus|psoas major|sartorius",
}
GROUPS = ["neutral", "bone", "tendon", "shell", *GROUP_RULES]
NEUTRAL = "sternocleidomastoid|scalenus|splenius|sternohyoid|omohyoid|external intercostal|teres major|coracobrachialis|levator scapulae|tibialis posterior|fibularis|extensor digitorum longus|flexor digitorum longus|flexor hallucis longus|extensor hallucis longus|serratus posterior|piriformis"
BONE = "humerus|scapula|clavicle|ulna$|radius$|hip bone|sacrum|lumbar vertebra|thoracic vertebra|cervical vertebra|atlas$|axis$|rib$|sternum|body of sternum|manubrium|xiphoid|femur$|tibia$|fibula$|patella$"
TENDON = "costal cartilage|calcaneal tendon|intervertebral disk"
BASE = "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/"
ARCHIVE = "isa_BP3D_4.0_obj_99.zip"
ZLABELS = [
    "Latissimus dorsi muscle",
    "Rectus abdominis muscle",
    "Internal abdominal oblique muscle",
    "Transversus abdominis muscle",
    "Quadratus lumborum muscle",
]
ELEMENTS = "isa_element_parts.txt"
DTYPE = np.dtype(
    [
        ("p", "<f4", 3),
        ("n", "<f4", 3),
        ("j", "u1", 4),
        ("w", "u1", 4),
        ("g", "<u4"),
        ("reserved", "<u4"),
    ]
)


def ramp(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def parse_obj(raw):
    vertices = np.fromstring(
        b" ".join(re.findall(rb"^v ([^\n]+)", raw, re.MULTILINE)), sep=" "
    ).reshape(-1, 3)
    rows = b" ".join(re.findall(rb"^f ([^\n]+)", raw, re.MULTILINE))
    faces = (
        np.fromstring(re.sub(rb"//[0-9]+", b"", rows), sep=" ", dtype=np.int32).reshape(
            -1, 3
        )
        - 1
    )
    return vertices, faces


def clipped(v, f, planes):
    for normal, origin in planes:
        v, f, _ = trimesh.intersections.slice_faces_plane(v, f, normal, origin)
    return v, f


def reduce_mesh(v, f, area_per_triangle, limit):
    # Fuse duplicate coordinates before quadric decimation. OBJ normal seams are
    # unnecessary on this satin single-material-per-structure surface.
    v, inv = np.unique(np.round(v, 5), axis=0, return_inverse=True)
    f = inv[f]
    cross = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    twice_area = np.linalg.norm(cross, axis=1)
    target = int(np.clip(twice_area.sum() * 0.5 / area_per_triangle, 48, limit))
    f = f[twice_area > 1e-8]
    if len(f) > target:
        v, f = fast_simplification.simplify(
            v, np.ascontiguousarray(f, np.int32), target_count=target, agg=5.0
        )
    used, inv = np.unique(f, return_inverse=True)
    return v[used], inv.reshape((-1, 3))


def normal_array(v, f):
    cross = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v)
    for ix in f.T:
        np.add.at(n, ix, cross)
    lengths = np.linalg.norm(n, axis=1)
    n[lengths < 1e-12] = [0, 1, 0]
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def skinning(v, name, group, rig, digits):
    x, y, z = v.T
    side = "left" if x.mean() > 0 else "right"
    table = np.zeros((len(v), len(rig)))
    ids = {j["name"]: i for i, j in enumerate(rig)}

    def single(j):
        table[:, ids[j]] = 1

    def transfer(a, b, factor):
        source = table[:, ids[a]] * factor
        table[:, ids[a]] -= source
        table[:, ids[b]] += source

    def start_torso():
        single("pelvis")
        transfer("pelvis", "spine", ramp(y, 0.917, 1.085))
        transfer("spine", "chest", ramp(y, 1.075, 1.24))

    limb = lambda j: side + j

    def arm():
        single(limb("UpperArm"))
        transfer(limb("UpperArm"), limb("Forearm"), 1 - ramp(y, 1.082, 1.16))
        transfer(limb("Forearm"), limb("Hand"), 1 - ramp(y, 0.864, 0.91))

    def leg():
        single(limb("Thigh"))
        transfer(limb("Thigh"), "pelvis", ramp(y, 0.846, 0.975))
        transfer(limb("Thigh"), limb("Shin"), 1 - ramp(y, 0.414, 0.492))
        transfer(limb("Shin"), limb("Foot"), 1 - ramp(y, 0.058, 0.112))

    if group == "shell":
        if "head" in name:
            single("neck")
            transfer("neck", "head", ramp(y, 1.491, 1.54))
        elif "foot" in name:
            single(limb("Foot"))
            transfer(limb("Foot"), limb("Shin"), ramp(y, 0.07, 0.117))
            transfer(limb("Foot"), limb("Toe"), ramp(z, 0.087, 0.13))
        else:
            single(limb("Hand"))
            transfer(limb("Hand"), limb("Forearm"), ramp(y, 0.867, 0.901))
            # Select the nearest finger's chain. Adjacent phalanges share weights
            # only near their hinge, while neighboring fingers remain independent.
            chains = {}
            for finger in ["Thumb", "Index", "Middle", "Ring", "Little"]:
                names = [n for n in digits if n.startswith(side + finger)]
                dist = []
                for n in names:
                    a, b = digits[n]
                    axis = b - a
                    t = np.clip((v - a) @ axis / (axis @ axis), 0, 1)
                    dist.append(np.linalg.norm(v - (a + t[:, None] * axis), axis=1))
                chains[finger] = (names, np.min(dist, axis=0))
            nearest = np.argmin([c[1] for c in chains.values()], axis=0)
            for k, (names, dist) in enumerate(chains.values()):
                mask = (nearest == k) * (1 - ramp(dist, 0.018, 0.031))
                last = limb("Hand")
                for i, n in enumerate(names):
                    a, b = digits[n]
                    axis = b - a
                    along = (v - a) @ axis / np.linalg.norm(axis)
                    transfer(
                        last, n, ramp(along, -0.008, 0.009) * (mask if i == 0 else 1)
                    )
                    last = n
    elif name == "inset trunk and neck":
        start_torso()
        transfer("chest", "neck", ramp(y, 1.42, 1.49))
        transfer("neck", "head", ramp(y, 1.5, 1.55))
    elif group == "bone":
        bone = None
        for pattern, j in [
            ("humerus", "UpperArm"),
            ("radius|ulna", "Forearm"),
            ("scapula|clavicle", "Clavicle"),
            ("femur", "Thigh"),
            ("fibula|tibia", "Shin"),
        ]:
            if re.search(pattern, name):
                bone = limb(j)
                break
        if "patella" in name:
            # The kneecap travels with the joint between femur and tibia.
            single(limb("Thigh"))
            transfer(limb("Thigh"), limb("Shin"), 0.48)
        elif bone:
            single(bone)
        elif "cervical" in name or name in ["atlas", "axis"]:
            single("neck")
        elif "rib" in name or re.search("sternum|manubrium|xiphoid", name):
            single("chest")
        else:
            start_torso()
    elif group in [
        "quadriceps",
        "hamstrings",
        "adductors",
        "hipAbductors",
        "glutes",
        "hipFlexors",
        "soleus",
        "gastrocnemius",
        "tibialisAnterior",
        "footStabilizers",
    ] or re.search(
        "calcaneal tendon|tibialis posterior|fibularis|digitorum longus|hallucis longus|piriformis",
        name,
    ):
        leg()
        if group in ["glutes", "hipAbductors"]:
            # Medial posterior origin remains attached to the sacrum.
            transfer(
                limb("Thigh"),
                "pelvis",
                (1 - ramp(abs(x), 0.035, 0.12)) * ramp(y, 0.81, 0.92),
            )
        if "psoas" in name:
            transfer("pelvis", "spine", ramp(y, 0.95, 1.15))
    elif (
        group
        in [
            "biceps",
            "brachialis",
            "triceps",
            "forearms",
            "anteriorDeltoids",
            "lateralDeltoids",
            "posteriorDeltoids",
        ]
        or "coracobrachialis" in name
    ):
        arm()
        if "deltoid" in name:
            transfer(limb("UpperArm"), limb("Clavicle"), 0.80 * ramp(y, 1.351, 1.431))
    elif group in ["rotatorCuff", "rhomboids"] or re.search(
        "teres major|levator scapulae", name
    ):
        single(limb("Clavicle"))
        if group == "rhomboids":
            transfer(limb("Clavicle"), "chest", 1 - ramp(abs(x), 0.019, 0.096))
        else:
            transfer(limb("Clavicle"), limb("UpperArm"), ramp(abs(x), 0.132, 0.169))
    elif re.search(
        "sternocleidomastoid|scalenus|splenius|sternohyoid|omohyoid|cervicis|capitis",
        name,
    ):
        single("chest")
        transfer("chest", "neck", ramp(y, 1.425, 1.496))
        transfer("neck", "head", ramp(y, 1.519, 1.568))
    else:
        start_torso()
        if group in ["pectorals", "upperPectorals", "lats"]:
            axilla = ramp(abs(x), 0.112, 0.168) * ramp(y, 1.266, 1.382)
            transfer("chest", limb("UpperArm"), axilla)
        if group in ["trapezius", "upperTrapezius"]:
            transfer(
                "chest",
                limb("Clavicle"),
                ramp(abs(x), 0.034, 0.125) * ramp(y, 1.276, 1.40),
            )
            transfer("chest", "neck", ramp(y, 1.46, 1.55))
    indices = np.argsort(-table, axis=1, kind="stable")[:, :4]
    weights = np.take_along_axis(table, indices, axis=1)
    assert np.allclose(table.sum(axis=1), 1)
    scaled = weights / weights.sum(1, keepdims=True) * 255
    packed = np.floor(scaled).astype("u1")
    # Assign remaining quantization units to largest fractional weights.
    order = np.argsort(-(scaled - packed), axis=1)
    remain = 255 - packed.sum(1)
    for k in range(4):
        packed[np.arange(len(v)), order[:, k]] += remain > k
    assert np.all(packed.sum(1) == 255)
    return indices, packed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cache", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def checked(path, sha):
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError(f"Unexpected input checksum: {path}")

    checked(
        args.cache / ARCHIVE,
        "40665852c49f218326590e204db91064a1ecfc3c6f8cbd7bbbcaac62c7cd409e",
    )
    checked(
        args.cache / ELEMENTS,
        "a3de74423f943b0d724ae8f59b3a817f87c423a544f8db98113b1980817cbeaf",
    )
    z = zipfile.ZipFile(args.cache / ARCHIVE)
    members = {Path(n).stem: n for n in z.namelist()}
    names = defaultdict(list)
    inverse = defaultdict(list)
    with (args.cache / ELEMENTS).open() as fid:
        rows = csv.reader(fid, delimiter="\t")
        next(rows)
        for _, name, k in rows:
            names[name].append(k)
            inverse[k].append(name)

    @lru_cache(maxsize=24)
    def bone(name):
        return parse_obj(z.read(members[names[name][0]]))[0]

    meta, digits = make_rig(bone)
    # Register the second atlas in mm to DBCLS using eight bilateral long bones.
    # Bounding-box extrema are consistently identifiable after decimation.
    s = []
    t = []
    for side in ["left", "right"]:
        for label in ["Humerus", "Femur", "Tibia", "Clavicle"]:
            a = np.load(args.cache / "zparts" / f"{side}_{label}.npz")["v"] * 1000
            b = bone(f"{side} {label.lower()}")
            s.extend([a.min(0), a.max(0)])
            t.extend([b.min(0), b.max(0)])
    s = np.array(s)
    t = np.array(t)
    scale = np.sum((s - s.mean(0)) * (t - t.mean(0)), axis=0) / np.sum(
        (s - s.mean(0)) ** 2, axis=0
    )
    offset = t.mean(0) - s.mean(0) * scale

    def supplement(side, label):
        npz = np.load(args.cache / "zparts" / f"{side}_{label}.npz")
        return npz["v"] * 1000 * scale + offset, npz["f"]

    def footprint(parts):
        vertices = []
        faces = []
        offset = 0
        for raw, f in parts:
            vertices.append(world(raw))
            faces.append(f + offset)
            offset += len(raw)
        return AnteriorFootprint(np.concatenate(vertices), np.concatenate(faces))

    rectus = footprint(
        [supplement(s, "Rectus abdominis muscle") for s in ["left", "right"]]
    )
    upper_pec = footprint(
        [
            parse_obj(z.read(members[k]))
            for k in names["clavicular part of pectoralis major"]
        ]
    )
    verts = []
    indices = []
    parts = []
    nv = ni = 0

    def add(raw_v, f, name, source, group):
        nonlocal nv, ni
        # More detail is retained at the face and in the finger silhouette.
        density, limit = (
            (13, 7200)
            if group == "shell"
            else (50, 1900)
            if group not in ["bone", "neutral", "tendon"]
            else (95, 650)
        )
        rv, f = reduce_mesh(raw_v, f, density, limit)
        v = world(rv)
        if group == "obliques" or "transversus abdominis" in name:
            recess_fascia(v, rectus)
        normals = normal_array(v, f)
        j, w = skinning(v, name, group, meta["joints"], digits)
        row = np.zeros(len(v), dtype=DTYPE)
        row["p"] = v
        row["n"] = normals
        row["j"] = j
        row["w"] = w
        row["g"] = GROUPS.index(group)
        sections = [(name, group, f)]
        if "sternocostal part" in name:
            center = v[f].mean(1)
            depth, inside = upper_pec.at(center)
            # Project the clavicular head onto the anterior overlap of the
            # pectoralis major. This preserves its true upper-chest footprint.
            mark = (
                (inside > -0.0005)
                & (center[:, 2] > depth - 0.001)
                & (center[:, 2] - depth < 0.084)
            )
            sections = [
                (name, group, f[~mark]),
                (
                    "clavicular head surface projection on " + name,
                    "upperPectorals",
                    f[mark],
                ),
            ]
        for label, g, faces in sections:
            if not len(faces):
                continue
            used, remap = np.unique(faces, return_inverse=True)
            subset = row[used].copy()
            subset["g"] = GROUPS.index(g)
            parts.append(
                {
                    "name": label,
                    "source": source,
                    "group": g,
                    "firstIndex": ni,
                    "indexCount": faces.size,
                }
            )
            verts.append(subset)
            indices.append(remap.ravel().astype("<u4") + nv)
            nv += len(used)
            ni += faces.size

    selected = set().union(
        *(
            names[c]
            for c in [
                "muscle organ",
                "zone of muscle organ",
                "head of muscle organ",
                "bone organ",
                "cartilage organ",
                "tendon",
            ]
        )
    )
    # These two trapezius subdivisions per side are classified as organ regions
    # outside 'zone of muscle organ' in the publisher's IS-A tree.
    for name in ["descending part of trapezius", "ascending part of trapezius"]:
        selected.update(names[name])
    for k in sorted(selected):
        raw = z.read(members[k])
        name = re.search(rb"# English name : (.*)", raw)[1].decode().strip().lower()
        if not name:
            name = min(inverse[k], key=lambda n: len(names[n]))
        group = next(
            (g for g, pattern in GROUP_RULES.items() if re.search(pattern, name)), None
        )
        if not group:
            if re.search(BONE, name):
                group = "bone"
            elif re.search(TENDON, name):
                group = "tendon"
            elif re.search(NEUTRAL, name):
                group = "neutral"
            else:
                continue
        v, f = parse_obj(raw)
        if name in ["atlas", "axis"] or len(v) == 0:
            continue
        # Once a tendon enters the hand or shoe-shaped foot skin, terminate the
        # hidden geometry. A fixed distal tendon would otherwise emerge from a
        # curled finger or dorsiflexed toe despite being invisible at bind.
        if (
            np.max(np.abs(v[:, 0])) > 195
            and v[:, 2].max() > 790
            and v[:, 2].min() < 819
            and group == "forearms"
        ):
            v, f = clipped(v, f, [([0, 0, 1], [0, 0, 818])])
        if v[:, 2].min() < 12 and group in [
            "footStabilizers",
            "neutral",
            "tendon",
            "tibialisAnterior",
            "soleus",
            "gastrocnemius",
        ]:
            if v[:, 2].max() < 14:
                continue
            v, f = clipped(v, f, [([0, 0, 1], [0, 0, 12])])
        if len(f):
            add(v, f, name, "BodyParts3D/" + k, group)
    # Retain only the skin regions that aid posture and floor/prop contact.
    v, f = parse_obj(z.read(members[names["skin"][0]]))
    full_skin = (world(v), f)
    for name, planes in (
        [("head shell", [([0, -0.32, 1], [0, -77, 1378])])]
        + [
            (
                side + " hand shell",
                [([sign, 0, 0], [sign * 195, 0, 0]), ([0, 0, -1], [0, 0, 849])],
            )
            for side, sign in [("left", 1), ("right", -1)]
        ]
        + [
            (
                side + " foot shell",
                [([sign, 0, 0], [0, 0, 0]), ([0, 0, -1], [0, 0, 53])],
            )
            for side, sign in [("left", 1), ("right", -1)]
        ]
    ):
        sv, sf = clipped(v, f, planes)
        # Selecting by x alone at the hand can also intersect the lateral thigh;
        # isolate the component containing the wrist, then remove tiny islands.
        piece = trimesh.Trimesh(sv, sf, process=True)
        comps = piece.split(only_watertight=False)
        piece = max(comps, key=lambda m: m.area)
        skin = np.asarray(piece.vertices).copy()
        up = skin[:, 2]
        if "head" in name:
            margin = up - 1378 - 0.32 * (skin[:, 1] + 77)
            center = [0, -67]
            taper = 1 - 0.14 * (1 - ramp(margin, 0, 28))
        elif "hand" in name:
            center = [np.sign(skin[:, 0].mean()) * 251, -112]
            taper = 1 - 0.22 * ramp(up, 817, 849)
        else:
            center = [np.sign(skin[:, 0].mean()) * 73, -78]
            taper = 1 - 0.20 * ramp(up, 18, 53)
        skin[:, :2] = center + (skin[:, :2] - center) * taper[:, None]
        if "head" in name:
            # The HP atlas skin includes the widening lower neck. Blend that cut
            # into the actual neck tissue instead of leaving a free collar edge.
            r = np.linalg.norm((skin[:, :2] - center) / [48, 57], axis=1)
            w = 1 - ramp(margin, 8, 57)
            skin[:, :2] = (
                center
                + (skin[:, :2] - center) * (1 - w + w / np.maximum(r, 1))[:, None]
            )
        add(skin, np.asarray(piece.faces), name, "BodyParts3D/FJ2810", "shell")
    for side in ["left", "right"]:
        for label in ZLABELS:
            a = np.load(args.cache / "zparts" / f"{side}_{label}.npz")
            name = side + " " + label.lower()
            group = next(g for g, r in GROUP_RULES.items() if re.search(r, name))
            add(
                a["v"] * 1000 * scale + offset,
                a["f"],
                name,
                "Z-Anatomy/" + label + "." + side[0],
                group,
            )
    driven = [
        "pectorals",
        "upperPectorals",
        "obliques",
        "abdominals",
        "lats",
        "glutes",
        "trapezius",
        "upperTrapezius",
        "spinalErectors",
        "rhomboids",
        "serratusAnterior",
    ]
    tissue = np.concatenate(
        [faces for faces, part in zip(indices, parts) if part["group"] in driven]
    )
    liner_v, liner_f = trunk_liner(
        *full_skin, np.concatenate(verts)["p"], tissue.reshape(-1, 3)
    )
    # The common emission path takes the original scanner coordinates in mm.
    raw = (liner_v * 1000 - [0, 78.13, -80])[:, [0, 2, 1]] * [1, -1, 1]
    add(raw, liner_f, "inset trunk and neck", "BodyParts3D/FJ2810/inset", "neutral")
    mesh = np.concatenate(verts)
    tri = np.concatenate(indices)
    assert (
        mesh.itemsize == 40 and tri.max() < len(mesh) and np.all(np.isfinite(mesh["p"]))
    )
    assert {p["group"] for p in parts} == set(GROUPS), set(GROUPS) - {
        p["group"] for p in parts
    }
    mesh["reserved"] = ambient_accessibility(mesh["p"], mesh["n"], tri.reshape(-1, 3))
    mesh.tofile(args.output / "vertices.bin")
    tri.tofile(args.output / "indices.bin")
    meta.update(version=1, groups=GROUPS, parts=parts, vertexCount=nv, indexCount=ni)
    (args.output / "model.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(
        f"{len(parts)} structures, {len(meta['joints'])} joints, {nv:,} vertices, {ni // 3:,} triangles, {(mesh.nbytes + tri.nbytes) / 1e6:.2f} MB"
    )
    print(
        "Z-Anatomy affine registration:",
        scale,
        offset,
        "extrema RMS mm",
        np.sqrt(np.mean((s * scale + offset - t) ** 2, axis=0)),
    )


if __name__ == "__main__":
    main()
