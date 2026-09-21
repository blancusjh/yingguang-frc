"""Separar retención, concentración axial y compresión radial en RZ m=0.

Usa las coordenadas de celda y unidades de openPMD, sin auto-exposición
ni umbrales de brillo. L80 es la distancia entre los cuantiles axiales
10% y 90% del inventario DENTRO de la bobina, no la longitud de separatriz.
R80 encierra el 80% de ese mismo inventario en dirección radial.
La concentración central usa |z|<6 cm por defecto, una ventana diagnóstica
elegida explícitamente, no una longitud inferida del vídeo de referencia.

Uso:
  python -m yingguang_frc.analysis.compactness runs/corrected-mirrors --out results/local
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from yingguang_frc.analysis.openpmd import iter_frames

QE = 1.602176634e-19


def read_frames(run_dir):
    for fr in iter_frames(run_dir):
        yield fr["t"], fr["rho"] / QE, fr["r_edges"], fr["z_edges"]


def window_fraction(edges, half_width):
    """Fracción geométrica de cada celda en [-half_width, half_width]."""
    return np.maximum(0., np.minimum(edges[1:], half_width)
                      - np.maximum(edges[:-1], -half_width)) / np.diff(edges)


def quantile(edges, weights, q):
    total = weights.sum()
    if total <= 0:
        return float("nan")
    return float(np.interp(q * total, np.r_[0., np.cumsum(weights)], edges))


def measure(n, r_edges, z_edges, coil_half=.18, center_half=.06):
    # Volumen exacto del anillo cilíndrico; aproximación de n constante en celda.
    area = np.pi * np.diff(r_edges ** 2)
    dz = np.diff(z_edges)
    counts = np.maximum(n, 0.) * area[:, None] * dz[None, :]
    linear_counts = counts.sum(axis=0)
    total = counts.sum()
    coil_frac = window_fraction(z_edges, coil_half)
    center_frac = window_fraction(z_edges, center_half)
    coil_counts = counts * coil_frac[None, :]
    nc = coil_counts.sum()
    # Para los cuantiles, las celdas cortadas por el borde se acortan.
    z_coil = np.clip(z_edges, -coil_half, coil_half)
    length80 = (quantile(z_coil, coil_counts.sum(0), .9)
                - quantile(z_coil, coil_counts.sum(0), .1))
    # Interpolar el CDF radial en r² conserva el volumen de los anillos.
    radius80 = np.sqrt(quantile(r_edges ** 2, coil_counts.sum(1), .8))
    center = float(np.sum(linear_counts * center_frac))
    return dict(N=float(total), N_coil=float(nc), N_center=center,
                center_fraction=center / total if total > 0 else np.nan,
                L80_cm=length80 * 100, R80_cm=radius80 * 100), linear_counts / dz


def analyze(run_dir, coil_half=.18, center_half=.06):
    rows = []
    profiles = []
    for t, n, r_edges, z_edges in read_frames(run_dir):
        row, line = measure(n, r_edges, z_edges, coil_half, center_half)
        row["t_us"] = t * 1e6
        rows.append(row)
        profiles.append((t, (z_edges[:-1] + z_edges[1:]) / 2, line))
    rows.sort(key=lambda row: row["t_us"])
    profiles.sort(key=lambda x: x[0])
    if not rows or not np.isclose(rows[0]["t_us"], 0., rtol=0., atol=1e-9):
        raise ValueError("Retention requires the t=0 snapshot for normalization")
    n0 = rows[0]["N"]
    if n0 <= 0:
        raise ValueError("Inventario inicial nulo; no se puede normalizar")
    for row in rows:
        row["retained"] = row["N"] / n0
        row["center_initial"] = row["N_center"] / n0
    return rows, profiles


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", nargs="+", help="Una etiqueta por run, en el mismo orden")
    ap.add_argument("--coil-half-cm", type=float, default=18.)
    ap.add_argument("--center-half-cm", type=float, default=6.)
    args = ap.parse_args()
    if not 0 < args.center_half_cm <= args.coil_half_cm:
        ap.error("La ventana central debe ser positiva y caber en la bobina")
    if args.labels and len(args.labels) != len(args.runs):
        ap.error("--labels requiere una etiqueta por run")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout="constrained")
    snapshots = []
    labels = ["Retained plasma (% of initial)",
              f"In central {2*args.center_half_cm:g} cm (% of initial)",
              "Axial L80 inside coil (cm)", "Radial R80 inside coil (cm)"]
    fields = [("retained", 100), ("center_initial", 100),
              ("L80_cm", 1), ("R80_cm", 1)]
    for i, run in enumerate(args.runs):
        name = (args.labels[i] if args.labels else
                Path(run).as_posix().removeprefix("runs/").lstrip("_"))
        rows, profiles = analyze(run, args.coil_half_cm / 100,
                                 args.center_half_cm / 100)
        with (out / f"{i:02d}_{Path(run).name}.csv").open("w") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        for ax, (key, scale), label in zip(axes.flat, fields, labels):
            ax.plot([r["t_us"] for r in rows], [scale*r[key] for r in rows], label=name)
            ax.set(xlabel="Simulation time (µs)", ylabel=label)
        # Mostrar perfiles absolutos: cada curva lleva el instante real.
        for ax, target in zip(axes.flat[4:], [4., 8.]):
            t, z, line = min(profiles, key=lambda p: abs(p[0]*1e6-target))
            ax.plot(z * 100, line / 1e19, label=f"{name}, {t*1e6:.2f} µs")
            ax.set(xlabel="Axial position z (cm)", ylabel="dN/dz (10¹⁹ ions/m)",
                   xlim=(-30, 30), title=f"Axial inventory near {target:g} µs")
        row = rows[-1]
        available = list(read_frames(run))
        snapshots.append((name, [min(available, key=lambda p: abs(p[0]*1e6-target))
                                 for target in [4., 8.]]))
        print(f"{name}: t={row['t_us']:.2f} us, retained={row['retained']:.1%}, "
              f"center/initial={row['center_initial']:.1%}, "
              f"center/remaining={row['center_fraction']:.1%}, "
              f"L80={row['L80_cm']:.2f} cm, R80={row['R80_cm']:.2f} cm")
    for ax in axes.flat:
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.savefig(out / "compactness.png", dpi=160)
    plt.close(fig)

    # Cortes directos de densidad: una escala absoluta para todos los runs
    # e instantes, sin filtro espacial ni ajuste individual de exposición.
    vmax = max(np.quantile(fr[1], .997) for _, frames in snapshots for fr in frames)
    fig, axes = plt.subplots(len(snapshots), 2, squeeze=False,
                             figsize=(13, 2.5*len(snapshots)), layout="constrained")
    for row_axes, (name, frames) in zip(axes, snapshots):
        for ax, (t, n, re, ze) in zip(row_axes, frames):
            radial_edges = np.r_[-re[:0:-1], re]
            density = np.concatenate([n[::-1], n], axis=0)
            im = ax.pcolormesh(ze*100, radial_edges*100, density/1e22,
                               shading="flat", cmap="inferno", vmin=0.,
                               vmax=max(vmax, 1.)/1e22, rasterized=True)
            ax.set(xlim=(-args.coil_half_cm, args.coil_half_cm),
                   xlabel="z (cm)", ylabel="Signed radius (cm)",
                   title=f"{name}, {t*1e6:.2f} µs", aspect="equal")
    fig.colorbar(im, ax=axes.ravel().tolist(), label="Ion density (10²² m⁻³)", shrink=.8)
    fig.savefig(out / "density_slices.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
