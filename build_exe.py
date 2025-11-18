"""Build a Windows-ready Authority Site Engine executable via PyInstaller."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from authority_site_engine.core.version import ENGINE_VERSION

ROOT = Path(__file__).parent.resolve()
VENV_DIR = ROOT / ".venv-build"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ENTRY_SCRIPT = ROOT / "app_main.py"
ICON_PATH = ROOT / "assets" / "icon.ico"
RUNTIME_DEFAULTS = ROOT / "runtime_defaults"


def _run(cmd: list[str], **kwargs) -> None:
    print("Executing:", " ".join(cmd))
    subprocess.run(cmd, check=True, **kwargs)


def _venv_python() -> Path:
    if not VENV_DIR.exists():
        _run([sys.executable, "-m", "venv", str(VENV_DIR)])
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    python_path = VENV_DIR / bin_dir / ("python.exe" if os.name == "nt" else "python")
    pip_path = VENV_DIR / bin_dir / ("pip.exe" if os.name == "nt" else "pip")
    _run([str(pip_path), "install", "--upgrade", "pip"])
    _run([str(pip_path), "install", "-r", "requirements.txt", "pyinstaller"])
    return python_path


def _write_version_file(version: str) -> Path:
    major, minor, patch, *_ = (version.split(".") + ["0", "0", "0"])
    template = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Authority Site Engine'),
        StringStruct('FileDescription', 'Authority Site Engine - SEO and affiliate automation'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'AuthoritySiteEngine'),
        StringStruct('OriginalFilename', 'AuthoritySiteEngine.exe'),
        StringStruct('ProductName', 'Authority Site Engine'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    version_file = BUILD_DIR / "version_info.txt"
    version_file.write_text(template, encoding="utf-8")
    return version_file


def build() -> None:
    if not ENTRY_SCRIPT.exists():
        raise SystemExit("Entry script app_main.py is missing")
    python_path = _venv_python()
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    version_file = _write_version_file(ENGINE_VERSION)
    data_spec = f"{RUNTIME_DEFAULTS}{os.pathsep}runtime_defaults"
    cmd = [
        str(python_path),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "AuthoritySiteEngine",
        "--version-file",
        str(version_file),
        "--add-data",
        data_spec,
    ]
    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])
    cmd.append(str(ENTRY_SCRIPT))
    _run(cmd, cwd=ROOT)
    print("Build completed. Check the dist/ directory for output.")


if __name__ == "__main__":
    build()
