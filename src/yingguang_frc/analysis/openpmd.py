"""Read cell-centered RZ m=0 fields using the coordinates stored in openPMD."""
from pathlib import Path

import h5py
import numpy as np


def mesh(dataset):
    # Vector components carry position/unitSI; their parent carries grid metadata.
    attrs = dict(dataset.parent.attrs)
    attrs.update(dataset.attrs)
    labels = [v.decode() if isinstance(v, bytes) else str(v)
              for v in attrs["axisLabels"]]
    if labels != ["z", "r"] or dataset.ndim != 3 or dataset.shape[0] != 1:
        raise ValueError("Only RZ m=0 fields with axes z,r are supported")
    if not np.allclose(attrs["position"], [.5, .5]):
        raise ValueError("Only cell-centered fields are supported")
    dz, dr = np.asarray(attrs["gridSpacing"]) * attrs.get("gridUnitSI", 1.)
    oz, orad = np.asarray(attrs["gridGlobalOffset"]) * attrs.get("gridUnitSI", 1.)
    if not np.all(np.isfinite([dz, dr, oz, orad])) or dr <= 0 or dz <= 0 or orad < 0:
        raise ValueError("Invalid RZ grid")
    values = np.asarray(dataset)[0].T * attrs.get("unitSI", 1.)
    r_edges = orad + np.arange(values.shape[0] + 1) * dr
    z_edges = oz + np.arange(values.shape[1] + 1) * dz
    return values, r_edges, z_edges


def iter_frames(run_dir, fields=("rho",)):
    files = sorted((Path(run_dir) / "diags/fields").glob("*.h5"))
    if not files:
        raise ValueError(f"No openPMD fields in {run_dir}/diags/fields")
    for path in files:
        with h5py.File(path) as h:
            for g in h["data"].values():
                frame = {"t": float(g.attrs["time"] * g.attrs.get("timeUnitSI", 1.))}
                for name in fields:
                    values, re, ze = mesh(g["fields"][name])
                    if "r_edges" in frame:
                        if not np.array_equal(re, frame["r_edges"]) or not np.array_equal(ze, frame["z_edges"]):
                            raise ValueError("Fields must share a grid")
                    frame.update(r_edges=re, z_edges=ze)
                    frame[name] = values
                frame["r"] = (re[:-1] + re[1:]) / 2
                frame["z"] = (ze[:-1] + ze[1:]) / 2
                yield frame


def load_series(run_dir):
    frames = []
    for frame in iter_frames(run_dir, ("rho", "B/r", "B/z", "B/t")):
        frame.update(Br=frame.pop("B/r"), Bz=frame.pop("B/z"), Bt=frame.pop("B/t"))
        frames.append(frame)
    frames.sort(key=lambda fr: fr["t"])
    for frame in frames[1:]:
        if not np.array_equal(frame["r_edges"], frames[0]["r_edges"]) or not np.array_equal(frame["z_edges"], frames[0]["z_edges"]):
            raise ValueError("Changing grids within a series are not supported")
    return frames
