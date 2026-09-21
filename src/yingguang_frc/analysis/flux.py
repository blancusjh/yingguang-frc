"""Exploratory poloidal-flux and smoothed axial-maximum diagnostics.

Integrates Bz over radius and searches inside the theta coil. The interpretation
as closed flux assumes a separatrix flux of zero and suitable magnetic geometry.
The smoothed axial maximum count is a proxy, not a general topology algorithm.
These values do not define the published compactness measurements.

Run with: python -m yingguang_frc.analysis.flux RUN --out figure.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d

from yingguang_frc.model import parameters as P
from yingguang_frc.analysis.openpmd import load_series

# Un minimo local cuenta como isla si llega al menos a esta fraccion del
# minimo global: filtra el rizado numerico sin perder toroides reales.
UMBRAL_ISLA = 0.15
# Suavizado axial antes de contar maximos. El rizado de las bandas tiene
# periodo 4.5 cm y la malla lo resuelve de sobra, asi que sin filtrar salen
# una docena de "islas" que son corrugacion, no toroides.
SIGMA_ISLA_CM = 1.0


def flujo_poloidal(Bz, r):
    """psi(r,z) = int_0^r Bz 2*pi*r' dr'  (Wb), acumulado en el eje radial."""
    integrando = Bz * 2 * np.pi * r[:, None]
    psi = np.zeros_like(Bz)
    psi[1:] = np.cumsum(0.5 * (integrando[1:] + integrando[:-1])
                        * np.diff(r)[:, None], axis=0)
    return psi


def metricas_frame(Bz, rho, r, z):
    """Metricas de un instante: flujo cerrado, punto O, islas, contraste."""
    psi = flujo_poloidal(Bz, r)
    # solo dentro de la bobina: fuera dominan los espejos (ver cabecera)
    dentro_bobina = np.abs(z) < P.L_COIL / 2
    # y solo donde el punto O es INTERIOR: si el maximo radial de psi cae en
    # la pared no hay nulo de campo, luego no hay flujo cerrado sino el
    # campo directo de la bobina. Sin esto, antes de la inversion salen
    # varios mWb espurios.
    i_r = psi.argmax(axis=0)
    hay_nulo = i_r < (len(r) - 2)
    valido = dentro_bobina & hay_nulo
    perfil = np.where(valido, psi.max(axis=0), -np.inf)
    if not valido.any() or perfil.max() <= 0:
        return dict(flujo=0.0, zO=np.nan, nislas=0, ratio=1.0, rO=np.nan)
    i_glob = int(perfil.argmax())
    psi_max = perfil[i_glob]

    if psi_max <= 0:                  # no hay flujo atrapado: no hay FRC
        return dict(flujo=0.0, zO=np.nan, nislas=0, ratio=1.0, rO=np.nan)

    # --- islas: maximos locales del perfil axial por encima del umbral
    corte = UMBRAL_ISLA * psi_max
    dz_cm = (z[1] - z[0]) * 100
    suave = gaussian_filter1d(np.where(valido, psi.max(axis=0), 0.0),
                              SIGMA_ISLA_CM / dz_cm)
    maximos = []
    for i in range(1, len(perfil) - 1):
        if not valido[i]:
            continue
        if suave[i] >= suave[i - 1] and suave[i] > suave[i + 1] \
                and suave[i] > corte:
            maximos.append(i)
    if not maximos:
        maximos = [i_glob]

    # --- contraste de densidad dentro/fuera de la separatriz (psi > 0)
    dentro = (psi > 0) & valido[None, :]
    n_in = rho[dentro].mean() / P.QE if dentro.any() else 0.0
    n_out = rho[~dentro].mean() / P.QE if (~dentro).any() else 1.0
    ratio = n_in / max(n_out, 1e-30)

    return dict(flujo=psi_max,                     # Wb
                zO=z[i_glob],
                rO=r[int(psi[:, i_glob].argmax())],
                nislas=len(maximos),
                ratio=ratio)


def serie(run_dir):
    frames = load_series(run_dir)
    nr, nz = frames[0]["Bz"].shape
    r = frames[0]["r"]
    z = frames[0]["z"]
    out = {k: [] for k in ("t", "flujo", "zO", "rO", "nislas", "ratio")}
    for f in frames:
        m = metricas_frame(f["Bz"], f["rho"], r, z)
        out["t"].append(f["t"])
        for k in ("flujo", "zO", "rO", "nislas", "ratio"):
            out[k].append(m[k])
    return {k: np.asarray(v) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--validar", default=None,
                    help="metricas_flujo.npz de referencia para comparar")
    args = ap.parse_args()

    s = serie(args.run_dir)
    t_us = s["t"] * 1e6
    print("  t(us)  flujo(mWb)  islas  z_O(cm)  r_O(cm)  n_in/n_out")
    for tt in (0.5, 1, 2, 3, 4, 5, 6, 7, 8):
        i = int(np.argmin(np.abs(t_us - tt)))
        if abs(t_us[i] - tt) > 0.2:
            continue
        print("  %5.2f  %9.3f  %5d  %7.1f  %7.2f  %9.2f"
              % (t_us[i], 1e3 * s["flujo"][i], s["nislas"][i],
                 100 * s["zO"][i], 100 * s["rO"][i], s["ratio"][i]))
    k = int(s["flujo"].argmax())
    print("  pico: %.3f mWb en t=%.2f us" % (1e3 * s["flujo"][k], t_us[k]))

    if args.validar:
        ref = np.load(args.validar)
        tr, fr = ref["t"], ref["flujo"]   # el npz guarda t en us
        fi = np.interp(tr, t_us, s["flujo"] * 1e3)
        m = fr > 0.05 * fr.max()
        err = np.abs(fi[m] - fr[m]) / fr[m]
        print("\n  validacion contra %s" % Path(args.validar).name)
        print("    pico  referencia %.3f  /  aqui %.3f mWb" % (fr.max(), fi.max()))
        print("    error relativo mediano donde hay flujo: %.1f %%"
              % (100 * np.median(err)))

    if args.out:
        fig, axs = plt.subplots(1, 3, figsize=(14, 4))
        axs[0].plot(t_us, 1e3 * s["flujo"]); axs[0].set_ylabel("flujo cerrado (mWb)")
        axs[1].step(t_us, s["nislas"], where="mid"); axs[1].set_ylabel("islas")
        axs[1].set_ylim(0, max(4, s["nislas"].max() + 1))
        axs[2].plot(t_us, 100 * s["zO"]); axs[2].set_ylabel("$z_O$ (cm)")
        axs[2].axhline(0, color="0.6", lw=0.6)
        for a in axs:
            a.set_xlabel("t (µs)"); a.grid(alpha=0.3)
        fig.tight_layout()
        out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150); print("\n->", out)


if __name__ == "__main__":
    main()
