import unittest
from eml import Program, load
from eml.data import ROOT
from tools.audit_apparatus import measure, segment_box


class ApparatusTests(unittest.TestCase):
    def test_finite_edges_and_very_thin_crossing(self):
        self.assertEqual(segment_box((-17, 0, 0), (13, 0, 0), (0.01, 1, 1)), 0)
        self.assertAlmostEqual(segment_box((-2, 2, 0), (2, 2, 0), (1, 1, 1)), 1)
        self.assertAlmostEqual(segment_box((2, 2, 2), (2, 2, 2), (1, 1, 1)), 3**0.5)

    def test_machine_pivots_cable_and_carriage_clear_the_torso(self):
        for name in ("pec-deck", "seated-cable-row", "hack-squat"):
            p = Program(load(ROOT / "exercises" / (name + ".json")))
            for i in range(len(p.doc["phases"])):
                for j in range(17):
                    f = p.segment(i, j / 16)
                    for part, gap in measure(p, f):
                        self.assertGreaterEqual(
                            gap, -0.012, (name, f["phase"], part, gap)
                        )
