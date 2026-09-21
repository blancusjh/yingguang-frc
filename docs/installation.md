# Installation

## Analysis

Python 3.11+ is required. From the repository root:

```bash
python -m venv .venv-analysis
source .venv-analysis/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

This installs NumPy, SciPy, h5py, and Matplotlib. No WarpX, CUDA, or display is
needed to analyze the sample or reproduce the compactness plots.

For the direct dependency versions used during the repository reorganization
(Python 3.14), install with `-c requirements-analysis.txt`.
These constraints are a record of the tested environment, not a complete
cross-platform lock file.

Optional interactive/3D rendering:

```bash
python -m pip install -e '.[render]'
```

Rendering requires a working VTK/OpenGL backend. Headless availability depends
on the machine; numerical analysis does not require it.

## Simulation

The completed corrected-mirror case used upstream WarpX 26.07, revision
`312d507407a1bf6f01ae43fb41b5c3a3700d053c`, with RZ, CUDA, openPMD/HDF5,
and MPI disabled. The original workstation used an RTX 4060 (compute
capability 8.9), Python 3.14, and GCC 15.

Obtain that WarpX revision in a separate source checkout. The build script
expects `../vendor/warpx` by default; set `WARPX_SRC` for another location.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
bash scripts/build_warpx.sh
```

The script verifies the WarpX revision and clean source checkout before
building. The CUDA toolkit and supported host compiler must already be
installed. Override machine-specific settings as needed:

```bash
CUDA_HOME=/path/to/cuda CUDAARCHS=89 CC=gcc-15 CXX=g++-15 \
CUDAHOSTCXX=g++-15 BUILD_PARALLEL=8 WARPX_SRC=/path/to/warpx \
bash scripts/build_warpx.sh
```

`VENV` can select another existing environment. The default values reproduce
the original workstation setup; compiler/toolkit compatibility must match
your installation.

Use the simulation environment's `frc-run` command. An analysis environment
cannot launch WarpX merely because another environment has it installed.
The launcher writes WarpX's build/runtime information to `run.log`.
