"""Análisis de la simulación FRC Yingguang-I (diagnósticos sintéticos).

Lee los volcados openPMD (HDF5) de diags/fields y produce:
  - r_s(t): radio de separatriz por flujo excluido en el plano medio (Eq. 1 paper)
  - B_z(t) en la "sonda" (r≈pared, z=0)  [cf. Fig. 17a]
  - densidad de línea por el diámetro    [interferómetro, cf. Fig. 17a]
  - longitud del FRC por nulos de B_z en el eje
  - imágenes end-on sintéticas ∫n² dz    [cámara, cf. Fig. 15c]
  - T_i promedio dentro de la separatriz [cf. Fig. 17d]

Usage: python -m yingguang_frc.analysis.diagnostics RUN --out results/local/diagnostics
"""

import argparse
import sys
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from yingguang_frc.model import parameters as P


from yingguang_frc.analysis.openpmd import load_series


def particle_temperature(run_dir, t_us, rs, ls):
    """T_i (eV) dentro de la separatriz desde los volcados de partículas.

    T = m_p <|v - <v>|^2> / 3 ponderado por peso, con v = p/m_p (no rel.).
    Donde aún no hay separatriz (r_s=0) se usa el núcleo r < R_PLASMA/2.
    """
    files = sorted((Path(run_dir) / "diags" / "particles").glob("*.h5"))
    tp, Ti = [], []
    for f in files:
        with h5py.File(f, "r") as h:
            base = h["data"]
            for it in base:
                g = base[it]
                t = float(g.attrs["time"] * g.attrs.get("timeUnitSI", 1.0))
                p = g["particles/ions"]
                x = np.asarray(p["position/x"])
                y = np.asarray(p["position/y"])
                z = np.asarray(p["position/z"])
                w = np.asarray(p["weighting"])
                r = np.hypot(x, y)
                rs_t = np.interp(t * 1e6, t_us, rs)
                ls_t = np.interp(t * 1e6, t_us, ls)
                if rs_t > 1e-3 and ls_t > 1e-2:
                    m = (r < rs_t) & (np.abs(z) < ls_t / 2)
                else:
                    m = (r < P.R_PLASMA / 2) & (np.abs(z) < 0.1)
                if m.sum() < 100:
                    continue
                wm = w[m]
                T = 0.0
                for c in ("x", "y", "z"):
                    v = np.asarray(p[f"momentum/{c}"])[m] / P.MP
                    vbar = np.average(v, weights=wm)
                    T += np.average((v - vbar) ** 2, weights=wm)
                tp.append(t * 1e6)
                Ti.append(P.MP * T / 3 / P.QE)
    return np.asarray(tp), np.asarray(Ti)


