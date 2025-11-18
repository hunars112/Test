"""Create a Windows installer for Authority Site Engine using Inno Setup."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from authority_site_engine.core.version import ENGINE_VERSION

ROOT = Path(__file__).parent.resolve()
PACKAGING_DIR = ROOT / "packaging"
INSTALLER_DIR = ROOT / "installer"
DIST_DIR = ROOT / "dist" / "AuthoritySiteEngine"
TEMPLATE_PATH = PACKAGING_DIR / "AuthoritySiteEngine.iss"
GENERATED_PATH = PACKAGING_DIR / "AuthoritySiteEngine.generated.iss"
DEFAULT_ISCC_PATHS = [
    Path(r"C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"),
    Path(r"C:\\Program Files\\Inno Setup 6\\ISCC.exe"),
]


def _run(cmd: list[str]) -> None:
    print("Executing:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _ensure_dist() -> None:
    if not DIST_DIR.exists():
        print("Executable build not found. Running build_exe.py first...")
        _run([sys.executable, "build_exe.py"])


def _render_template(version: str) -> Path:
    if not TEMPLATE_PATH.exists():
        raise SystemExit("Missing installer template at packaging/AuthoritySiteEngine.iss")
    dist_path = DIST_DIR.resolve()
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    content = content.replace("{{VERSION}}", version)
    content = content.replace("{{DIST_DIR}}", str(dist_path).replace("\\", "\\\\"))
    GENERATED_PATH.write_text(content, encoding="utf-8")
    return GENERATED_PATH


def _find_iscc() -> Path | None:
    env_path = os.environ.get("ISCC_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
    for candidate in DEFAULT_ISCC_PATHS:
        if candidate.exists():
            return candidate
    return None


def build_installer() -> None:
    _ensure_dist()
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    generated_script = _render_template(ENGINE_VERSION)
    iscc_path = _find_iscc()
    if not iscc_path:
        print("Inno Setup compiler not found. Install Inno Setup and set ISCC_PATH env var.")
        print(f"Generated script available at {generated_script}.")
        return
    _run([str(iscc_path), str(generated_script)])
    print("Installer compilation finished. Check the installer/ directory for output.")


if __name__ == "__main__":
    build_installer()
