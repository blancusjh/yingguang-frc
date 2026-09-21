# Configurations

| File | Status | Grid | Ions/cell | dt factor |
|---|---|---|---:|---:|
| [corrected-mirrors.toml](corrected-mirrors.toml) | Completed corrected-mirror case | 48 × 176 | 20 | 0.04 |
| [corrected-mirrors-high-resolution.toml](corrected-mirrors-high-resolution.toml) | Launched locally; no completed result published | 96 × 352 | 60 | 0.01 |

Both files specify every configurable model parameter and execution option.
There is no implicit inheritance. Values use SI units except initial
temperatures (eV), crowbar time (µs), and diagnostic interval (ns), explicitly
marked in the files.

The higher-resolution repeat changes only grid resolution, particle count,
time-step factor, and diagnostic cadence. It is a repeat of the same physical
configuration, not evidence of convergence.

To explore, copy a configuration, edit it, and choose a new output directory.
The loader rejects missing/unknown keys, nonfinite values, invalid dimensions,
and mirrors aligned with the positive bias.
The corrected-mirror case's early crowbar and prescribed resistivity are
modeling choices, not claims about the exact experimental discharge.

`render/presentation.json` is a visualization preset, not a simulation
configuration. It uses fixed physical scales and a presentation camera,
transparent device, and density transfer function. See the
[viewer guide](../docs/visualization.md) for tuning and export commands.
