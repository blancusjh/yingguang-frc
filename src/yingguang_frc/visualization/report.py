"""Plot a compactness table without WarpX or raw simulation data."""
import argparse
from pathlib import Path
import numpy as np


def plot_table(table, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = np.atleast_1d(np.genfromtxt(table, delimiter=",", names=True))
    panels = [("retained", 100, "Retained ions (% of initial)"),
              ("center_initial", 100, "Central ions (% of initial)"),
              ("L80_cm", 1, "Axial L80 inside coil (cm)"),
              ("R80_cm", 1, "Radial R80 inside coil (cm)")]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), layout="constrained")
    for ax, (key, factor, label) in zip(axes.flat, panels):
        ax.plot(data["t_us"], factor * data[key], color="#256779", lw=2)
        ax.set(xlabel="Simulation time (µs)", ylabel=label)
        ax.grid(alpha=.2)
    fig.suptitle("Yingguang-I · plasma retention and compactness")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plot_table(args.table, args.out)


if __name__ == "__main__":
    main()
