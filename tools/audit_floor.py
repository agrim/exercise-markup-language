"""Measure the lowest skinned atlas vertex across EML phases. Optional: numpy and scipy."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eml import Program, load


def build_surface(model):
    vertex = np.dtype(
        [
            ("pos", "<f4", 3),
            ("normal", "<f4", 3),
            ("joints", "u1", 4),
            ("weights", "u1", 4),
            ("group", "<u4"),
            ("packed", "<u4"),
        ]
    )
    verts = np.fromfile(ROOT / "anatomy/vertices.bin", vertex)
    j = verts["joints"].astype(int)
    w = verts["weights"].astype(float) / 255
    rest = np.array([x["position"] for x in model["joints"]])
    xyz = verts["pos"][:, None, :] - rest[j]
    xyzw = np.concatenate((xyz, np.ones((*xyz.shape[:2], 1))), axis=-1)
    rows = np.broadcast_to(np.arange(len(verts))[:, None, None], xyzw.shape)
    cols = j[:, :, None] * 4 + np.arange(4)
    m = coo_matrix(
        ((xyzw * w[:, :, None]).ravel(), (rows.ravel(), cols.ravel())),
        shape=(len(verts), len(rest) * 4),
    ).tocsr()
    m.eliminate_zeros()
    return m


def audit(num=5):
    model = load(ROOT / "anatomy/model.json")
    surface = build_surface(model)
    joints = model["joints"]
    out = {}
    for path in sorted((ROOT / "exercises").glob("*.json")):
        p = Program(load(path))
        extrema = []
        for i in range(len(p.doc["phases"])):
            for k in range(num):
                f = p.segment(i, k / (num - 1))
                rotations = Rotation.from_quat(
                    [f["rotations"][j["name"]] for j in joints]
                ).as_matrix()
                for n, j in enumerate(joints):
                    if j["parent"] >= 0:
                        rotations[n] = rotations[j["parent"]] @ rotations[n]
                y = np.array([f["positions"][j["name"]][1] for j in joints])
                columns = np.column_stack((rotations[:, 1, :], y)).ravel()
                extrema.append(float((surface @ columns).min()))
        out[p.doc["id"]] = [round(min(extrema), 4), round(max(extrema), 4)]
    return {"samplesPerPhase": num, "units": "metres", "lowestVertexRanges": out}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    a = parser.parse_args()
    a.o.write_text(json.dumps(audit(a.samples), indent=2) + "\n")
