"""Validate, snapshot, and run a configuration in a new output directory."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from yingguang_frc.config import apply, load
from yingguang_frc.model import parameters as P


def now():
    return datetime.now(timezone.utc).isoformat()


def git_output(root, *args):
    try:
        return subprocess.check_output(["git", "-C", str(root), *args],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare(config_path, output, steps=None):
    """Reserve a new directory and snapshot the exact Python worker source."""
    config_path = Path(config_path).resolve()
    cfg = load(config_path)
    resolved = apply(cfg)
    q = P.plasma_quantities()
    package = Path(__file__).resolve().parent
    output = Path(output).resolve()
    if output.is_relative_to(package):
        raise ValueError("Run outputs must be outside the installed source package")
    if steps is not None and (type(steps) is not int or steps <= 0):
        raise ValueError("steps must be a positive integer")
    # Never reuse even an empty directory: a typo must not overwrite a run.
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(config_path, output / "config.toml")
    snapshot = output / "source" / "yingguang_frc"
    for source in package.rglob("*.py"):
        target = snapshot / source.relative_to(package)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    root = package.parents[1]
    versions = {}
    for name in ("numpy", "scipy", "h5py", "matplotlib", "pywarpx", "picmistandard"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    command = [sys.executable, "-m", "yingguang_frc.model.simulation",
               "--config", "config.toml"]
    if steps is not None:
        command += ["--steps", str(steps)]
    manifest = {
        "schema_version": 1, "name": cfg["name"], "status": "prepared",
        "created_utc": now(), "configuration": cfg,
        "resolved_parameters": resolved, "dt_s": q["dt"],
        "requested_steps": steps if steps is not None else q["n_steps"],
        "short_run": steps is not None,
        "source_revision": git_output(root, "rev-parse", "HEAD"),
        "source_worktree_status": git_output(root, "status", "--porcelain"),
        "python": sys.version, "platform": platform.platform(),
        "dependencies": versions, "command": command,
        "random_seed": cfg["execution"]["random_seed"],
        "reproducibility": "GPU execution is not guaranteed bitwise deterministic.",
        "source_sha256": {str(f.relative_to(output)): digest(f)
                          for f in sorted(snapshot.rglob("*.py"))},
        "config_sha256": digest(output / "config.toml"),
    }
    write_manifest(output, manifest)
    return output, manifest


def write_manifest(output, manifest):
    path = output / "manifest.json"
    temporary = output / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--steps", type=int, help="Short verification run; overrides duration")
    ap.add_argument("--dry-run", action="store_true", help="Validate and print; write nothing")
    args = ap.parse_args()
    if args.steps is not None and args.steps <= 0:
        ap.error("--steps must be positive")
    try:
        cfg = load(args.config)
        apply(cfg)
        q = P.plasma_quantities()
        if args.output.exists():
            raise ValueError(f"Output already exists: {args.output}; choose a new directory")
        if args.dry_run:
            print(json.dumps({"configuration": cfg, "dt_s": q["dt"],
                              "steps": args.steps or q["n_steps"],
                              "output": str(args.output.resolve())}, indent=2))
            return
        if importlib.util.find_spec("pywarpx") is None:
            raise ValueError("pywarpx is not installed; see docs/installation.md")
        output, manifest = prepare(args.config, args.output, args.steps)
    except (OSError, ValueError) as error:
        ap.error(str(error))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(output / "source")
    env["PYTHONUNBUFFERED"] = "1"
    manifest.update(status="running", started_utc=now())
    write_manifest(output, manifest)
    print(f"Running {cfg['name']}; log: {output / 'run.log'}", flush=True)
    returncode = 1
    try:
        with (output / "run.log").open("x") as log:
            child = subprocess.Popen(manifest["command"], cwd=output, env=env,
                                     stdout=log, stderr=subprocess.STDOUT)
            try:
                returncode = child.wait()
            except KeyboardInterrupt:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                returncode = 130
    finally:
        manifest.update(status=("completed" if returncode == 0 else
                                "interrupted" if returncode == 130 else "failed"),
                        returncode=returncode, finished_utc=now())
        manifest["outputs"] = [
            {"path": str(f.relative_to(output)), "bytes": f.stat().st_size,
             "sha256": digest(f)}
            for f in sorted(output.rglob("*")) if f.is_file()
            and "source" not in f.relative_to(output).parts
            and f.name not in ("manifest.json", "manifest.json.tmp")]
        write_manifest(output, manifest)
    print(f"{manifest['status']}: {output}")
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
