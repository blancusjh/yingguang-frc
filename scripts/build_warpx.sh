#!/bin/bash
# Compila pywarpx RZ + CUDA y lo instala en el .venv del proyecto (~30 min).
#
# Fuente: WarpX upstream 26.07 (tag 312d5074), sin parches locales. Se espera
# en ../vendor/warpx; con WARPX_SRC se puede apuntar a otro sitio.
#
# Ajustado a una RTX 4060 (CC 8.9). Para otra GPU, cambiar CUDAARCHS.
# El host compiler es gcc-15 porque nvcc aun no admite gcc-16.
set -e

PROJ=$(cd "$(dirname "$0")/.." && pwd)
WARPX_SRC=${WARPX_SRC:-$PROJ/../vendor/warpx}
VENV=${VENV:-$PROJ/.venv}

[ -d "$WARPX_SRC" ] || { echo "No encuentro el fuente de WarpX en $WARPX_SRC"; exit 1; }
[ -x "$VENV/bin/pip" ] || { echo "No encuentro el venv en $VENV"; exit 1; }

EXPECTED_REV=312d507407a1bf6f01ae43fb41b5c3a3700d053c
ACTUAL_REV=$(git -C "$WARPX_SRC" rev-parse HEAD)
[ "$ACTUAL_REV" = "$EXPECTED_REV" ] || {
  echo "Expected WarpX $EXPECTED_REV; found $ACTUAL_REV"; exit 1;
}
[ -z "$(git -C "$WARPX_SRC" status --porcelain)" ] || {
  echo "WarpX source has local changes; use a clean checkout of $EXPECTED_REV"; exit 1;
}
export CUDA_HOME=${CUDA_HOME:-/opt/cuda}
export PATH="$CUDA_HOME/bin:$PATH"
export CUDAARCHS=${CUDAARCHS:-89}
export CUDAHOSTCXX=${CUDAHOSTCXX:-g++-15}
export CC=${CC:-gcc-15} CXX=${CXX:-g++-15}
export WARPX_DIMS=RZ
export WARPX_COMPUTE=CUDA
export WARPX_MPI=OFF
export WARPX_OPENPMD=ON
export BUILD_PARALLEL=${BUILD_PARALLEL:-14}

echo "Compilando $WARPX_SRC -> $VENV"
cd "$WARPX_SRC"
"$VENV/bin/pip" install -v .
