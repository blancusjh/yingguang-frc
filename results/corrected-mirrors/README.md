# Corrected-mirror result

This is the repository's only published simulation result.
The original run completed on 7 September 2026 with 48 × 176 cells and
20 macroparticles per cell. Its final output is at 7.9998756 µs.

[Configuration](../../configs/corrected-mirrors.toml) ·
[Model](../../docs/model.md) ·
[Reproduction commands](../../docs/reproduction.md)

![Compactness](compactness.png)
![Density at selected times](density.png)

| Final measurement | Value |
|---|---:|
| Retained inventory / initial | 0.8588148348 |
| Central inventory / initial | 0.5194397174 |
| Central inventory / remaining | 0.6048331915 |
| L80 inside coil | 14.05747173 cm |
| R80 inside coil | 2.178144525 cm |

Extra digits are retained for software regression, not physical precision.
See the [diagnostic definitions](../../docs/diagnostics.md) for integration
windows, normalization, and limitations.

## Contents

- `compactness.csv`: all 42 output times and measured quantities.
- `compactness.png`: retention and inventory dimensions from that table.
- `density.png`: density near 4 and 8 µs on a shared absolute scale.
- `device.png`: configured geometry, initial field, and drive.
- [evolution.mp4](evolution.mp4): 1920 × 800, 24 fps visualization of the corrected
  case, with display-only temporal interpolation between diagnostic outputs.
- [render.png](render.png): high-quality final-time render with a metadata sidecar.
- [viewer.png](viewer.png): interactive viewer and tuning controls.
- `sample/diags/fields/`: four unmodified original openPMD field snapshots
  at t = 0 and near 2, 4, and 8 µs; about 3.7 MB in total.
- `provenance/`: original launch record, WarpX inputs, file checksums,
  and what is known about the original execution.

The raw complete simulation is local under ignored `runs/corrected-mirrors/`.
It is not included in a fresh checkout. Recompute it with the corrected-mirror
configuration to obtain the complete fields and particle outputs.

The sample reproduces its four table rows. Recreating the full CSV requires
the complete output series. The CSV alone suffices to regenerate the overview.

## Status

This is a coarse-grid numerical result, not a validated experimental
reproduction or a demonstrated converged equilibrium.
The [higher-resolution configuration](../../configs/corrected-mirrors-high-resolution.toml)
was launched locally on 21 September 2026; no completed higher-resolution
result is attached here.
