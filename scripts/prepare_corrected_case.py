"""Verify the corrected-mirror case and export portable result assets."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import h5py
import numpy as np

from yingguang_frc.analysis.compactness import analyze
from yingguang_frc.run import digest
from yingguang_frc.visualization.report import plot_table

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    expected = np.genfromtxt(ROOT / "results/corrected-mirrors/compactness.csv",
                             delimiter=",", names=True)
    rows, _ = analyze(args.run)
    if len(rows) != len(expected):
        raise ValueError("The complete corrected-mirror time series is required")
    for key in expected.dtype.names:
        np.testing.assert_allclose([row[key] for row in rows], expected[key],
                                   rtol=1e-12, atol=1e-12, err_msg=key)
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.out / "compactness.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    plot_table(args.out / "compactness.csv", args.out / "compactness.png")
    subprocess.run([sys.executable, "-m", "yingguang_frc.visualization.design",
                    "--config", str(ROOT / "configs/corrected-mirrors.toml"),
                    "--out", str(args.out / "device.png")], check=True)
    with tempfile.TemporaryDirectory(prefix="frc-corrected-") as td:
        subprocess.run([sys.executable, "-m", "yingguang_frc.analysis.compactness",
                        str(args.run), "--labels", "Corrected-mirrors", "--out", td], check=True)
        shutil.copyfile(Path(td) / "density_slices.png", args.out / "density.png")
    files = sorted((args.run / "diags/fields").glob("*.h5"))
    times = []
    for path in files:
        with h5py.File(path) as h:
            g = next(iter(h["data"].values()))
            times.append(float(g.attrs["time"] * g.attrs.get("timeUnitSI", 1.)))
    selected = []
    for target in (0., 2e-6, 4e-6, 8e-6):
        i = int(np.argmin(np.abs(np.asarray(times) - target)))
        source = files[i]
        dest = args.out / "sample/diags/fields" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        selected.append({"path": str(dest.relative_to(args.out)), "time_s": times[i],
                         "sha256": digest(dest), "bytes": dest.stat().st_size})
    manifest = {
        "analysis_source_sha256": {
            str(f.relative_to(ROOT)): digest(f)
            for f in sorted((ROOT / "src/yingguang_frc").rglob("*.py"))},
        "recipe_sha256": digest(Path(__file__)),
        "configuration": "configs/corrected-mirrors.toml",
        "config_sha256": digest(ROOT / "configs/corrected-mirrors.toml"),
        "full_series_frames": len(rows), "sample_frames": selected,
        "sample_scope": "Selected original field snapshots; no particle data.",
        "full_run_field_files": [
            {"path": str(f.relative_to(args.run)), "sha256": digest(f)} for f in files],
        "artifacts": {name: digest(args.out / name) for name in
                      ("compactness.csv", "compactness.png", "density.png", "device.png")},
        "measurement_definition": {"coil_half_m": .18, "center_half_m": .06,
                                   "inventory": "cell-centered annular volumes"},
    }
    (args.out / "data-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified {len(rows)} frames; exported {len(selected)} samples to {args.out}")


if __name__ == "__main__":
    main()
