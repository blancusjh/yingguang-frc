"""Shared scene, bounded render cache, and physical-time frame interpolation."""
from collections import OrderedDict
from dataclasses import asdict
import json
import hashlib
from pathlib import Path
import platform

import numpy as np
import pyvista as pv
from scipy.ndimage import gaussian_filter

from yingguang_frc.visualization.scene import Resampler, add_geometry, zero_axial_field
from yingguang_frc.visualization.settings import CAMERAS, QUALITY


def transfer_function(settings):
    x = np.linspace(0, 1, 256)
    x = np.clip((x - settings.density_cutoff) / (1 - settings.density_cutoff), 0, 1)
    # A full 256-entry PyVista lookup table uses byte opacity (0..255).
    return np.round(255 * settings.opacity * x ** settings.opacity_gamma).astype(np.uint8)


def frame_at_time(frames, time_us):
    """Interpolate fields for display only; never change the source frames."""
    times = np.asarray([f["t"] * 1e6 for f in frames])
    if not np.isfinite(time_us) or time_us < times[0] - 1e-6 or time_us > times[-1] + 1e-6:
        raise ValueError(f"Time must be between {times[0]:g} and {times[-1]:g} µs")
    k = int(np.searchsorted(times, time_us))
    if k == 0:
        return frames[0]
    if k == len(frames):
        return frames[-1]
    if np.isclose(times[k], time_us, atol=1e-10, rtol=0):
        return frames[k]
    a, b = frames[k-1], frames[k]
    fraction = (time_us - times[k-1]) / (times[k] - times[k-1])
    result = dict(a, t=time_us*1e-6)
    for key in ("rho", "Br", "Bz", "Bt"):
        result[key] = a[key]*(1-fraction) + b[key]*fraction
    return result


def select_frames(frames, stride):
    if stride < 1:
        raise ValueError("stride must be positive")
    selected = frames[::stride]
    if selected[-1] is not frames[-1]:
        selected.append(frames[-1])
    return selected


def seeds(density):
    # Sparse, repeatable meridional seeds reveal the core without a dense curtain
    # of open field lines covering the volume. Btheta remains in the integration.
    points = []
    phis = np.linspace(0, 2*np.pi, 4, endpoint=False)
    for phi in phis:
        for r in np.linspace(.7, 2.6, density + 1):
            points.append((0, r*np.cos(phi), r*np.sin(phi)))
        for z in (-15., 15.):
            points.append((z, 1.4*np.cos(phi), 1.4*np.sin(phi)))
        points.append((0, 4.1*np.cos(phi), 4.1*np.sin(phi)))
    return pv.PolyData(np.asarray(points))


