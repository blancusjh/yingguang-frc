"""Exploratory inventory estimates by device region.

For the published annular-volume measurements use analysis.compactness.
Run with: python -m yingguang_frc.analysis.confinement RUN --out figure.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from yingguang_frc.model import parameters as P
from yingguang_frc.analysis.openpmd import load_series

R_WALL_FRAC = 0.85      # "cerca de la pared" = r > 0.85 * R_tubo


def inventario(run_dir):
    """Series de inventario de un run.

    Devuelve dict con t (us), N/N0 total, la fraccion en cada zona axial
    (referida a N0) y la fraccion del plasma que esta cerca de la pared.
    """
    frames = load_series(run_dir)
    nr, nz = frames[0]["rho"].shape
    r = frames[0]["r"]
    z = frames[0]["z"]
    zc = np.abs(z)
    coil, mirror = P.L_COIL / 2, P.Z_MIRROR
    r_wall = R_WALL_FRAC * P.LR

    t, tot, en_bobina, entre, fuera, pared = [], [], [], [], [], []
    N0 = None
    for f in frames:
        n = f["rho"] / P.QE
        # dN/dz, integrando 2*pi*r*n dr
        lin = np.trapezoid(n * 2 * np.pi * r[:, None], r, axis=0)
        N = np.trapezoid(lin, z)
        if N0 is None:
            N0 = N if N > 0 else 1.0
        t.append(f["t"] * 1e6)
        tot.append(N / N0)
        en_bobina.append(np.trapezoid(np.where(zc < coil, lin, 0.0), z) / N0)
        entre.append(np.trapezoid(
            np.where((zc >= coil) & (zc < mirror), lin, 0.0), z) / N0)
        fuera.append(np.trapezoid(np.where(zc >= mirror, lin, 0.0), z) / N0)
        # perfil radial (integrado en z) -> cuanto vive pegado a la pared
        nrad = np.trapezoid(n * 2 * np.pi * r[:, None], z, axis=1)
        denom = max(np.trapezoid(nrad, r), 1e-30)
        pared.append(np.trapezoid(np.where(r > r_wall, nrad, 0.0), r) / denom)

    return dict(t=np.asarray(t), tot=np.asarray(tot),
                bobina=np.asarray(en_bobina), entre=np.asarray(entre),
                fuera=np.asarray(fuera), pared=np.asarray(pared))


def vida_1e(t, tot):
    """Instante en que el inventario cae a 1/e. NaN si no llega."""
    k = np.where(tot < 1 / np.e)[0]
    return t[k[0]] if len(k) else np.nan


def resumen(nombre, s):
    print(f"\n{nombre}")
    print("   t(us)   N/N0    bobina  entre  fuera   pared")
    for tt in (0.0, 0.2, 0.5, 1.0, 2.0, 4.0, 8.0):
        i = int(np.argmin(np.abs(s["t"] - tt)))
        if abs(s["t"][i] - tt) > 0.15:
            continue
        print("  %5.2f  %6.1f%%  %6.1f%% %6.1f%% %6.1f%%  %6.1f%%"
              % (s["t"][i], 100 * s["tot"][i], 100 * s["bobina"][i],
                 100 * s["entre"][i], 100 * s["fuera"][i], 100 * s["pared"][i]))
    print("   vida 1/e del inventario: %.2f us" % vida_1e(s["t"], s["tot"]))
    print("   pico de plasma en la pared: %.1f%% en t=%.2f us"
          % (100 * s["pared"].max(), s["t"][int(s["pared"].argmax())]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--out", default=None, help="PNG comparativo")
    args = ap.parse_args()

    series = {}
    for d in args.run_dirs:
        nombre = Path(d).name
        series[nombre] = inventario(d)
        resumen(nombre, series[nombre])

    if not args.out:
        return
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    for nombre, s in series.items():
        axs[0].plot(s["t"], 100 * s["tot"], label=nombre)
        axs[1].plot(s["t"], 100 * s["bobina"], label=nombre)
        axs[2].plot(s["t"], 100 * s["pared"], label=nombre)
    for a, ttl, yl in (
            (axs[0], "Inventario retenido", "N / N$_0$ (%)"),
            (axs[1], "Dentro de la bobina ($|z|<18$ cm)", "N / N$_0$ (%)"),
            (axs[2], "Plasma pegado a la pared", "fracción (%)")):
        a.set_title(ttl)
        a.set_xlabel("t (µs)")
        a.set_ylabel(yl)
        a.grid(alpha=0.3)
        a.legend(fontsize=8)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print("\n->", out)


if __name__ == "__main__":
    main()
