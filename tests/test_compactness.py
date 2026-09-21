"""Validación geométrica independiente de las métricas de concentración."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import h5py
import numpy as np

from yingguang_frc.analysis.compactness import QE, analyze, measure, read_frames


class CompactnessTests(unittest.TestCase):
    def test_truncated_series_cannot_be_called_initial_inventory(self):
        frame = (1e-6, np.ones((2, 4)), np.linspace(0, .05, 3),
                 np.linspace(-.5, .5, 5))
        with patch('yingguang_frc.analysis.compactness.read_frames', return_value=iter([frame])):
            with self.assertRaisesRegex(ValueError, 't=0'):
                analyze('unused')

    def test_uniform_cylinder_with_partial_axial_cells(self):
        r = np.linspace(0, .05, 11)
        z = np.linspace(-.5, .5, 201)
        n = np.full((10, 200), 3e21)
        m, line = measure(n, r, z, coil_half=.183, center_half=.061)
        total = 3e21 * np.pi * .05**2
        self.assertAlmostEqual(m['N'] / total, 1)
        self.assertAlmostEqual(m['N_center'] / total, .122)
        self.assertAlmostEqual(m['N_coil'] / total, .366)
        self.assertAlmostEqual(m['L80_cm'], .366 * .8 * 100)
        self.assertAlmostEqual(m['R80_cm'], np.sqrt(.8) * 5)
        np.testing.assert_allclose(line, total)

    def test_empty_plasma_has_no_finite_size(self):
        m, _ = measure(np.zeros((2, 4)), np.linspace(0, .05, 3),
                       np.linspace(-.5, .5, 5))
        self.assertEqual(m['N'], 0)
        self.assertTrue(np.isnan(m['L80_cm']))
        self.assertTrue(np.isnan(m['R80_cm']))

    def test_openpmd_units_offsets_and_mode_guard(self):
        with tempfile.TemporaryDirectory() as td:
            fields = Path(td) / 'diags/fields'
            fields.mkdir(parents=True)
            path = fields / 'openpmd_000000.h5'
            with h5py.File(path, 'w') as h:
                g = h.create_group('data/0')
                g.attrs.update(time=2., timeUnitSI=1e-6)
                d = g.create_dataset('fields/rho', data=np.ones((1, 4, 2)))
                d.attrs.update(axisLabels=np.array(['z', 'r'], dtype='S'),
                               gridSpacing=[2., 1.], gridGlobalOffset=[-4., 0.],
                               gridUnitSI=.01, position=[.5, .5], unitSI=2*QE)
            t, n, r, z = next(read_frames(td))
            self.assertEqual(t, 2e-6)
            np.testing.assert_allclose(n, 2)
            np.testing.assert_allclose(r, [0, .01, .02])
            np.testing.assert_allclose(z, [-.04, -.02, 0, .02, .04])
            with h5py.File(path, 'a') as h:
                g = h['data/0/fields']
                attrs = dict(g['rho'].attrs)
                del g['rho']
                d = g.create_dataset('rho', data=np.ones((3, 4, 2)))
                d.attrs.update(attrs)
            with self.assertRaises(ValueError):
                next(read_frames(td))


if __name__ == '__main__':
    unittest.main()
