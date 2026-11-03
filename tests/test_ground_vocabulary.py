"""Ground movements need usable FK and explicit, portable contacts for planted demonstrations."""

import copy
import unittest
from math import dist

from eml import Program, load
from eml.data import ROOT


def guide():
    return [
        row
        for row in load(ROOT / "docs/upper-motion-setups.json")["setups"]
        if "support" in row
    ]


def personal(row, **fields):
    return {
        "eml": "1.1",
        "id": "personal-ground-sequence",
        "title": "My ground sequence",
        "start": {"pose": row["pose"]},
        "muscles": {"primary": [], "secondary": []},
        "repeat": {"mode": "loop", "count": 1},
        **fields,
    }


class GroundVocabulary(unittest.TestCase):
    def test_each_ground_motion_works_as_a_single_action_from_its_advertised_pose(self):
        self.assertEqual(
            {r["pose"] for r in guide()},
            {
                "high-plank",
                "upper-kneeling-plank",
                "upper-inclined-plank",
                "quadruped",
                "lower-bear",
            },
        )
        for row in guide():
            for motion in row["motions"]:
                with self.subTest(pose=row["pose"], motion=motion):
                    d = personal(
                        row,
                        phases=[
                            {"id": "move", "seconds": 1, "actions": [{"use": motion}]},
                            {"id": "recover", "seconds": 1, "actions": []},
                        ],
                    )
                    p = Program(d)
                    base = p.sample(0)
                    frames = [p.segment(0, i / 64) for i in range(65)]
                    self.assertFalse(
                        [issue for f in frames for issue in f["diagnostics"]]
                    )
                    if "push" in motion:
                        feet = (
                            []
                            if row["pose"] == "upper-kneeling-plank"
                            else ["leftBall", "rightBall"]
                        )
                        complete = frames + [p.segment(1, j / 32) for j in range(33)]
                        for name in ["leftPalm", "rightPalm", *feet]:
                            for frame in complete:
                                self.assertLess(
                                    dist(
                                        frame["landmarks"][name],
                                        base["landmarks"][name],
                                    ),
                                    0.002,
                                )
                    end = frames[-1]
                    if row["pose"] == "quadruped":
                        side = "left" if "-left" in motion else "right"
                        planted = "right" if side == "left" else "left"
                        self.assertGreater(
                            end["landmarks"][side + "Palm"][2]
                            - base["landmarks"][side + "Palm"][2],
                            0.20,
                        )
                        self.assertLess(
                            dist(
                                end["landmarks"][planted + "Palm"],
                                base["landmarks"][planted + "Palm"],
                            ),
                            0.001,
                        )
                    elif row["pose"] == "lower-bear":
                        active = "left" if motion.endswith("left") else "right"
                        hand = "right" if active == "left" else "left"
                        for name in (active + "Ball", hand + "Palm"):
                            self.assertGreater(
                                end["landmarks"][name][1] - base["landmarks"][name][1],
                                0.045,
                            )
                    else:
                        self.assertGreater(
                            base["positions"]["pelvis"][1]
                            - end["positions"]["pelvis"][1],
                            0.04,
                        )
                        self.assertLess(
                            dist(
                                end["landmarks"]["leftPalm"],
                                base["landmarks"]["leftPalm"],
                            ),
                            0.008,
                        )
                    self.assertLess(
                        dist(
                            p.sample(p.duration)["positions"]["leftHand"],
                            base["positions"]["leftHand"],
                        ),
                        0.0001,
                    )

    def test_copying_the_ground_template_keeps_each_named_contact_during_its_phase(
        self,
    ):
        for row in guide():
            with self.subTest(pose=row["pose"]):
                p = Program(personal(row, **copy.deepcopy(row["support"])))
                clip = p.compile(15)
                self.assertTrue(clip["frames"])
                for i, phase in enumerate(p.doc["phases"]):
                    contacts = p.effective_contacts(phase)
                    self.assertTrue(contacts)
                    for j in range(17):
                        f = p.segment(i, j / 16)
                        for claim in contacts:
                            effector, target = claim["effector"], claim["target"]
                            expected = (
                                p.anchors[effector]
                                if target == "start"
                                else f["equipment"][target["item"]]["sockets"][
                                    target["socket"]
                                ]
                            )
                            self.assertLess(
                                dist(f["landmarks"][effector], expected), 0.002
                            )

    def test_incline_pads_leave_space_for_the_lowered_chest(self):
        row = next(r for r in guide() if r["pose"] == "upper-inclined-plank")
        p = Program(personal(row, **copy.deepcopy(row["support"])))
        pads = p.kit[p.items["platform"]["kind"]]["visual"][:2]
        self.assertGreater(pads[0]["position"][0] - pads[0]["dimensions"][0] / 2, 0.13)
        self.assertLess(pads[1]["position"][0] + pads[1]["dimensions"][0] / 2, -0.13)
        targets = {c["landmark"]: c["surface"]["part"] for c in p.doc["constraints"]}
        self.assertEqual(targets, {"leftPalm": 0, "rightPalm": 1})

    def test_lowering_the_incline_surface_fails_if_the_hand_targets_stay_put(self):
        row = next(r for r in guide() if r["pose"] == "upper-inclined-plank")
        d = personal(row, **copy.deepcopy(row["support"]))
        # A bad attachment that places the palms above the actual pad must fail the surface test.
        for c in d["contacts"]:
            if c["effector"].endswith("Palm"):
                c["target"] = "start"
        d["equipment"][0]["position"][1] -= 0.20
        self.assertEqual(
            {
                d["effector"]
                for d in Program(d).sample(0.5)["diagnostics"]
                if d["reason"] == "support-gap"
            },
            {"leftPalm", "rightPalm"},
        )
