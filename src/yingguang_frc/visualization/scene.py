"""RZ-to-Cartesian field resampling and device geometry.

The device axis is Cartesian X, and scene coordinates are centimeters.
The m=0 model can have nonzero Btheta: the Cartesian field is
(Bz, Br*y/r - Btheta*z/r, Br*z/r + Btheta*y/r).
ImageData enables VTK ray-cast volume rendering without mesh tessellation.
Rendering policy, smoothing, transfer functions, and caching live in rendering.py.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from scipy.ndimage import map_coordinates

from yingguang_frc.model import parameters as P

CM = 100.0


class Resampler:
    """Resample RZ (nr, nz) onto a Cartesian grid with the axis along X (cm)."""

    def __init__(self, frame: dict, nx: int, nyz: int):
        r, z = frame["r"], frame["z"]
        wall = frame["r_edges"][-1]
        x = np.linspace(frame["z_edges"][0], frame["z_edges"][-1], nx) * CM
        yz = np.linspace(-wall, wall, nyz) * CM
        self.grid = pv.ImageData(
            dimensions=(nx, nyz, nyz),
            spacing=(x[1] - x[0], yz[1] - yz[0], yz[1] - yz[0]),
            origin=(x[0], yz[0], yz[0]))
        X, Y, Z = np.meshgrid(x, yz, yz, indexing="ij")
        RHO = np.sqrt(Y ** 2 + Z ** 2)
        self.outside = RHO > wall * CM
        rho_safe = np.maximum(RHO, 1e-9)
        self.uy = Y / rho_safe
        self.uz = Z / rho_safe
        ir = (RHO / CM - r[0]) / (r[1] - r[0])
        iz = (X / CM - z[0]) / (z[1] - z[0])
        self.coords = np.stack([ir.ravel(), iz.ravel()])
        self.shape = X.shape

    def scalar(self, f2d: np.ndarray) -> np.ndarray:
        out = map_coordinates(f2d, self.coords, order=1, mode="nearest")
        return out.reshape(self.shape)

    def density(self, fr: dict) -> np.ndarray:
        """Resampled ion density, zero outside the cylindrical domain."""
        n3 = self.scalar(fr["rho"] / P.QE)
        n3[self.outside] = 0.0
        return n3

    def fill(self, fr: dict, density: bool = True) -> None:
        """Populate magnetic fields and, optionally, ion density on the grid."""
        if density:
            self.grid["n_i"] = self.density(fr) \
                .astype(np.float32).ravel(order="F")
        bax = self.scalar(fr["Bz"])
        brad = self.scalar(fr["Br"])
        btheta = self.scalar(fr["Bt"]) if "Bt" in fr else 0.0
        bx = bax
        by = brad * self.uy - btheta * self.uz
        bz = brad * self.uz + btheta * self.uy
        for b in (bx, by, bz):
            b[self.outside] = 0.0
        g = self.grid
        g["Bmag"] = np.sqrt(bx ** 2 + by ** 2 + bz ** 2) \
            .astype(np.float32).ravel(order="F")
        g["B"] = np.column_stack(
            [b.astype(np.float32).ravel(order="F") for b in (bx, by, bz)])
        # Axial field for the Bz=0 contour. Mask outside the cylindrical
        # domain to avoid an artificial zero contour along the wall.
        bz_sep = bax.copy()
        bz_sep[self.outside] = np.nan
        g["Bz_sep"] = bz_sep.astype(np.float32).ravel(order="F")
        g.set_active_vectors("B")



def zero_axial_field(grid):
    """Bz=0 isosurface; this is not a magnetic separatrix calculation."""
    return grid.contour(isosurfaces=[0.0], scalars="Bz_sep")


def add_geometry(plotter: pv.Plotter, opacity=.13):
    """Stylized translucent theta-coil bands and mirror coils."""
    actors = []
    def band(xc, radius, height):
        cyl = pv.Cylinder(center=(xc, 0, 0), direction=(1, 0, 0),
                          radius=radius, height=height,
                          resolution=160, capping=False)
        actors.append(plotter.add_mesh(cyl, color="#aebccc", opacity=opacity,
                         smooth_shading=True, show_scalar_bar=False,
                         ambient=.25, diffuse=.65, specular=.45, specular_power=30,
                         reset_camera=False, render=False))

    for xc in np.linspace(-(P.L_COIL / 2 - 0.02),
                          P.L_COIL / 2 - 0.02, P.N_BANDS) * CM:
        band(xc, P.R_COIL * CM, 2.8)
    for sgn in (-1, 1):
        band(sgn * P.Z_MIRROR * CM, P.R_MIRROR * CM, 9.0)
    return actors
