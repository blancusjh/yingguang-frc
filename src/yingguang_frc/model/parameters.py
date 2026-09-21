"""Parámetros físicos y numéricos del Yingguang-I (Sun et al. 2017, MRE 2, 263)
y del modelo de simulación WarpX hybrid-PIC.

Device constants and field functions. Run-specific values are loaded from
an explicit configuration by yingguang_frc.config before simulation.

Convenciones: SI salvo indicación. Eje z = eje del dispositivo, r radial.
"""

import sys

import numpy as np
from scipy.special import ellipe, ellipk

_this = sys.modules[__name__]   # para que override() escriba en el modulo

# ---------------------------------------------------------------------------
# Constantes físicas
# ---------------------------------------------------------------------------
MU0 = 4.0e-7 * np.pi
QE = 1.602176634e-19
MP = 1.67262192369e-27
ME = 9.1093837015e-31
EPS0 = 8.8541878128e-12
KB = 1.380649e-23
CLIGHT = 299792458.0

# Configured device and initial state; all are explicit in corrected-mirrors.toml.
# Lengths are in metres, times in seconds, fields in tesla, temperatures in eV.
R_COIL = 0.062
R_TUBE = 0.0525
L_COIL = 0.36
W_FRINGE = 0.031
Z_MIRROR = 0.30
R_MIRROR = 0.07
B_MIRROR_0 = -0.9  # Sun 2013 §2.3: opposite to bias, aligned with main drive.
B_BIAS = 0.2
B_DRIVE_AMP = 1.7
N_BANDS = 8
K_RIPPLE = 2 * np.pi * N_BANDS / L_COIL
RIPPLE_EPS = 1.2
T_QUARTER = 3.8e-6
T_FULL = 4 * T_QUARTER
OMEGA_DRIVE = 2 * np.pi / T_FULL
TAU_CROWBAR = 50e-6
N0_PHYSICAL = 3.9e21
N0 = N0_PHYSICAL
T_I0 = 10.0
T_E0 = 10.0
R_PLASMA = 0.048
DELTA_PLASMA = 0.003
Z_PLASMA = 0.18
DELTA_Z_PLASMA = 0.03
LNLAMBDA = 10.0
ETA0 = 1.47e-6  # Prescribed resistivity; independent of electron temperature.
ETA_HYPER = 3.5e-10
N_FLOOR_FRAC = 0.05
ETA_CLAMP_FACTOR = 10.0
LR = R_TUBE
LZ = 1.00
NR = 48
NZ = 176
NPPC = 20
DT_FACTOR = 0.04
SUBSTEPS = 40
T_SIM = 8.0e-6

# ---------------------------------------------------------------------------
# Funciones de campo
# ---------------------------------------------------------------------------
def coil_profile(z, l=None, w=None):
    """Perfil axial normalizado f(z) del campo de la bobina theta-pinch."""
    l = L_COIL if l is None else l
    w = W_FRINGE if w is None else w
    return 0.5 * (np.tanh((z + l / 2) / w) - np.tanh((z - l / 2) / w))


def coil_profile_dz(z, l=None, w=None):
    """df/dz del perfil axial."""
    l = L_COIL if l is None else l
    w = W_FRINGE if w is None else w
    return 0.5 / w * (np.cosh((z + l / 2) / w) ** -2
                      - np.cosh((z - l / 2) / w) ** -2)


def loop_field(r, z, a, z0, current):
    """Campo (Br, Bz) de una espira de radio a en z0 con corriente I (SI).

    Solucion exacta con integrales elipticas; regularizada en el eje.
    """
    r = np.asarray(r, dtype=float)
    z = np.asarray(z, dtype=float)
    rho = np.maximum(np.abs(r), 1e-9)
    zz = z - z0
    alpha2 = a**2 + rho**2 + zz**2 - 2 * a * rho
    beta2 = a**2 + rho**2 + zz**2 + 2 * a * rho
    k2 = 1 - alpha2 / beta2
    K = ellipk(k2)
    E = ellipe(k2)
    C = MU0 * current / np.pi
    Bz = C / (2 * np.sqrt(beta2)) * (
        (a**2 - rho**2 - zz**2) / alpha2 * E + K)
    Br = C * zz / (2 * rho * np.sqrt(beta2)) * (
        (a**2 + rho**2 + zz**2) / alpha2 * E - K)
    Br = np.where(np.abs(r) < 1e-8, 0.0, Br)
    return Br, Bz


# Espejo distribuido: una espira equivalente por seccion de solenoide, en el
# radio medio de las 4 capas de hilo de 4.5 mm (Sun 2013 §2.3). Suaviza el
# gradiente en el borde del dominio frente a la espira unica.
R_MIRROR_MEAN = R_MIRROR + 0.009        # m, radio medio de las capas
DZ_SECTIONS = (-0.025, 0.0, 0.025)      # m, centros de las 3 secciones


def _mirror_unit(r, z, z0):
    """Campo del conjunto espejo en z0 por amperio-vuelta total."""
    Br, Bz = 0.0, 0.0
    for d in DZ_SECTIONS:
        br, bz = loop_field(r, z, R_MIRROR_MEAN, z0 + d, 1.0 / len(DZ_SECTIONS))
        Br, Bz = Br + br, Bz + bz
    return Br, Bz


NI_MIRROR = 0.0         # A-vuelta del espejo, calibrados para B_MIRROR_0 en
                        # el eje; deriva de B_MIRROR_0, lo fija
                        # recompute_derived()


