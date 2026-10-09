#!/usr/bin/env python3
"""Bootstrap a private build environment and invoke build_itch.py.

The only system prerequisite is Python >=3.10 with venv/ensurepip available.
Does not install packages into a system Python/Conda environment.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".venv-build"
REQUIREMENTS = ROOT / "requirements-build.txt"
ENV_PYTHON = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command: list[str], *, label: str) -> None:
    print(f"[build] {label}", flush=True)
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Cannot run {command[0]!r}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{label} failed (exit code {exc.returncode}).") from exc


def expected_versions() -> dict[str, str]:
    """Parse our deliberately small, pinned build requirements file."""
    if not REQUIREMENTS.is_file():
        raise RuntimeError(f"Missing {REQUIREMENTS.name}; copy all build files together.")
    expected = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([\w-]+)==([\w.]+)", line)
        if not match:
            raise RuntimeError(f"Unsupported build requirement: {line!r} (use package==version)")
        expected[match.group(1).lower()] = match.group(2)
    if not {"pygbag", "pygame-ce"}.issubset(expected):
        raise RuntimeError("requirements-build.txt must pin pygbag and pygame-ce.")
    return expected


def installed_versions(python: Path, names: list[str]) -> dict[str, str]:
    """Ask the venv's own interpreter, without importing native pygame modules."""
    code = """import importlib.metadata as metadata
import json
import sys
versions = {}
for name in sys.argv[1:]:
    try:
        versions[name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        versions[name] = None
print(json.dumps(versions))
"""
    result = subprocess.run(
        [str(python), "-c", code, *names],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    import json
    return json.loads(result.stdout)


def ensure_environment(*, recreate: bool = False) -> Path:
    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"Python >=3.10 is required (found {sys.version.split()[0]}). "
            "Install a newer Python, or select one using the PYTHON environment variable."
        )

    expected = expected_versions()
    if recreate and ENV.exists():
        print("[build] Deleting previous isolated build environment.", flush=True)
        shutil.rmtree(ENV)

    if not ENV_PYTHON.is_file():
        if ENV.exists():
            raise RuntimeError(
                f"{ENV} exists but has no Python executable. Delete that folder "
                "or rerun with --recreate-env."
            )
        run([sys.executable, "-m", "venv", str(ENV)], label="Creating .venv-build virtual environment")
    if not ENV_PYTHON.is_file():
        raise RuntimeError(
            "The venv was not created correctly. On Debian/Ubuntu, install "
            "python3-venv and python3-pip, then use --recreate-env."
        )

    try:
        installed = installed_versions(ENV_PYTHON, list(expected))
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise RuntimeError(
            "Existing build environment is unusable. Rerun with --recreate-env."
        ) from exc
    mismatched = {
        name: (installed.get(name), wanted)
        for name, wanted in expected.items() if installed.get(name) != wanted
    }
    if mismatched:
        print("[build] Installing/updating missing or mismatched build dependencies:", flush=True)
        for name, (found, wanted) in mismatched.items():
            print(f"  {name}: {found or 'not installed'} -> {wanted}", flush=True)
        run(
            [str(ENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
            label="Installing Pygbag and pygame-ce (internet required on first run)",
        )
        installed = installed_versions(ENV_PYTHON, list(expected))
        if any(installed.get(name) != wanted for name, wanted in expected.items()):
            raise RuntimeError("Build dependencies are still mismatched after pip install.")
    else:
        print("[build] Reusing existing .venv-build; dependencies are already installed.", flush=True)
    return ENV_PYTHON


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build WasteGame, creating a private Python environment automatically."
    )
    parser.add_argument("--recreate-env", action="store_true", help="Recreate the local build environment")
    parser.add_argument("--skip-build", action="store_true", help="Patch/ZIP existing WasteGame/build/web without rebuilding")
    args = parser.parse_args()

    if not (ROOT / "build_itch.py").is_file():
        parser.error("build_itch.py is missing; keep scripts together")
    if not (ROOT / "WasteGame" / "main.py").is_file():
        parser.error("WasteGame/main.py was not found. Keep the scripts beside WasteGame/.")
    try:
        python = ensure_environment(recreate=args.recreate_env)
        command = [str(python), str(ROOT / "build_itch.py")]
        if args.skip_build:
            command.append("--skip-build")
        run(command, label="Building and packaging WasteGame")
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        print(
            "If dependencies cannot be downloaded, check internet access. "
            "If your Python lacks venv support, install python3-venv "
            "(Linux) or reinstall Python with pip (Windows).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
