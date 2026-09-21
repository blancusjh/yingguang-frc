"""Draw the configured geometry, initial axial field, and drive waveform."""
import argparse
from pathlib import Path
import numpy as np
from yingguang_frc.config import load, apply
from yingguang_frc.model import parameters as P


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cfg = load(args.config)
    apply(cfg)
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), layout="constrained")
    ax = axes[0]
    ax.add_patch(Rectangle((-P.LZ/2*100, -P.R_TUBE*100), P.LZ*100,
                           2*P.R_TUBE*100, fill=False, edgecolor="gray"))
    for z in np.linspace(-P.L_COIL/2, P.L_COIL/2, P.N_BANDS):
        for sign in (-1, 1):
            ax.add_patch(Rectangle((z*100-1, sign*P.R_COIL*100-.4), 2, .8,
                                   color="#b16c3c"))
    for z in (-P.Z_MIRROR, P.Z_MIRROR):
        for sign in (-1, 1):
            ax.add_patch(Rectangle((z*100-4, sign*P.R_MIRROR*100-.5), 8, 1,
                                   color="#256779"))
    ax.add_patch(Rectangle((-P.Z_PLASMA*100, -P.R_PLASMA*100),
                           2*P.Z_PLASMA*100, 2*P.R_PLASMA*100,
                           color="#e5b64b", alpha=.3))
    ax.set(xlim=(-55, 55), ylim=(-10, 10), xlabel="z (cm)", ylabel="Signed radius (cm)",
           title="Device: tube, theta-pinch bands, mirrors, nominal plasma fill")
    z = np.linspace(-P.LZ/2, P.LZ/2, 1001)
    axes[1].plot(z*100, P.initial_field(np.zeros_like(z), z)[1], color="#256779")
    axes[1].axhline(0, color="gray", lw=.7)
    axes[1].set(xlabel="z (cm)", ylabel="Initial axial Bz (T)",
                title=f"Bias +{P.B_BIAS:g} T; mirrors {P.B_MIRROR_0:g} T")
    t = np.linspace(0, P.T_SIM, 1000)
    e = cfg["execution"]
    axes[2].plot(t*1e6, P.drive_waveform(t, e["crowbar"], e["t_crowbar"]*1e-6),
                 color="#256779")
    axes[2].set(xlabel="Simulation time (µs)", ylabel="Drive component (T)",
                title="Prescribed theta-pinch drive (excluding bias and mirrors)")
    for ax in axes:
        ax.grid(alpha=.2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
