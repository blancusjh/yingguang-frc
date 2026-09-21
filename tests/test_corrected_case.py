"""Regress scientific measurements against actual corrected-case snapshots."""
from pathlib import Path
import unittest

import numpy as np

from yingguang_frc.analysis.compactness import analyze
from yingguang_frc.analysis.openpmd import load_series

ROOT = Path(__file__).resolve().parents[1]


class CorrectedCaseTests(unittest.TestCase):
    def test_sample_matches_complete_corrected_case_table(self):
        ref = np.genfromtxt(ROOT / "results/corrected-mirrors/compactness.csv",
                            delimiter=",", names=True)
        rows, _ = analyze(ROOT / "results/corrected-mirrors/sample")
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["t_us"], 0.)
        for row in rows:
            i = int(np.argmin(np.abs(ref["t_us"] - row["t_us"])))
            for key in ref.dtype.names:
                np.testing.assert_allclose(row[key], ref[key][i], rtol=1e-12, atol=1e-12,
                                           err_msg=f"{key} at {row['t_us']} us")

    def test_vector_fields_share_metadata_coordinates(self):
        frames = load_series(ROOT / "results/corrected-mirrors/sample")
        for f in frames:
            self.assertEqual(f["rho"].shape, (48, 176))
            self.assertEqual(f["Bt"].shape, f["Bz"].shape)
            self.assertAlmostEqual(f["r"][0], .0525/48/2)
            self.assertAlmostEqual(f["z"][0], -.5 + 1/176/2)
            self.assertAlmostEqual(f["r_edges"][-1], .0525)


if __name__ == "__main__":
    unittest.main()
