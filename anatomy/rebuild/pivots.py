"""Mark weighted forearm/hand vertices in the existing 40-byte atlas format."""

import struct

WRIST_PIVOTS = ["leftHand", "rightHand"]


def mark_wrist_blends(vertices, joints):
    data = bytearray(vertices)
    names = [joint["name"] for joint in joints]
    pairs = [
        (joints[names.index(name)]["parent"], names.index(name))
        for name in WRIST_PIVOTS
    ]
    for offset in range(0, len(data), 40):
        indices = data[offset + 24 : offset + 28]
        weights = data[offset + 28 : offset + 32]
        marker = data[offset + 36]  # Keep baked ambient visibility in the low byte.
        for pair, (forearm, hand) in enumerate(pairs, 1):
            a = sum(w for j, w in zip(indices, weights) if j == forearm)
            b = sum(w for j, w in zip(indices, weights) if j == hand)
            if a and b:
                marker |= (pair << 8) | (a << 16) | (b << 24)
                break
        struct.pack_into("<I", data, offset + 36, marker)
    return data
