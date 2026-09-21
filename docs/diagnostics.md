# Diagnostic definitions

## Corrected-mirror compactness measurements

The corrected-mirror table is produced by `analysis.compactness`. It reads the
coordinates, offsets, component positions, and SI units from openPMD.
Only cell-centered RZ m = 0 data with axes (z,r) are supported; unsupported
layouts raise an error.

For each cell, ion inventory is density times the exact annular volume:

`N_cell = max(n_i, 0) π(r_outer² − r_inner²) Δz`.

Axial windows use the fractional overlap of boundary cells. The reported
values are grid estimates; charge filtering and deposition mean they need
not equal a direct count of particle weights. They are not subpercent
confinement measurements.

| CSV field | Meaning |
|---|---|
| `t_us` | Actual output time in microseconds |
| `N` | Ions estimated in the full domain |
| `N_coil` | Ions within \|z\| < 18 cm |
| `N_center` | Ions within \|z\| < 6 cm |
| `retained` | N(t) / N(0) |
| `center_initial` | N_center(t) / N(0) |
| `center_fraction` | N_center(t) / N(t) |
| `L80_cm` | Distance between axial 10% and 90% inventory quantiles inside the coil |
| `R80_cm` | Radius enclosing 80% of the inventory inside the coil |

The central 12 cm is an explicit diagnostic choice.
L80 and R80 are inventory dimensions, not the magnetic separatrix.
Normalization requires an actual t = 0 snapshot; the bundled sample includes
it. Empty plasma has undefined (NaN) quantile sizes.

## Additional exploratory tools

`analysis.diagnostics` estimates excluded-flux radius, line density,
magnetic probes, and particle temperature when particle output is present.
`analysis.flux` integrates poloidal flux and counts smoothed axial maxima.
`analysis.confinement` estimates inventory by spatial zones.

These are exploratory diagnostics, not the source of the corrected-mirror compactness
table. Their geometric approximations, smoothing thresholds, and topology
interpretations need further validation. In particular, an axial maximum
count is not a general magnetic-island finder, and a Bz = 0 contour is not
the separatrix.

All field readers now obtain coordinates from output metadata. Device-specific
analysis windows and visualization geometry correspond to the corrected-mirror
device; adapt them explicitly when studying another geometry.

## Figures

The overview plots the complete CSV without spatial filtering.
Density slices use one absolute density scale across displayed times.
The optional 3D renderer includes Bθ and supports fixed density and magnetic
color limits. Its smoothing and opacity are presentation settings, not
definitions of retained or centrally concentrated plasma.
