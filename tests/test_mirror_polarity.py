"""Invariante del montaje de Sun 2013 §2.3, independiente del PIC."""
import sys
import unittest
from pathlib import Path

import numpy as np

from yingguang_frc.model import parameters as P


class MirrorPolarityTests(unittest.TestCase):
    def test_mirrors_oppose_bias_and_align_with_main_pulse(self):
        self.assertGreater(P.B_BIAS, 0)
        self.assertLess(P.B_MIRROR_0, 0)
        self.assertLess(float(P.drive_waveform(P.T_QUARTER)), 0)
        for z in [-P.Z_MIRROR, P.Z_MIRROR]:
            self.assertLess(float(P.mirror_field(0., z)[1]), 0)

    def test_initial_axial_nulls_between_core_and_mirrors(self):
        # El artículo describe explícitamente un nulo axial en cada extremo
        # durante el bias. La polaridad histórica +0.9 no produce ninguno.
        z = np.linspace(-P.Z_MIRROR, P.Z_MIRROR, 2001)
        br, bz = P.initial_field(np.zeros_like(z), z)
        crossings = np.flatnonzero(np.diff(np.sign(bz)))
        self.assertEqual(len(crossings), 2)
        self.assertGreater(bz[len(z)//2], 0)
        self.assertLess(bz[0], 0)
        self.assertLess(bz[-1], 0)
        np.testing.assert_allclose(bz, bz[::-1], atol=1e-12)
        np.testing.assert_allclose(br, 0., atol=1e-12)


if __name__ == '__main__':
    unittest.main()
