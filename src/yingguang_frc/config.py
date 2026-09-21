"""Explicit, validated configurations shared by launching and device plots."""
from __future__ import annotations

import math
from pathlib import Path
import tomllib

from yingguang_frc.model import parameters as P

PARAMETERS = set("""R_COIL R_TUBE L_COIL W_FRINGE Z_MIRROR R_MIRROR
R_MIRROR_MEAN DZ_SECTIONS B_MIRROR_0 B_BIAS B_DRIVE_AMP N_BANDS RIPPLE_EPS
T_QUARTER TAU_CROWBAR N0 T_I0 T_E0 R_PLASMA DELTA_PLASMA Z_PLASMA
DELTA_Z_PLASMA LNLAMBDA ETA0 ETA_HYPER N_FLOOR_FRAC ETA_CLAMP_FACTOR
LR LZ NR NZ NPPC DT_FACTOR SUBSTEPS T_SIM""".split())
EXECUTION = set("""crowbar t_crowbar diag_ns no_div_clean no_filter verbose
substep_rtol substep_atol max_substep_attempts random_seed""".split())


def _keys(values, expected, section):
    if not isinstance(values, dict):
        raise ValueError(f"{section} must be a table")
    if set(values) != expected:
        raise ValueError(f"{section}: missing {sorted(expected - set(values))}; "
                         f"unknown {sorted(set(values) - expected)}")


def load(path):
    """Read a complete configuration; reject misspellings and unsafe values."""
    with Path(path).open("rb") as f:
        cfg = tomllib.load(f)
    _keys(cfg, {"schema_version", "name", "status", "description", "parameters",
                "execution"}, "configuration")
    if type(cfg["schema_version"]) is not int or cfg["schema_version"] != 1:
        raise ValueError("Unsupported configuration schema")
    for key in ("name", "status", "description"):
        if not isinstance(cfg[key], str) or not cfg[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    p, e = cfg["parameters"], cfg["execution"]
    _keys(p, PARAMETERS, "parameters")
    _keys(e, EXECUTION, "execution")
    signed = {"B_MIRROR_0", "DZ_SECTIONS"}
    nonnegative = {"RIPPLE_EPS", "Z_PLASMA", "ETA_CLAMP_FACTOR", "ETA_HYPER"}
    for key, value in p.items():
        values = value if key == "DZ_SECTIONS" else [value]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{key} must contain numerical values")
        for v in values:
            if type(v) not in (int, float) or not math.isfinite(v):
                raise ValueError(f"{key} must be finite and numerical")
            if key not in signed and (v < 0 if key in nonnegative else v <= 0):
                raise ValueError(f"Invalid {key}: {v}")
    for key in ("NR", "NZ", "NPPC", "SUBSTEPS", "N_BANDS"):
        if type(p[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    if p["NR"] < 2 or p["NZ"] < 2:
        raise ValueError("At least two cells per direction are required")
    if p["B_MIRROR_0"] >= 0:
        raise ValueError("Mirrors must oppose the positive bias")
    if not 0 < p["R_PLASMA"] < p["R_TUBE"] < p["R_COIL"]:
        raise ValueError("Require R_PLASMA < R_TUBE < R_COIL")
    if p["LR"] != p["R_TUBE"] or p["N_FLOOR_FRAC"] >= 1:
        raise ValueError("Require LR = R_TUBE and 0 < N_FLOOR_FRAC < 1")
    if p["Z_PLASMA"] > p["LZ"] / 2 or p["Z_MIRROR"] >= p["LZ"] / 2:
        raise ValueError("Plasma and mirror centers must fit inside the domain")
    for key in ("crowbar", "no_div_clean", "no_filter", "verbose"):
        if type(e[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")
    for key in ("t_crowbar", "diag_ns", "substep_rtol", "substep_atol",
                "max_substep_attempts"):
        if type(e[key]) not in (int, float) or not math.isfinite(e[key]) or e[key] <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if type(e["max_substep_attempts"]) is not int:
        raise ValueError("max_substep_attempts must be an integer")
    seed = e["random_seed"]
    if seed not in ("default", "random") and not (type(seed) is int and seed > 0):
        raise ValueError("random_seed must be 'default', 'random', or a positive integer")
    return cfg


def apply(cfg):
    """Resolve all device/plasma inputs, then apply the explicit resistivity."""
    P.override(**cfg["parameters"])
    P.ETA0 = cfg["parameters"]["ETA0"]
    return {key: value for key, value in vars(P).items()
            if key.isupper() and isinstance(value, (int, float, tuple, list))}