# ---------------------------------------------------------------------------
# Cantidades derivadas
# ---------------------------------------------------------------------------
# Estas dependen de valores que se pueden sobreescribir desde la linea de
# ordenes, asi que NO pueden quedar congeladas al importar: se recalculan
# todas juntas. Al añadir una derivada nueva, ponla aqui y no habra que
# acordarse de nada en el script de simulacion.
def recompute_derived() -> None:
    """Recalcula todo lo que depende de un parametro sobreescribible."""
    global NI_MIRROR, T_FULL, OMEGA_DRIVE, K_RIPPLE
    NI_MIRROR = B_MIRROR_0 / float(_mirror_unit(0.0, Z_MIRROR, Z_MIRROR)[1])
    T_FULL = 4 * T_QUARTER
    OMEGA_DRIVE = 2 * np.pi / T_FULL
    K_RIPPLE = 2 * np.pi * N_BANDS / L_COIL


def override(**kwargs) -> None:
    """Sobreescribe parametros y recalcula las derivadas.

    Los valores None se ignoran, para poder pasar directamente los flags
    de argparse sin filtrarlos.
    """
    for name, value in kwargs.items():
        if value is None:
            continue
        if not hasattr(_this, name):
            raise KeyError(f"parametro desconocido: {name}")
        setattr(_this, name, value)
    recompute_derived()


def mirror_field(r, z):
    """Campo (Br, Bz) de las dos bobinas espejo."""
    Br1, Bz1 = _mirror_unit(r, z, +Z_MIRROR)
    Br2, Bz2 = _mirror_unit(r, z, -Z_MIRROR)
    return (Br1 + Br2) * NI_MIRROR, (Bz1 + Bz2) * NI_MIRROR


def initial_field(r, z):
    """Campo externo inicial (Br, Bz): bias con perfil de bobina + espejos."""
    Brm, Bzm = mirror_field(r, z)
    Bz = B_BIAS * coil_profile(z) + Bzm
    Br = -0.5 * r * B_BIAS * coil_profile_dz(z) + Brm
    return Br, Bz


def drive_waveform(t, crowbar=True, t_crowbar=2.2e-6):
    """Campo del drive theta-pinch en vacio, en el centro (T), vs t desde el
    disparo del banco. Negativo = invertido respecto al bias.
    Configured case: crowbar at 2.2 microseconds followed by L/R decay."""
    t = np.asarray(t, dtype=float)
    rise = np.sin(OMEGA_DRIVE * t)
    if not crowbar:
        return -B_DRIVE_AMP * rise
    hold = np.sin(OMEGA_DRIVE * t_crowbar) * np.exp(-(t - t_crowbar) / TAU_CROWBAR)
    return -B_DRIVE_AMP * np.where(t < t_crowbar, rise, hold)


def density_profile(r, z=None):
    """Perfil inicial de densidad ionica.

    Radial siempre; axial solo si Z_PLASMA > 0 (ver la nota alli).
    """
    n = N0 / (1 + np.exp((np.asarray(r) - R_PLASMA) / DELTA_PLASMA))
    if Z_PLASMA and z is not None:
        n = n / (1 + np.exp((np.abs(np.asarray(z)) - Z_PLASMA) / DELTA_Z_PLASMA))
    return n


def beta_inicial(n=None, Ti=None, Te=None, B=None):
    """Beta del plasma en t=0, frente al bias.

    This is a pressure-ratio diagnostic relative to the nominal bias,
    not a proof of equilibrium or a stability criterion.
    """
    n = N0 if n is None else n
    Ti = T_I0 if Ti is None else Ti
    Te = T_E0 if Te is None else Te
    B = B_BIAS if B is None else B
    return 2 * MU0 * n * (Ti + Te) * QE / B**2


# ---------------------------------------------------------------------------
# Cantidades derivadas del plasma
# ---------------------------------------------------------------------------
def plasma_quantities(n=None, B=None, Ti=None):
    """Escalas del plasma. Sin argumentos usa los valores VIGENTES del
    modulo, no los que hubiera al importar."""
    n = N0 if n is None else n
    Ti = T_I0 if Ti is None else Ti
    q = {}
    q["w_pi"] = np.sqrt(n * QE**2 / (MP * EPS0))
    q["d_i"] = CLIGHT / q["w_pi"]
    B_peak = B_BIAS + B_DRIVE_AMP if B is None else B
    q["w_ci"] = QE * B_peak / MP
    q["t_ci"] = 2 * np.pi / q["w_ci"]
    q["v_thi"] = np.sqrt(Ti * QE / MP)
    q["rho_i"] = q["v_thi"] / q["w_ci"]
    q["v_A"] = B_peak / np.sqrt(MU0 * n * MP)
    q["dt"] = DT_FACTOR / q["w_ci"]
    q["n_steps"] = int(T_SIM / q["dt"])
    return q


recompute_derived()


if __name__ == "__main__":
    q = plasma_quantities()
    print("Derivados (n0=%.1e m^-3, B_peak=%.1f T):" % (N0, B_BIAS + B_DRIVE_AMP))
    for k, v in q.items():
        print(f"  {k:8s} = {v:.4g}")
    print(f"  NI espejo = {NI_MIRROR/1e3:.0f} kA-vuelta")
    print(f"  eta0      = {ETA0:.3g} Ohm*m")
    print(f"  dr={LR/NR*1e3:.2f} mm, dz={LZ/NZ*1e3:.2f} mm, "
          f"d_i(n0)={plasma_quantities()['d_i']*1e3:.1f} mm")
