"""Offline surface exposure and accessibility for a compact, readable écorché."""

import numpy as np
from embreex.mesh_construction import TriangleMesh
from embreex.rtcore_scene import EmbreeScene
from scipy.ndimage import distance_transform_edt, map_coordinates


class AnteriorFootprint:
    """A coronal depth map of named source muscle, sampled on a 1 mm grid."""

    def __init__(self, vertices, faces):
        low = vertices[:, :2].min(0) - 0.022
        high = vertices[:, :2].max(0) + 0.022
        self.origin = low
        x, y = np.meshgrid(
            *(np.arange(a, b, 0.001) for a, b in zip(low, high)), indexing="ij"
        )
        origins = (
            np.stack([x, y, np.full_like(x, 0.4)], axis=-1).reshape(-1, 3).astype("f")
        )
        directions = np.zeros_like(origins)
        directions[:, 2] = -1
        scene = EmbreeScene()
        _geometry = TriangleMesh(scene, vertices.astype("f"), faces.astype("i"))
        depth = 0.4 - scene.run(origins, directions, query="DISTANCE").reshape(x.shape)
        valid = depth > -0.4
        dist, nearest = distance_transform_edt(~valid, return_indices=True)
        self.depth = depth[tuple(nearest)]
        self.signed = (distance_transform_edt(valid) - dist) * 0.001

    def at(self, pts):
        coordinates = ((pts[:, :2] - self.origin) * 1000).T
        depth = map_coordinates(self.depth, coordinates, order=1, mode="nearest")
        inside = map_coordinates(
            self.signed, coordinates, order=1, mode="constant", cval=-1.0
        )
        return depth, inside


def recess_fascia(v, reference):
    depth, inside = reference.at(v)
    # Feather the edge of the dissection. Only fascia anterior to the
    # measured rectus surface is moved back to the underlying layer.
    s = np.clip((inside + 0.012) / 0.015, 0, 1)
    s = s * s * (3 - 2 * s)
    v[:, 2] -= s * np.clip(v[:, 2] - depth + 0.004, 0, 0.035)


def ambient_accessibility(v, n, f):
    scene = EmbreeScene()
    _geometry = TriangleMesh(scene, v.astype("f"), f.astype("i"))
    origins = (v + 0.00065 * n).astype("f")
    maximum = 0.032
    occ = np.zeros(len(v))
    total = np.zeros(len(v))
    # Fibonacci directions distribute cosine-weighted samples on the hemisphere
    # without dependence on UVs or per-part topology.
    for i in range(60):
        t = (i + 0.5) / 60
        z = 1 - 2 * t
        theta = i * np.pi * (3 - np.sqrt(5))
        axis = np.array(
            [np.sqrt(1 - z * z) * np.cos(theta), z, np.sqrt(1 - z * z) * np.sin(theta)],
            dtype="f",
        )
        cos = np.maximum(0, n @ axis)
        mask = cos > 0.02
        rays = np.broadcast_to(axis, (int(mask.sum()), 3)).copy()
        nearest = scene.run(
            origins[mask],
            rays,
            dists=np.full(len(rays), maximum, "f"),
            query="DISTANCE",
        )
        occ[mask] += cos[mask] * np.square(1 - np.clip(nearest / maximum, 0, 1))
        total += cos * mask
    return (
        (1 + np.rint(254 * (1 - occ / np.maximum(1e-6, total))))
        .clip(1, 255)
        .astype("u1")
    )


def trunk_liner(skin_v, skin_f, muscle_v, muscle_f):
    """Continuous inset support behind separated muscles, fitted from the skin
    and the actual outermost muscular surface. Keeps daylight and the far-side
    vertebrae from showing through the narrow linea alba and between insertions.
    """
    from scipy.ndimage import gaussian_filter, median_filter

    levels = np.arange(0.816, 1.544, 0.008)
    steps = 96
    heights, angles = np.meshgrid(
        levels, np.arange(steps) * 2 * np.pi / steps, indexing="ij"
    )
    h = heights.ravel()
    origins = np.stack(
        [
            np.zeros_like(h),
            h,
            np.interp(
                h, [0.81, 1, 1.18, 1.4, 1.54], [0.006, 0.023, 0.027, 0.007, -0.011]
            ),
        ],
        1,
    ).astype("f")
    axes = np.stack(
        [np.cos(angles).ravel(), np.zeros_like(h), np.sin(angles).ravel()], 1
    ).astype("f")

    def scene(v, f):
        s = EmbreeScene()
        return s, TriangleMesh(s, v.astype("f"), f.astype("i"))

    skin_s, _skin_geometry = scene(skin_v, skin_f)
    radius = (
        skin_s.run(origins, axes, query="DISTANCE")
        .clip(0.016, 0.225)
        .reshape(heights.shape)
    )
    # Restrict the uppermost silhouette to the neck at the shoulder junction.
    width = np.interp(h, [1.38, 1.43, 1.46, 1.54], [0.19, 0.086, 0.055, 0.053]).reshape(
        heights.shape
    )
    radius = np.minimum(radius, width / np.maximum(0.01, np.abs(np.cos(angles))))
    muscular_s, _muscle_geometry = scene(muscle_v, muscle_f)
    distance = muscular_s.run(
        np.ascontiguousarray(origins + 0.42 * axes), -axes, query="DISTANCE"
    )
    external = (0.42 - distance).reshape(heights.shape)
    observed = (external > radius * 0.63) & (external < 0.23)
    _, nearest = distance_transform_edt(~observed, return_indices=True)
    tissue = external[tuple(nearest)]
    # The inset margin changes with the amount of superficial tissue.
    inset = np.interp(
        heights,
        [0.81, 0.90, 1.18, 1.39, 1.47, 1.54],
        [0.035, 0.032, 0.036, 0.029, 0.012, 0.01],
    )
    radius = np.minimum(radius - inset, tissue - 0.010)
    radius = gaussian_filter(
        median_filter(radius, (3, 5), mode="wrap"), (0.8, 1.3), mode=("nearest", "wrap")
    )
    pelvis_tip = np.clip((heights - 0.81) / 0.048, 0, 1)
    radius = np.maximum(0.007, radius) * pelvis_tip
    v = origins + axes * radius.ravel()[:, None]
    f = []
    for i in range(len(levels) - 1):
        for j in range(steps):
            a = i * steps + j
            b = i * steps + (j + 1) % steps
            f.extend([[a, a + steps, b], [b, a + steps, b + steps]])
    return v, np.array(f, dtype="i")
