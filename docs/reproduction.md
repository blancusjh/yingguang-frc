# Reproducing the corrected-mirror case

All commands below run from the repository root after installation.

## Included data

`results/corrected-mirrors/compactness.csv` contains the complete measured time series.
`results/corrected-mirrors/sample/` contains four original field outputs, including
the initial and final snapshots. No particle data are bundled.

```bash
frc-report results/corrected-mirrors/compactness.csv --out results/local/overview.png
frc-compactness results/corrected-mirrors/sample --labels Corrected-mirrors --out results/local/sample
python -m yingguang_frc.visualization.design \
  --config configs/corrected-mirrors.toml --out results/local/device.png
```

The sample reproduces the selected-time measurements, not intermediate
evolution. The regression test compares every bundled sample time against
the complete corrected-mirror table.

## A new simulation

With the WarpX environment activated:

```bash
# Inspect the entire configuration and derived step count without writing.
frc-run --config configs/corrected-mirrors.toml --output runs/repeat --dry-run

# Short installation check in its own directory.
frc-run --config configs/corrected-mirrors.toml --output runs/smoke --steps 2

# Complete 8 µs corrected-mirror case.
frc-run --config configs/corrected-mirrors.toml --output runs/repeat
```

Each output directory must be new. Standard output from the worker is in
`run.log`; `manifest.json` records running/completed/failed/interrupted status.
A completed short run is marked `short_run: true` and is not a completed
8 µs case. The original completed local data are in `runs/corrected-mirrors`.

The launcher copies and executes its own Python source snapshot. It saves
the input TOML, resolved parameters, source hashes, revision/worktree status,
Python/dependency versions, random-seed setting, and output sizes/checksums.
The log includes WarpX's runtime/build information. A source snapshot is
essential because fields are partly defined by Python callbacks.

Fixed seed settings do not guarantee bitwise-identical GPU runs. Compare
physical measurements with appropriate tolerances.

## Analyze a complete run

```bash
frc-compactness runs/repeat --labels Corrected-mirrors --out results/local/repeat
frc-report results/local/repeat/00_repeat.csv --out results/local/repeat/overview.png
```

To prepare the curated assets from the original completed data:

```bash
python scripts/prepare_corrected_case.py --run runs/corrected-mirrors --out results/local/prepared
```

This verifies the complete recomputed compactness table against the published
table before exporting selected snapshots, figures, and a data manifest.

## Higher-resolution repeat

```bash
frc-run --config configs/corrected-mirrors-high-resolution.toml --output runs/refined --dry-run
frc-run --config configs/corrected-mirrors-high-resolution.toml --output runs/refined
```

This changes resolution from 48 × 176 to 96 × 352, particles per cell from
20 to 60, time-step factor from 0.04 to 0.01, and field diagnostic cadence
from 200 to 100 ns. The physical configuration is unchanged. This run was
launched locally on 21 September 2026 in `runs/refined`; inspect its manifest
for the current status. Do not relaunch into that existing directory.
It is not yet a published result or a complete convergence study.

## Optional 3D rendering

Install the `render` extra and use a working OpenGL backend:

```bash
frc-render runs/corrected-mirrors --settings configs/render/presentation.json \
  --out results/local/evolution.mp4 --duration 8 --fps 24 --size 1920 800
frc-view runs/corrected-mirrors --settings configs/render/presentation.json --quality interactive
```

The [visualization guide](visualization.md) explains tuning, camera presets,
settings files, and the distinction between rendering and simulation
resolution. Rendering uses cell coordinates from metadata; VTK/OpenGL
differences between machines can change the pixels. Movie settings and
checksums are recorded alongside the published result.
