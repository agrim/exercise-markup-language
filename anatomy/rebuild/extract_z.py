"""Run inside Blender on Z-Anatomy's original Startup.blend. No add-ons required."""

import sys
from pathlib import Path

import bpy
import numpy as np

out = Path(sys.argv[sys.argv.index("--") + 1])
out.mkdir(parents=True, exist_ok=True)
# Reference bone surfaces give a similarity registration in case the two atlas
# coordinate frames differ. They are excluded from the final drawable mesh.
labels = [
    "Latissimus dorsi muscle",
    "Rectus abdominis muscle",
    "Internal abdominal oblique muscle",
    "Transversus abdominis muscle",
    "Quadratus lumborum muscle",
    "Humerus",
    "Femur",
    "Tibia",
    "Clavicle",
]
for label in labels:
    for side, letter in [("left", "l"), ("right", "r")]:
        name = f"{label}.{letter}"
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise KeyError(name)
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        vertices = np.array([tuple(obj.matrix_world @ v.co) for v in mesh.vertices])
        triangles = np.array(
            [tuple(p.vertices) for p in mesh.loop_triangles], dtype=np.int32
        )
        # Several right-side atlas objects use a negative object scale.
        if obj.matrix_world.to_3x3().determinant() < 0:
            triangles = triangles[:, ::-1]
        np.savez(out / f"{side}_{label}.npz", v=vertices, f=triangles)
        print(name, len(vertices), vertices.min(0), vertices.max(0))
        evaluated.to_mesh_clear()
