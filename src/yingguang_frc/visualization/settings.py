"""Portable render settings shared by the interactive viewer and exports."""
from dataclasses import asdict, dataclass, fields
import json
import math
from pathlib import Path


QUALITY = {
    "interactive": (176, 64),
    "high": (352, 128),
    "ultra": (528, 192),
}
CAMERAS = {
    "presentation": ((-22., -105., 32.), (0., 0., 0.), (0., 0., 1.)),
    "side": ((0., -110., 0.), (0., 0., 0.), (0., 0., 1.)),
    "end": ((-110., 0., 0.), (0., 0., 0.), (0., 0., 1.)),
}


@dataclass
class RenderSettings:
    schema_version: int = 1
    density_max: float = 3.5e22
    magnetic_max: float = 2.2
    opacity: float = .32
    density_cutoff: float = .06
    opacity_gamma: float = 1.4
    smoothing_r_cm: float = .08
    smoothing_z_cm: float = .3
    density_cmap: str = "turbo"
    field_cmap: str = "turbo"
    line_opacity: float = .35
    line_width: float = 1.0
    line_density: int = 3
    geometry_opacity: float = .13
    show_lines: bool = True
    show_geometry: bool = True
    show_zero_field: bool = False
    auto_exposure: bool = False
    shade: bool = False
    camera: str = "presentation"
    camera_position: list | None = None
    parallel_scale: float = 17.0
    time_us: float = 0.0
    quality: str = "interactive"
    fps: float = 8.0

    def validate(self):
        if self.schema_version != 1:
            raise ValueError("Unsupported render settings version")
        for name in ("density_max", "magnetic_max", "opacity_gamma", "line_width",
                     "parallel_scale", "fps"):
            v = getattr(self, name)
            if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("opacity", "density_cutoff", "line_opacity", "geometry_opacity"):
            v = getattr(self, name)
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.density_cutoff >= 1:
            raise ValueError("density_cutoff must be less than 1")
        for name in ("smoothing_r_cm", "smoothing_z_cm", "time_us"):
            v = getattr(self, name)
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if type(self.line_density) is not int or not 1 <= self.line_density <= 8:
            raise ValueError("line_density must be an integer from 1 to 8")
        for name in ("show_lines", "show_geometry", "show_zero_field", "auto_exposure", "shade"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if (not isinstance(self.quality, str) or self.quality not in QUALITY
                or not isinstance(self.camera, str) or self.camera not in CAMERAS):
            raise ValueError("Unknown quality or camera preset")
        for name in ("density_cmap", "field_cmap"):
            if getattr(self, name) not in ("turbo", "jet", "inferno", "viridis", "magma"):
                raise ValueError(f"Unsupported colormap: {getattr(self, name)}")
        if self.camera_position is not None:
            c = self.camera_position
            if (not isinstance(c, (list, tuple)) or len(c) != 3
                    or any(not isinstance(v, (list, tuple)) or len(v) != 3 for v in c)):
                raise ValueError("camera_position must contain position, focal point, and up vector")
            if any(type(v) not in (float, int) or not math.isfinite(v) for row in c for v in row):
                raise ValueError("camera_position must be finite")
            direction = [c[1][i] - c[0][i] for i in range(3)]
            cross = [direction[1]*c[2][2] - direction[2]*c[2][1],
                     direction[2]*c[2][0] - direction[0]*c[2][2],
                     direction[0]*c[2][1] - direction[1]*c[2][0]]
            if sum(v*v for v in cross) < 1e-16:
                raise ValueError("Camera direction and up vector must be independent")
        return self

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError("Render settings must be a JSON object")
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown render settings: {sorted(unknown)}")
        return cls(**data).validate()

    def save(self, path):
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
