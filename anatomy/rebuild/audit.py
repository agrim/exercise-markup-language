"""Check the shipped anatomy bytes and surface visibility in six orthographic views."""

import argparse
import json
from pathlib import Path

import numpy as np
from build import DTYPE
from embreex.mesh_construction import TriangleMesh
from embreex.rtcore_scene import EmbreeScene


def audit(base):
    model = json.loads((base / "model.json").read_text())
    vertices = np.fromfile(base / "vertices.bin", DTYPE)
    faces = np.fromfile(base / "indices.bin", "<u4").reshape((-1, 3))
    assert vertices.size == model["vertexCount"] and faces.size == model["indexCount"]
    assert np.all(np.isfinite(vertices["p"])) and np.all(np.isfinite(vertices["n"]))
    assert np.max(np.abs(np.linalg.norm(vertices["n"], axis=1) - 1)) < 1e-5
    assert len(vertices) > faces.max() and vertices["g"].max() < len(model["groups"])
    assert vertices["j"].max() < len(model["joints"])
    assert np.all(vertices["w"].sum(1) == 255)
    assert np.all((vertices["reserved"] >= 1) & (vertices["reserved"] <= 255))
    for i, j in enumerate(model["joints"]):
        assert j["parent"] == -1 if i == 0 else 0 <= j["parent"] < i
    seen = 0
    for part in model["parts"]:
        assert part["firstIndex"] == seen and part["indexCount"] % 3 == 0
        batch = faces[seen // 3 : (seen + part["indexCount"]) // 3]
        gid = model["groups"].index(part["group"])
        assert np.all(vertices["g"][batch] == gid)
        seen += part["indexCount"]
    assert seen == faces.size
    w, h = 410, 900
    x, y = np.meshgrid(
        (np.arange(w) - (w - 1) / 2) / 500, (h - np.arange(h) - 22) / 500
    )
    x, y = x.ravel(), y.ravel()
    scene = EmbreeScene()
    _geometry = TriangleMesh(scene, vertices["p"].copy(), faces.astype("i"))
    names = model["groups"]
    count = {}
    for angle in [0, 33, -52, 92, 143, 180]:
        c, s = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
        origins = np.column_stack([x * c + 1.8 * s, y, -x * s + 1.8 * c]).astype("f")
        directions = np.full_like(origins, [-s, 0, -c])
        rays = scene.run(origins, directions, query="INTERSECT")
        groups = vertices["g"][faces[rays[rays >= 0], 0]]
        count[str(angle)] = dict(
            zip(names, np.bincount(groups, minlength=len(names)).tolist())
        )
    front = count["0"]
    assert front["abdominals"] > 6500 and front["obliques"] > 4500
    assert front["pectorals"] > 6000 and front["upperPectorals"] > 1200
    assert count["180"]["lats"] > 4000 and count["180"]["glutes"] > 4500
    for muscle in names[4:]:
        assert max(view[muscle] for view in count.values()) > 0, muscle
    return {
        "vertices": len(vertices),
        "triangles": len(faces),
        "joints": len(model["joints"]),
        "muscleGroups": len(names[4:]),
        "sections": len(model["parts"]),
        "metersTall": float(np.ptp(vertices["p"][:, 1])),
        "firstHitPixelsByAzimuth": count,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("resources", type=Path)
    print(json.dumps(audit(p.parse_args().resources), indent=2))
