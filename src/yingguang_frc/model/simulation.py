"""WarpX worker for an explicit Yingguang-I simulation configuration.

Launch through frc-run so the configuration, source, and environment are
recorded alongside outputs. This module preserves the corrected-mirror PICMI model.
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np

from yingguang_frc.model import parameters as P

from yingguang_frc.config import load, apply

parser = argparse.ArgumentParser(description="WarpX worker; use frc-run to record provenance.")
parser.add_argument("--config", required=True)
parser.add_argument("--steps", type=int)
parsed = parser.parse_args()
if parsed.steps is not None and parsed.steps <= 0:
    parser.error("--steps must be positive")
configuration = load(parsed.config)
apply(configuration)
args = argparse.Namespace(**configuration["execution"], steps=parsed.steps)

# Import only after configuration validation; --help works without WarpX.
from pywarpx import picmi
constants = picmi.constants

# ---------------------------------------------------------------------------
# Parámetros numéricos
# ---------------------------------------------------------------------------
q = P.plasma_quantities()
DT = q["dt"]
TOTAL_STEPS = args.steps or q["n_steps"]
DIAG_PERIOD = max(1, int(args.diag_ns * 1e-9 / DT))

RHO0 = P.N0 * P.QE
RHO_FLOOR = P.N_FLOOR_FRAC * RHO0

print(f"[frc] dt={DT:.3e} s  pasos={TOTAL_STEPS}  "
      f"t_final={DT*TOTAL_STEPS*1e6:.2f} us  diag cada {DIAG_PERIOD} pasos")
print(f"[frc] malla {P.NR}x{P.NZ}  dr={P.LR/P.NR*1e3:.2f} mm  "
      f"dz={P.LZ/P.NZ*1e3:.2f} mm  ppc={P.NPPC}")
print(f"[frc] n0={P.N0:.2e} m^-3  Ti0={P.T_I0:g} eV  Te0={P.T_E0:g} eV  "
      f"eta0={P.ETA0:.2e}  clamp={P.ETA_CLAMP_FACTOR:g}x  "
      f"drive={P.B_DRIVE_AMP:g} T  espejo={P.B_MIRROR_0:g} T  "
      f"ripple={P.RIPPLE_EPS:g}")
_beta = P.beta_inicial()
print(f"[frc] beta(t=0) = {_beta:.2f} frente al bias de {P.B_BIAS:g} T"
      + ("   <-- initial thermal pressure exceeds nominal bias pressure" if _beta > 1 else "")
      + f"   relleno axial: {'tubo entero' if not P.Z_PLASMA else f'|z|<{P.Z_PLASMA*100:.0f} cm'}")

simulation = picmi.Simulation(verbose=args.verbose, warpx_random_seed=args.random_seed)

# ---------------------------------------------------------------------------
# Malla RZ y fronteras
# ---------------------------------------------------------------------------
grid = picmi.CylindricalGrid(
    number_of_cells=[P.NR, P.NZ],
    lower_bound=[0.0, -P.LZ / 2],
    upper_bound=[P.LR, P.LZ / 2],
    lower_boundary_conditions=["none", "dirichlet"],
    upper_boundary_conditions=["dirichlet", "dirichlet"],
    lower_boundary_conditions_particles=["none", "absorbing"],
    upper_boundary_conditions_particles=["absorbing", "absorbing"],
    warpx_max_grid_size=64,
)
simulation.time_step_size = DT
simulation.max_steps = TOTAL_STEPS
simulation.current_deposition_algo = "direct"
simulation.particle_shape = 1
simulation.use_filter = not args.no_filter

# ---------------------------------------------------------------------------
# Solver híbrido + drive del theta-pinch (A externo)
# ---------------------------------------------------------------------------
# Perfil axial de la bobina f(z) en sintaxis del parser de WarpX
fz = (f"(0.5*(tanh((z+{P.L_COIL/2})/{P.W_FRINGE})"
      f"-tanh((z-{P.L_COIL/2})/{P.W_FRINGE})))")

# A_theta = -(r/2)*B_drive*f(z)  ->  B_z = -B_drive*f(z) (invertido vs bias)
# g(t): seno puro (2017) o retención por crowbar tras el pico (diseño 2013)
if args.crowbar:
    t_cb = args.t_crowbar * 1e-6 if args.t_crowbar else P.T_QUARTER
    g_cb = math.sin(P.OMEGA_DRIVE * t_cb)
    g_t = (f"if(t<{t_cb}, sin({P.OMEGA_DRIVE}*t), "
           f"{g_cb}*exp(-(t-{t_cb})/{P.TAU_CROWBAR}))")
else:
    g_t = f"sin({P.OMEGA_DRIVE}*t)"
ax_expr = f"0.5*y*{P.B_DRIVE_AMP}*{fz}"
ay_expr = f"-0.5*x*{P.B_DRIVE_AMP}*{fz}"
if P.RIPPLE_EPS:
    # Bandas discretas de la bobina: primer armonico de vacio
    #   A_theta_rip = +(B_D*eps/k)*I1(kr)/I0(kR_c)*cos(kz)*f(z)
    #   -> Bz_rip = +B_D*eps*I0(kr)/I0(kR_c)*cos(kz)*f(z)
    # (refuerza |B| bajo las bandas, cos=-1 en multiplos impares de
    # lambda/2, y lo debilita en los huecos). Bessel aproximada por su
    # asintotica exp(k(r-R_c))*sqrt(R_c/r), valida donde el rizado es
    # relevante (kr > 4); el max() protege el eje.
    k = P.K_RIPPLE
    rs = "max(sqrt(x*x+y*y),1e-4)"
    rip = (f"({P.B_DRIVE_AMP * P.RIPPLE_EPS / k})"
           f"*exp({k}*({rs}-{P.R_COIL}))*sqrt({P.R_COIL}/{rs})"
           f"*cos({k}*z)*{fz}")
    ax_expr += f"-(y/{rs})*{rip}"
    ay_expr += f"+(x/{rs})*{rip}"
A_ext = {
    "theta_coil": {
        "Ax_external_function": ax_expr,
        "Ay_external_function": ay_expr,
        "Az_external_function": "0",
        "A_time_external_function": g_t,
    }
}

solver = picmi.HybridPICSolver(
    grid=grid,
    gamma=5.0 / 3.0,
    Te=P.T_E0,
    n0=P.N0,
    n_floor=P.N_FLOOR_FRAC * P.N0,
    # eta(n) = eta0 * (rho0/rho): Spitzer(Te0) con Te ~ n^(gamma-1),
    # con tope ETA_CLAMP_FACTOR*eta0 (evita aniquilar el flujo invertido
    # en la capa de baja densidad, donde el floor daria 50*eta0)
    plasma_resistivity=(
        f"min({P.ETA0}*{RHO0}/max(rho,{RHO_FLOOR}),"
        f"{P.ETA_CLAMP_FACTOR * P.ETA0})"
        if P.ETA_CLAMP_FACTOR
        else f"{P.ETA0}*{RHO0}/max(rho,{RHO_FLOOR})"
    ),
    plasma_hyper_resistivity=P.ETA_HYPER,
    substeps=P.SUBSTEPS,
    use_rkf45=True,
    holmstrom_vacuum_region=True,
    A_external=A_ext,
    **{k: v for k, v in (("substep_rtol", args.substep_rtol),
                         ("substep_atol", args.substep_atol),
                         ("max_substep_attempts", args.max_substep_attempts))
       if v is not None},
)
simulation.solver = solver


# ---------------------------------------------------------------------------
# Campo externo inicial (bias + espejos) cargado en la malla
# ---------------------------------------------------------------------------
def load_initial_field():
    for comp in ("r", "theta", "z"):
        F = simulation.fields.get("Bfield_fp_external", dir=comp, level=0)
        RM, ZM = np.meshgrid(F.mesh("r"), F.mesh("z"), indexing="ij")
        if comp == "theta":
            F[:, :] = 0.0
        else:
            Br, Bz = P.initial_field(RM, ZM)
            F[:, :] = Br if comp == "r" else Bz


B_ext = picmi.LoadInitialFieldFromPython(
    load_from_python=load_initial_field,
    warpx_do_initial_div_cleaning=not args.no_div_clean,
    load_B=True,
    load_E=False,
)
simulation.add_applied_field(B_ext)

# ---------------------------------------------------------------------------
# Iones H+: relleno uniforme con borde suave, maxwelliano
# ---------------------------------------------------------------------------
v_thi = np.sqrt(P.T_I0 * P.QE / P.MP)

# NO activar warpx_do_temperature_deposition: corrompe el heap en RZ
# (WarpX 26.07, doVarianceDepositionShapeN). T_i se calcula en postproceso
# desde los volcados de particulas, en analysis/diagnostics.py.
ions = picmi.Species(
    name="ions",
    charge="q_e",
    mass=P.MP,
    initial_distribution=picmi.AnalyticDistribution(
        density_expression=(
            "n0_p/(1+exp((sqrt(x*x+y*y)-R_p)/delta_p))"
            + ("/(1+exp((sqrt(z*z)-Z_p)/delta_z))" if P.Z_PLASMA else "")
        ),
        momentum_expressions=["0", "0", "0"],
        warpx_momentum_spread_expressions=[str(v_thi)] * 3,
        warpx_density_min=P.N_FLOOR_FRAC * P.N0,
        n0_p=P.N0,
        R_p=P.R_PLASMA,
        delta_p=P.DELTA_PLASMA,
        **({"Z_p": P.Z_PLASMA, "delta_z": P.DELTA_Z_PLASMA} if P.Z_PLASMA else {}),
    ),
)
simulation.add_species(
    ions,
    layout=picmi.PseudoRandomLayout(grid=grid, n_macroparticles_per_cell=P.NPPC),
)

# ---------------------------------------------------------------------------
# Diagnósticos
# ---------------------------------------------------------------------------
field_diag = picmi.FieldDiagnostic(
    name="fields",
    grid=grid,
    period=DIAG_PERIOD,
    data_list=["B", "E", "rho"],
    write_dir="diags",
    warpx_format="openpmd",
    warpx_openpmd_backend="h5",
)
simulation.add_diagnostic(field_diag)

part_diag = picmi.ParticleDiagnostic(
    name="particles",
    period=max(DIAG_PERIOD * 10, 1),
    species=[ions],
    data_list=["ux", "uy", "uz", "x", "z", "weighting"],
    write_dir="diags",
    warpx_format="openpmd",
    warpx_openpmd_backend="h5",
)
simulation.add_diagnostic(part_diag)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
simulation.initialize_inputs()

# El memory-profiler del TinyProfiler añade contabilidad por asignación y
# no se usa aquí.
from pywarpx.WarpX import warpx as _warpx_inputs  # noqa: E402
_warpx_inputs.get_bucket("tiny_profiler").memprof_enabled = 0

simulation.initialize_warpx()
simulation.step()
