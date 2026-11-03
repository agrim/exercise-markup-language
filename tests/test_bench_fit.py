"""Support belongs to the rendered face of the pad, including its finite width and length."""
import importlib.util
import unittest

from eml import Program, load
from eml.data import ROOT

EXERCISES = (
    "arnold-press", "dumbbell-shoulder-press", "overhead-dumbbell-triceps-extension",
    "incline-bench-press", "incline-dumbbell-press", "incline-dumbbell-curl",
    "decline-bench-press", "chest-supported-dumbbell-row", "leg-press",
)


class BenchSupportTests(unittest.TestCase):
    def test_moving_the_support_out_from_under_the_body_fails_a_contact_check(self):
        for name in EXERCISES:
            with self.subTest(name=name):
                doc = load(ROOT / "exercises" / f"{name}.json")
                self.assertFalse(Program(doc).sample(0)["diagnostics"])
                # Same rig and pose, but shift the apparatus 30 cm to the athlete's left.
                doc["equipment"][0]["position"][0] += .30
                failures = Program(doc).sample(0)["diagnostics"]
                self.assertTrue(any(f["reason"] == "support-edge" for f in failures))

    @unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                         "The skin-surface oracle uses the optional floor-audit dependencies")
    def test_actual_torso_and_thigh_mesh_stays_out_of_support_pads_and_steel(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        from eml.data import registry
        from tools.audit_floor import build_surface, read_vertices

        model = registry()[3]
        joints = model["joints"]
        names = [j["name"] for j in joints]
        vertices = read_vertices()
        owners = vertices["joints"][np.arange(len(vertices)), vertices["weights"].argmax(axis=1)]
        torso = {"pelvis", "spine", "chest", "neck", "head"}
        regions = torso | {"leftThigh", "rightThigh"}
        selected = np.isin(owners, [names.index(k) for k in regions])
        is_torso = np.isin(owners[selected], [names.index(k) for k in torso])
        surface = build_surface(model)[selected]

        for name in EXERCISES:
            p = Program(load(ROOT / "exercises" / f"{name}.json"))
            apparatus = p.equipment[0]
            parts = p.kit[apparatus["kind"]]["visual"]
            back = {"leg-press": 8, "chest-supported-dumbbell-row": 0}.get(name, 1)
            for phase in range(len(p.doc["phases"])):
                for fraction in (0, .5, 1):
                    with self.subTest(name=name, phase=phase, fraction=fraction):
                        frame = p.segment(phase, fraction)
                        world = Rotation.from_quat([frame["rotations"][j] for j in names]).as_matrix()
                        for i, joint in enumerate(joints):
                            if joint["parent"] >= 0:
                                world[i] = world[joint["parent"]] @ world[i]
                        position = np.array([frame["positions"][j] for j in names])
                        transforms = np.concatenate((world.transpose(0, 2, 1), position[:, None, :]), axis=1)
                        body = surface @ transforms.reshape(-1, 3)
                        item = frame["equipment"][apparatus["id"]]
                        local = Rotation.from_quat(item["rotation"]).inv().apply(body - item["position"])
                        for index, part in enumerate(parts):
                            if part["shape"] != "box":
                                continue
                            half = np.array(part["dimensions"]) / 2
                            plane = Rotation.from_euler("xyz", part["rotation"], degrees=True)
                            points = plane.inv().apply(local - part["position"])
                            depth = np.min(half - abs(points), axis=1)
                            self.assertLess(np.max(depth), .004, f"body inside {part['material']} part {index}")
                            if index == back:
                                within = is_torso & (abs(points[:, 0]) <= half[0]) & (abs(points[:, 2]) <= half[2])
                                self.assertTrue(np.any(within), "torso misses the finite support")
                                self.assertAlmostEqual(np.min(points[within, 1]) - half[1], 0, delta=.005)
