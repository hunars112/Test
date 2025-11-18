"""Simple extension/plug-in loader for Authority Site Engine."""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List


class Extension:
    """Base class that extensions can inherit for optional hooks."""

    name = "anonymous"
    version = "1.0"

    def on_project_load(self, **kwargs) -> None:  # pragma: no cover - hook
        ...

    def on_posting_completed(self, **kwargs) -> None:  # pragma: no cover - hook
        ...

    def on_linking_completed(self, **kwargs) -> None:  # pragma: no cover - hook
        ...

    def on_daily_automation(self, **kwargs) -> None:  # pragma: no cover - hook
        ...


class ExtensionManager:
    """Discover and execute lightweight extension hooks."""

    def __init__(self, extensions_dir: Path) -> None:
        self.extensions_dir = extensions_dir
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        self._extensions: List[Extension] = []
        self._load_extensions()

    def _load_extensions(self) -> None:
        for path in self.extensions_dir.glob("*.py"):
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[misc]
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Extension) and obj is not Extension:
                    try:
                        self._extensions.append(obj())
                    except Exception:
                        continue

    def emit(self, hook: str, **kwargs) -> None:
        for extension in self._extensions:
            func: Callable[..., Any] | None = getattr(extension, hook, None)
            if not func:
                continue
            try:
                func(**kwargs)
            except Exception:
                continue


_extension_manager: ExtensionManager | None = None


def get_extension_manager(base_dir: Path | None = None) -> ExtensionManager:
    global _extension_manager
    if _extension_manager is None:
        base = base_dir or Path.cwd()
        _extension_manager = ExtensionManager(base / "extensions")
    return _extension_manager


__all__ = ["Extension", "ExtensionManager", "get_extension_manager"]