def analyze(frames, outdir, run_dir="."):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    nr, nz = frames[0]["Bz"].shape
    r = frames[0]["r"]
    z = frames[0]["z"]
    jz0 = nz // 2
    jwall = nr - 2

    t_us, Bwall, rs, ls, nline = [], [], [], [], []
    phi_trap, ntot, nline_in = [], [], []
    for fr in frames:
        Bz, rho = fr["Bz"], fr["rho"]
        t_us.append(fr["t"] * 1e6)
        Bw = Bz[jwall, jz0]
        Bwall.append(Bw)

        # flujo excluido en plano medio
        phi_p = np.trapezoid(Bz[:, jz0] * 2 * np.pi * r, r)
        arg = 1 - phi_p / (np.pi * frames[0]["r_edges"][-1]**2 * Bw) if Bw != 0 else 0.0
        rs.append(frames[0]["r_edges"][-1] * np.sqrt(max(arg, 0.0)))

        # flujo invertido (atrapado): celdas del plano medio con Bz de
        # signo opuesto a la pared — es el flujo que cierra la FRC
        integ = Bz[:, jz0] * 2 * np.pi * r
        opp = np.sign(Bz[:, jz0]) == -np.sign(Bw)
        phi_trap.append(abs(np.trapezoid(np.where(opp, integ, 0.0), r)))

        # longitud FRC: distancia entre nulos de Bz en el eje
        s = np.sign(Bz[1, :])
        idx = np.where(np.diff(s) != 0)[0]
        ls.append(z[idx[-1]] - z[idx[0]] if len(idx) >= 2 else 0.0)

        # interferómetro: cuerda diametral en plano medio
        n = rho / P.QE
        nline.append(2 * np.trapezoid(n[:, jz0], r))

        # inventario: total del dominio (drenaje axial) y densidad de
        # linea del plano medio dentro de la separatriz (atrapamiento)
        ntot.append(np.trapezoid(
            np.trapezoid(n * 2 * np.pi * r[:, None], r, axis=0), z))
        nmid = n[:, jz0] * 2 * np.pi * r
        nline_in.append(np.trapezoid(np.where(r <= rs[-1], nmid, 0.0), r)
                        / max(np.trapezoid(nmid, r), 1.0))

    t_us = np.asarray(t_us)

    fig, axs = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    a = axs[0, 0]
    a.plot(t_us, Bwall, "k-")
    a.set_ylabel("$B_z$ pared, z=0 (T)")
    a.set_title("Sonda B sintética (cf. Fig. 17a)")
    a.axhline(0, color="0.5", lw=0.5)

    a = axs[0, 1]
    a.plot(t_us, np.asarray(rs) * 100, "b-")
    a.set_ylabel("$r_s$ (cm)")
    a.set_title("Separatriz por flujo excluido (cf. Figs. 16a/17b)")
    a.axhline(4.0, color="r", ls=":", label="exp: 4 cm")
    a.legend(fontsize=8)

    a = axs[1, 0]
    a.plot(t_us, np.asarray(nline) / 1e4 / 1e17, "g-")  # m^-2 -> 1e17 cm^-2
    a.set_ylabel("$\\int n\\,dl$ ($10^{17}$ cm$^{-2}$)")
    a.set_xlabel("t (µs)")
    a.set_title("Interferómetro sintético")
    a.axhline(2.8, color="r", ls=":", label="exp: 2.8e17")
    a.legend(fontsize=8)

    a = axs[1, 1]
    tp, Tip = particle_temperature(run_dir, t_us, np.asarray(rs), np.asarray(ls))
    if len(tp):
        a.plot(tp, Tip, "mo-", ms=4, label="desde partículas")
    a.set_ylabel("$T_i$ (eV)")
    a.set_xlabel("t (µs)")
    a.set_title("Temperatura iónica media (cf. Fig. 17d)")
    a.axhline(106, color="r", ls=":", label="Sun 2017: ~106 eV")
    a.legend(fontsize=8)

    fig.suptitle("FRC Yingguang-I — diagnósticos sintéticos WarpX")
    fig.tight_layout()
    fig.savefig(outdir / "res_diagnosticos.png", dpi=150)
    print("->", outdir / "res_diagnosticos.png")

    # Atrapamiento: flujo invertido e inventario (drenaje axial)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    a1.plot(t_us, np.asarray(phi_trap) * 1e3, "b-")
    a1.set_ylabel("$\\phi_{trap}$ (mWb)")
    a1.set_title("Flujo invertido atrapado en el plano medio")
    ntot = np.asarray(ntot)
    a2.plot(t_us, ntot / max(ntot[0], 1.0), "k-",
            label="inventario total / inicial")
    a2.plot(t_us, nline_in, "b--",
            label="fracción en plano medio dentro de $r_s$")
    a2.set_ylim(0, 1.05)
    a2.set_xlabel("t (µs)")
    a2.set_ylabel("fracción")
    a2.set_title("Retención de partículas")
    a2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "res_atrapamiento.png", dpi=150)
    print("->", outdir / "res_atrapamiento.png")

    np.savez(outdir / "res_series.npz", t_us=t_us, Bwall=Bwall, rs=rs,
             ls=ls, nline=nline, t_pi=tp, Ti_p=Tip,
             phi_trap=phi_trap, ntot=ntot, nline_in=nline_in)

    # Mapa 2D final + imágenes end-on
    fr = frames[-1]
    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 6))
    pc = a.pcolormesh(z, r, fr["rho"] / P.QE, cmap="inferno", shading="auto")
    fig.colorbar(pc, ax=a, label="$n_i$ (m$^{-3}$)")
    cs = a.contour(z, r, fr["Bz"], levels=[0], colors="c")
    a.set_ylabel("r (m)")
    a.set_title(f"n_i y contorno $B_z$=0 (cian) @ t={fr['t']*1e6:.2f} µs")

    lum = np.trapezoid((fr["rho"] / P.QE) ** 2, z, axis=1)
    b.plot(r * 100, lum / max(lum.max(), 1e-30), "k-")
    b.set_xlabel("r (cm)  |  z (m) arriba")
    b.set_ylabel("∫n² dz (norm.)")
    b.set_title("Perfil radial de luminosidad end-on sintética")
    fig.tight_layout()
    fig.savefig(outdir / "res_mapa_final.png", dpi=150)
    print("->", outdir / "res_mapa_final.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?", default=".")
    ap.add_argument("--out", default="figures")
    args = ap.parse_args()
    frames = load_series(args.run_dir)
    print(f"{len(frames)} volcados, t = {frames[0]['t']*1e6:.3f} .. "
          f"{frames[-1]['t']*1e6:.3f} µs")
    analyze(frames, args.out, run_dir=args.run_dir)
