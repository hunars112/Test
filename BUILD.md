# Authority Site Engine Build & Packaging Guide

This document explains how to run the desktop app from source, execute the
regression suite, build the standalone executable, and compile the Windows
installer defined in Part 14.

## Prerequisites

* Python 3.10+
* Git
* (Optional) Inno Setup 6 for generating the installer (`ISCC.exe`)

## Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r dev-requirements.txt
```

## Run tests

```bash
pytest
```

## Launch the app from source

```bash
python app_main.py
```

On first launch the app stores configuration, projects, logs, and credentials
under the OS-specific data directory (for Windows this is
`%APPDATA%\AuthoritySiteEngine`). A welcome dialog lets you override the base
path and HTTP timeout defaults.

## Build the executable

`build_exe.py` bundles the GUI via PyInstaller. It creates a dedicated virtual
environment, installs the runtime dependencies, injects version metadata based on
`authority_site_engine.core.version.ENGINE_VERSION`, and produces a one-folder
build under `dist/AuthoritySiteEngine/`. If you want a custom icon, place
`icon.ico` inside `assets/` before running the build; otherwise the default
PyInstaller icon is used.

```bash
python build_exe.py
```

## Build the installer

The installer consumes the output in `dist/AuthoritySiteEngine/`.
`build_installer.py` renders `packaging/AuthoritySiteEngine.iss` with the current
version and dist paths, then invokes the Inno Setup compiler. If `ISCC.exe`
cannot be found automatically, set the `ISCC_PATH` environment variable to the
compiler executable and rerun the command.

```bash
python build_installer.py
```

The resulting `AuthoritySiteEngineSetup.exe` is written to the ignored
`installer/` folder. The installer writes binaries to `Program Files`, adds
optional Start Menu/Desktop shortcuts, and preserves user data in
`%APPDATA%\AuthoritySiteEngine` unless the user chooses to remove it during
uninstall.