class PlasmaScene:
    """Own the actors in one renderer; share this class between viewer/export."""
    def __init__(self, plotter, first_frame, settings, dimensions=None):
        self.p = plotter
        self.settings = settings.validate()
        self.dimensions = dimensions or QUALITY[settings.quality]
        self.rs = Resampler(first_frame, *self.dimensions)
        self.cache = OrderedDict()
        self.cache_limit = 4
        self.cache_bytes_limit = 192 * 1024**2
        self.last_time = None
        self.p.set_background("#03070c", all_renderers=False)
        # VTK's SSAA render pass drops volumes on some EGL/OSMesa backends.
        # MSAA smooths geometry without replacing the volume-rendering pass.
        self.p.enable_anti_aliasing("msaa", multi_samples=8, all_renderers=False)
        self.geometry = add_geometry(self.p, opacity=settings.geometry_opacity)
        self.density_scale = settings.density_max
        self.apply_camera()
        self.p.add_text("YINGGUANG-I", position=(.035, .94), viewport=True,
                        font_size=15, font="arial", color="#ecf5ff", name="title")
        self.p.add_text("Axisymmetric hybrid-PIC  /  ion density + magnetic field",
                        position=(.035, .9), viewport=True, font_size=9,
                        color="#91a6bb", name="subtitle")
        self.clock = self.p.add_text("", position=(.035, .83), viewport=True,
                                     font_size=12, color="#ecf5ff", name="clock")

    def apply_camera(self):
        s = self.settings
        self.p.camera_position = s.camera_position or CAMERAS[s.camera]
        self.p.enable_parallel_projection()
        self.p.camera.parallel_scale = s.parallel_scale * 2.4 / self.aspect()
        self.p.reset_camera_clipping_range()

    def capture_camera(self):
        self.settings.camera_position = [list(v) for v in self.p.camera_position]
        self.settings.parallel_scale = float(self.p.camera.parallel_scale) * self.aspect() / 2.4

    def aspect(self):
        x0,y0,x1,y1=self.p.renderer.viewport
        width,height=self.p.window_size
        return (x1-x0)*width/((y1-y0)*height)

    def _processed(self, frame):
        s = self.settings
        key = (float(frame["t"]), s.smoothing_r_cm, s.smoothing_z_cm, s.line_density,
               s.show_lines, s.show_zero_field)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        processed = dict(frame)
        sigma = [s.smoothing_r_cm / (np.diff(frame["r_edges"])[0]*100),
                 s.smoothing_z_cm / (np.diff(frame["z_edges"])[0]*100)]
        processed["rho"] = gaussian_filter(frame["rho"], sigma) if any(sigma) else frame["rho"]
        # Density stays in SI; changing a color scale never changes the data.
        self.rs.fill(processed, density=True)
        density = np.array(self.rs.grid["n_i"], copy=True)
        lines = None
        if s.show_lines:
            lines = self.rs.grid.streamlines_from_source(
                seeds(s.line_density), vectors="B", integration_direction="both",
                max_length=160., max_steps=2000, initial_step_length=.15,
                terminal_speed=1e-5)
        surface = zero_axial_field(self.rs.grid) if s.show_zero_field else None
        item = (density, lines, surface)
        self.cache[key] = item
        def memory():
            return sum(v[0].nbytes + sum(m.GetActualMemorySize()*1024 for m in v[1:] if m is not None)
                       for v in self.cache.values())
        while len(self.cache) > 1 and (len(self.cache) > self.cache_limit or memory() > self.cache_bytes_limit):
            self.cache.popitem(last=False)
        return item

    def draw(self, frame, render=True):
        s = self.settings
        density, lines, surface = self._processed(frame)
        self.rs.grid["n_i"] = density
        # Auto exposure is explicitly opt-in; fixed scales are the default.
        self.density_scale = max(float(np.quantile(density, .997)), s.density_max*.1) if s.auto_exposure else s.density_max
        # Normalize only the display array. Raw density and colorbar stay in SI.
        self.rs.grid["density_display"] = np.clip(density/self.density_scale,0,1)
        self.p.remove_actor("density", render=False)
        for title in ("Ion density (m^-3)", "|B| (T)"):
            if title in self.p.scalar_bars:
                self.p.remove_scalar_bar(title, render=False)
        bar = dict(title="Ion density (m^-3)", vertical=False, position_x=.22,
                   position_y=.055, width=.5, height=.055, n_labels=4,
                   fmt="%.1e", color="#cdd9e6", title_font_size=13, label_font_size=10)
        actor = self.p.add_volume(self.rs.grid, scalars="density_display", name="density",
                                 cmap=s.density_cmap, clim=(0, 1),
                                 opacity=transfer_function(s), opacity_unit_distance=1.0,
                                 shade=s.shade, ambient=.45, diffuse=.55, specular=.12,
                                 blending="composite",
                                 show_scalar_bar=False, reset_camera=False, render=False)
        color_mapper=pv.DataSetMapper()
        color_mapper.lookup_table=pv.LookupTable(cmap=s.density_cmap,scalar_range=(0,self.density_scale))
        color_mapper.scalar_range=(0,self.density_scale)
        self.p.add_scalar_bar(mapper=color_mapper,**bar,render=False)
        actor.prop.interpolation_type = "linear"
        mapper = actor.mapper
        if hasattr(mapper, "SetAutoAdjustSampleDistances"):
            mapper.SetAutoAdjustSampleDistances(s.quality == "interactive")
            mapper.SetSampleDistance(min(self.rs.grid.spacing)*.5)
        self.p.remove_actor("lines", render=False)
        if s.show_lines and lines is not None and lines.n_points:
            self.p.add_mesh(lines, name="lines", scalars="Bmag", cmap=s.field_cmap,
                            clim=(0, s.magnetic_max), opacity=s.line_opacity,
                            line_width=s.line_width, render_lines_as_tubes=True,
                            lighting=False, reset_camera=False, render=False,
                            scalar_bar_args=dict(title="|B| (T)", vertical=True,
                                                 position_x=.92, position_y=.27,
                                                 width=.035, height=.35, n_labels=4,
                                                 color="#cdd9e6", title_font_size=12,
                                                 label_font_size=10, fmt="%.1f"))
        self.p.remove_actor("zero-field", render=False)
        if s.show_zero_field and surface is not None and surface.n_points:
            self.p.add_mesh(surface, name="zero-field", color="#87d2f3", opacity=.12,
                            smooth_shading=True, show_scalar_bar=False,
                            reset_camera=False, render=False)
        for actor in self.geometry:
            actor.visibility = s.show_geometry
            actor.prop.opacity = s.geometry_opacity
        self.last_time = float(frame["t"]*1e6)
        s.time_us = self.last_time
        mode = "  |  adaptive density scale" if s.auto_exposure else ""
        self.clock.input = f"t = {self.last_time:6.3f} µs{mode}"
        self.p.reset_camera_clipping_range()
        if render:
            self.p.render()

    def save_metadata(self, path, run_dir, extra=None):
        self.capture_camera()
        source_dir = Path(__file__).parent
        data = {"settings": asdict(self.settings), "run": str(Path(run_dir).resolve()),
                "time_us": self.last_time, "density_scale_m_minus_3": self.density_scale,
                "resampling_shape": self.dimensions, "interpolation": "linear for display only",
                "environment": {"python": platform.python_version(), "pyvista": pv.__version__,
                                "vtk": str(pv.vtk_version_info), "numpy": np.__version__},
                "source_sha256": {name: hashlib.sha256((source_dir/name).read_bytes()).hexdigest()
                                  for name in ("rendering.py", "scene.py", "settings.py", "animate.py")}}
        if extra:
            data.update(extra)
        Path(path).write_text(json.dumps(data, indent=2) + "\n")
