"""High-quality image/video export using the same scene and settings as frc-view."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pyvista as pv

from yingguang_frc.analysis.openpmd import load_series
from yingguang_frc.visualization.rendering import PlasmaScene, frame_at_time, select_frames
from yingguang_frc.visualization.settings import RenderSettings, QUALITY


def render_image(frames, settings, run_dir, output, time_us=None, size=(1920, 800), dimensions=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Output exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = replace(settings)
    settings.validate()
    frame = frame_at_time(frames, settings.time_us if time_us is None else time_us)
    p = pv.Plotter(off_screen=True, window_size=size)
    try:
        scene = PlasmaScene(p, frames[0], settings, dimensions)
        scene.draw(frame)
        p.screenshot(str(output))
        scene.save_metadata(output.with_suffix(".metadata.json"), run_dir,
                            {"size": list(size), "kind": "image"})
    finally:
        p.close()
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--settings", type=Path)
    ap.add_argument("--quality", choices=QUALITY, default=None)
    ap.add_argument("--size", type=int, nargs=2, default=(1920, 800))
    ap.add_argument("--time-us", type=float, help="Export one PNG at this physical time")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--duration", type=float, help="Video seconds; interpolate fields for smooth playback")
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--n-max", type=float)
    ap.add_argument("--b-max", type=float)
    ap.add_argument("--opacity", type=float)
    ap.add_argument("--no-lines", action="store_true")
    ap.add_argument("--no-geometry", action="store_true")
    ap.add_argument("--sin-suavizado", "--no-smoothing", action="store_true")
    ap.add_argument("--sin-auto-exp", "--fixed-exposure", action="store_true")
    ap.add_argument("--nx", type=int, help="Optional axial render-grid samples")
    ap.add_argument("--nyz", type=int, help="Optional diameter render-grid samples")
    # Preserve snapshot indices for existing reproduction commands.
    ap.add_argument("--snap", help="Comma-separated indices in the selected output series")
    args = ap.parse_args()
    if args.fps <= 0 or args.stride <= 0 or min(args.size) < 64:
        ap.error("fps/stride must be positive and image dimensions at least 64")
    if args.duration is not None and (not np.isfinite(args.duration) or args.duration <= 0):
        ap.error("duration must be finite and positive")
    if (args.nx is None) != (args.nyz is None) or any(v is not None and v < 8 for v in (args.nx,args.nyz)):
        ap.error("Specify both --nx and --nyz, each at least 8")
    try:
        s = RenderSettings.load(args.settings) if args.settings else RenderSettings()
        s.quality = args.quality or ("high" if not args.settings else s.quality)
        for arg, name in ((args.n_max,"density_max"), (args.b_max,"magnetic_max"), (args.opacity,"opacity")):
            if arg is not None:
                setattr(s,name,arg)
        if args.no_lines:
            s.show_lines = False
        if args.no_geometry:
            s.show_geometry = False
        if args.sin_suavizado:
            s.smoothing_r_cm = s.smoothing_z_cm = 0.
        if args.sin_auto_exp:
            s.auto_exposure = False
        s.validate()
        frames = select_frames(load_series(args.run_dir), args.stride)
        dimensions = (args.nx, args.nyz) if args.nx is not None else None
        if args.snap:
            indices = [int(v) for v in args.snap.split(",")]
            if any(k < 0 or k >= len(frames) for k in indices):
                raise ValueError("Snapshot index outside available frames")
            for k in indices:
                target = args.out.with_name(f"{args.out.stem}_f{k:03d}.png")
                render_image(frames, s, args.run_dir, target, frames[k]["t"]*1e6, args.size, dimensions)
                print(target, flush=True)
            return
        if args.time_us is not None or args.out.suffix.lower() == ".png":
            if args.out.suffix.lower() != ".png":
                raise ValueError("Single-frame output must use .png")
            time_us = args.time_us if args.time_us is not None else s.time_us
            print(render_image(frames, s, args.run_dir, args.out, time_us, args.size, dimensions))
            return
        if args.out.suffix.lower() != ".mp4" or any(v % 2 for v in args.size):
            raise ValueError("Video output must be .mp4 with even dimensions")
        if args.out.exists():
            raise FileExistsError(f"Output exists: {args.out}")
        times = ([fr["t"]*1e6 for fr in frames] if args.duration is None else
                 np.linspace(frames[0]["t"]*1e6, frames[-1]["t"]*1e6,
                             max(2, round(args.fps*args.duration))).tolist())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        p = pv.Plotter(off_screen=True, window_size=args.size)
        dimensions = (args.nx, args.nyz) if args.nx is not None else None
        scene = PlasmaScene(p, frames[0], s, dimensions)
        writer = imageio_ffmpeg.write_frames(
            str(args.out), args.size, fps=args.fps, codec="libx264",
            quality=9, macro_block_size=1, pix_fmt_out="yuv420p")
        writer.send(None)
        try:
            for k,time_us in enumerate(times):
                scene.draw(frame_at_time(frames,time_us))
                writer.send(p.screenshot(return_img=True)[:,:,:3])
                print(f"Frame {k+1}/{len(times)} · t={time_us:.3f} µs",flush=True)
            scene.save_metadata(args.out.with_suffix(".metadata.json"), args.run_dir,
                                {"kind":"video","fps":args.fps,"size":list(args.size),
                                 "times_us":times,"temporal_interpolation":args.duration is not None})
        finally:
            writer.close()
            p.close()
    except (ValueError,OSError) as error:
        ap.error(str(error))


if __name__ == "__main__":
    main()
