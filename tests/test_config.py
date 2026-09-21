"""Configuration validation and safe provenance capture, without WarpX."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from yingguang_frc.config import apply, load
from yingguang_frc.model import parameters as P
from yingguang_frc.run import digest, prepare

ROOT = Path(__file__).resolve().parents[1]
CORRECTED_CASE = ROOT / "configs/corrected-mirrors.toml"


class ConfigurationTests(unittest.TestCase):
    def tearDown(self):
        apply(load(CORRECTED_CASE))

    def test_corrected_case_matches_recorded_launch(self):
        cfg = load(CORRECTED_CASE)
        resolved = apply(cfg)
        self.assertEqual((P.NR, P.NZ, P.NPPC), (48, 176, 20))
        self.assertEqual(resolved["B_MIRROR_0"], -.9)
        self.assertEqual(resolved["ETA0"], 1.47e-6)
        self.assertEqual(P.plasma_quantities()["n_steps"], 36399)
        self.assertAlmostEqual(P.plasma_quantities()["dt"], 2.1978284031269795e-10)

    def test_refinement_changes_only_numerics(self):
        base, refined = load(CORRECTED_CASE), load(ROOT / "configs/corrected-mirrors-high-resolution.toml")
        changed = {k for k in base["parameters"]
                   if base["parameters"][k] != refined["parameters"][k]}
        self.assertEqual(changed, {"NR", "NZ", "NPPC", "DT_FACTOR"})
        self.assertEqual({k for k in base["execution"]
                          if base["execution"][k] != refined["execution"][k]}, {"diag_ns"})

    def test_misspellings_missing_values_and_wrong_sign_fail(self):
        text = CORRECTED_CASE.read_text()
        variants = [text.replace("B_MIRROR_0", "B_MIRROR_O"),
                    text.replace("B_MIRROR_0 = -0.9", "B_MIRROR_0 = 0.9"),
                    text.replace("NR = 48", "NR = 0"),
                    text.replace("NR = 48", "NR = 48.5"),
                    text.replace("DT_FACTOR = 0.04", "DT_FACTOR = nan")]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"
            for variant in variants:
                p.write_text(variant)
                with self.assertRaises(ValueError):
                    load(p)

    def test_initial_field_symmetry_and_crowbar_continuity(self):
        cfg = load(CORRECTED_CASE)
        apply(cfg)
        t = cfg["execution"]["t_crowbar"] * 1e-6
        values = P.drive_waveform(np.array([t - 1e-14, t, t + 1e-14]))
        np.testing.assert_allclose(values, values[1], rtol=1e-7)
        z = np.linspace(0, .4, 25)
        positive = P.initial_field(np.full_like(z, .02), z)
        negative = P.initial_field(np.full_like(z, .02), -z)
        np.testing.assert_allclose(positive[0], -negative[0], atol=1e-12)
        np.testing.assert_allclose(positive[1], negative[1], atol=1e-12)

    def test_prepare_snapshots_source_and_protects_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            output, manifest = prepare(CORRECTED_CASE, Path(td) / "new-run", steps=2)
            self.assertEqual(manifest["status"], "prepared")
            self.assertEqual(manifest["requested_steps"], 2)
            self.assertTrue(manifest["short_run"])
            self.assertEqual(manifest["resolved_parameters"]["B_MIRROR_0"], -.9)
            self.assertEqual(manifest["config_sha256"], digest(output / "config.toml"))
            for name, checksum in manifest["source_sha256"].items():
                self.assertEqual(digest(output / name), checksum)
            saved = json.loads((output / "manifest.json").read_text())
            with self.assertRaises(FileExistsError):
                prepare(CORRECTED_CASE, output)
            self.assertEqual(saved, json.loads((output / "manifest.json").read_text()))


if __name__ == "__main__":
    unittest.main()
