# Provenance of the completed corrected-mirror case

The original run was named `runs/compactness/correct-mirrors`.
Its complete local output was moved to `runs/corrected-mirrors` during repository
organization; field data were not modified.

`original-launch.txt` is an execution record, not a runnable entry point:
its relative paths describe the former repository layout.
Use `frc-run --config configs/corrected-mirrors.toml --output runs/new-name` now.

`warpx_used_inputs` is the original WarpX dump. It records parser inputs
but does not capture the Python callback that loads the mirror field.
The signed mirror setting is documented by the launch command, model,
and output fields.

The corrected-mirror TOML was reconstructed from that command and the available
model. The earlier execution did not save a complete source/environment
manifest, so an exact original source revision cannot be established.
No source hash recorded during the reorganization is presented as a hash
recorded at simulation time.

The available WarpX checkout is upstream 26.07 at revision
`312d507407a1bf6f01ae43fb41b5c3a3700d053c`, without local patches.
The original runtime was pywarpx 26.7 with RZ/CUDA and openPMD/HDF5.
The seed option was omitted, corresponding to WarpX's default.

`data-manifest.json` records the sample hashes, complete raw field inventory,
configuration hash, and regenerated figure/table hashes. All 42 rows were
recomputed and matched the original compactness table to a relative tolerance
of 10⁻¹². That is a software consistency check, not an uncertainty estimate.

The committed movie was regenerated from the complete corrected case using
the reorganized source and metadata-based reader. Its command, settings,
and checksum are in `render.json`. The movie samples every second output,
ending at 7.991304 µs; the table and bundled final snapshot extend to
7.999876 µs. Display settings use fixed n_max = 5 × 10²² m⁻³,
B_max = 2.2 T, the common camera, and density smoothing.

New runs use the launcher, which snapshots the source it actually executes
and records their configuration, environment, status, and checksums.
