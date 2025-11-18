"""Bulk regeneration helpers for Authority Site Engine."""
from __future__ import annotations

from pathlib import Path

from ..core.models import ProjectData
from .affiliate import AffiliateLinkEngine
from .blueprint import TopicalBlueprintGenerator
from .category_menu import CategoryMenuBuilder
from .internal_linking import InternalLinkingEngine
from .schema import SchemaEngine


class BulkRegenerator:
    """Expose consistent rebuild hooks for key modules."""

    def __init__(self, project_data: ProjectData, project_root: Path) -> None:
        self.project_data = project_data
        self.project_root = project_root

    def rebuild_internal_links(self, *, mode: str = "full", dry_run: bool = False) -> None:
        engine = InternalLinkingEngine(self.project_data, self.project_root)
        if mode == "full":
            engine.link_map_path.unlink(missing_ok=True)
        engine.run(dry_run=dry_run, partial=(mode == "missing"))

    def rebuild_schema(self, *, mode: str = "full") -> None:
        engine = SchemaEngine(self.project_data, self.project_root)
        if mode == "full":
            engine.schema_map_path.unlink(missing_ok=True)
        engine.run(partial=(mode == "missing"))

    def rebuild_affiliate_ctas(self, *, mode: str = "full") -> None:
        engine = AffiliateLinkEngine(self.project_data, self.project_root)
        if mode == "full":
            engine.cta_map_path.unlink(missing_ok=True)
        engine.run(partial=(mode == "missing"))

    def rebuild_categories(self) -> None:
        builder = CategoryMenuBuilder(self.project_data, self.project_root)
        builder.run()

    def rebuild_blueprint(self) -> None:
        generator = TopicalBlueprintGenerator(self.project_data, self.project_root)
        generator.generate()


__all__ = ["BulkRegenerator"]
