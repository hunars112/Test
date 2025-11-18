"""Test helpers for building sample Authority Site Engine data."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Tuple

from authority_site_engine.core.models import (
    AffiliateLinkSet,
    AffiliateOffer,
    AutomationSettings,
    BasicSiteInfo,
    CategorySettings,
    CloudflareHostInfo,
    ContentStructureSettings,
    DeploymentSettings,
    HealthMonitoringSettings,
    LinkingRules,
    PostingPreferences,
    ProductLists,
    ProjectData,
    SchemaSettings,
    ZimmWriterSettings,
    ZimmWriterTemplate,
)
from authority_site_engine.core.project_manager import ProjectManager
from authority_site_engine.modules.blueprint import TopicalBlueprintGenerator


def build_sample_project(tmp_path: Path) -> ProjectData:
    manager = ProjectManager(base_directory=tmp_path)
    suggestions = manager.suggest_categories("test niche")
    return ProjectData(
        basic_info=BasicSiteInfo(
            project_name="Test Project",
            niche="Portable Heaters",
            domain_name="portableheat.example",
            wp_admin_url="https://portableheat.example/wp-admin",
            wp_username="admin",
            wp_password="password",
        ),
        cloudflare=CloudflareHostInfo(
            cloudflare_email="user@example.com",
            cloudflare_api_key="key",
            ssh_host="",
            ssh_username="",
            ssh_password="",
            dns_records=[
                {"type": "A", "name": "@", "content": "192.0.2.1", "proxied": True},
                {"type": "CNAME", "name": "www", "content": "portableheat.example", "proxied": True},
            ],
        ),
        content_structure=ContentStructureSettings(
            pillar_posts=4,
            supporting_posts_per_pillar=5,
            informational_posts=40,
            affiliate_product_posts=10,
            amazon_roundup_posts=5,
            custom_product_posts=3,
        ),
        categories=CategorySettings(suggestions=suggestions, categories=suggestions[:4]),
        product_lists=ProductLists(
            affiliate_products=["Heater A", "Heater B", "Heater C"],
            amazon_products=["HeatMax 2.0", "WarmCozy"],
            custom_products=["Garage Heater Kit"],
            notes="seasonal",
        ),
        affiliate_links=AffiliateLinkSet(
            cpa_links=["https://cpa.example/offer"],
            amazon_links=["https://amazon.example/product"],
            custom_links=["https://external.example"],
            geo_targeted={"US": "https://us.example"},
            backup_url="https://backup.example",
            offers=[
                AffiliateOffer(
                    offer_id="heater-a",
                    name="Heater A",
                    base_url="https://offers.example/heater-a",
                    network_type="CPA",
                    product_names=["Heater A"],
                    post_types=["affiliate_review", "amazon_roundup"],
                    categories=["Heating Basics"],
                    weight=70,
                ),
                AffiliateOffer(
                    offer_id="heater-b",
                    name="Heater B",
                    base_url="https://offers.example/heater-b",
                    network_type="CPA",
                    product_names=["Heater B"],
                    post_types=["affiliate_review", "info"],
                    weight=30,
                ),
            ],
            placeholder_post_types={
                "CTA_TOP": ["affiliate_review", "amazon_roundup"],
                "CTA_BOTTOM": ["affiliate_review", "amazon_roundup", "info"],
                "CTA_INLINE": ["info", "supporting"],
                "AFFILIATE_BOX": ["affiliate_review", "amazon_roundup"],
            },
            max_ctas_per_post=3,
            rotation_enabled=True,
            geo_redirector_url="https://redirect.example/go",
        ),
        posting_preferences=PostingPreferences(
            post_immediately=False,
            scheduling_interval_hours=12,
            drip_posting=True,
            publish_sequence=["pillar", "supporting", "affiliate", "informational"],
        ),
        zimmwriter=ZimmWriterSettings(
            templates=[
                ZimmWriterTemplate(name="Pillar", template_path="pillar.csv", description="pillars"),
                ZimmWriterTemplate(name="Supporting", template_path="support.csv", description="support"),
            ]
        ),
        linking_rules=LinkingRules(),
        schema=SchemaSettings(
            site_name="Authority Site Engine",
            site_url="https://portableheat.example",
            publisher_logo_url="https://portableheat.example/logo.png",
            default_author_name="Editorial Team",
            breadcrumb_enabled=True,
        ),
        deployment=DeploymentSettings(
            configure_cloudflare=True,
            install_theme=True,
            install_plugins=True,
            deploy_content=True,
            run_category_builder=True,
            run_internal_linking=True,
            run_affiliate=True,
            run_schema=True,
            ping_sitemaps=False,
            theme_slug="twentytwentythree",
            plugin_slugs=["classic-editor"],
            wp_cli_path="wp",
            site_title="Portable Heat HQ",
            admin_email="user@example.com",
            timezone="UTC",
            site_url="https://portableheat.example",
            wp_rest_username="admin",
            wp_app_password="app-password",
        ),
        health=HealthMonitoringSettings(
            enable_http_checks=True,
            http_sample_size=2,
            enable_ssl_check=True,
            enable_sitemap_check=True,
            enable_linking_check=True,
            enable_content_stats=True,
            enable_cloudflare_stats=False,
            http_timeout=10,
            cloudflare_hours=24,
        ),
        automation=AutomationSettings(),
    )


class FakeWordPressClient:
    """Simple test double for WordPress REST interactions."""

    def __init__(self) -> None:
        self._category_counter = 1
        self._tag_counter = 1
        self._menu_counter = 1
        self._menu_item_counter = 1
        self.categories = []
        self.tags = []
        self.created_posts = []
        self.updated_posts = []
        self.post_store: dict[int, dict[str, object]] = {}
        self.menus: list[dict[str, object]] = []
        self.menu_items: dict[int, list[dict[str, object]]] = {}
        self.settings_updates: list[dict[str, object]] = []
        self.deleted_posts: list[int] = []

    # Category helpers -------------------------------------------------
    def list_categories(self):
        return list(self.categories)

    def create_category(self, name: str):
        self._category_counter += 1
        category = {"id": self._category_counter, "name": name}
        self.categories.append(category)
        return category

    def ensure_category(self, name: str, slug: str | None = None):
        for category in self.categories:
            if category["name"].lower() == name.lower():
                return category["id"], False
        created = self.create_category(name)
        return created["id"], True

    # Tag helpers ------------------------------------------------------
    def list_tags(self):
        return list(self.tags)

    def create_tag(self, name: str):
        self._tag_counter += 1
        tag = {"id": self._tag_counter, "name": name}
        self.tags.append(tag)
        return tag

    def ensure_tag(self, name: str):
        for tag in self.tags:
            if tag["name"].lower() == name.lower():
                return tag["id"], False
        created = self.create_tag(name)
        return created["id"], True

    # Posts -------------------------------------------------------------
    def create_post(self, payload):
        post_id = len(self.post_store) + 1
        enriched_content = self._enrich_content(payload.get("content", ""))
        timestamp = datetime.utcnow().isoformat()
        record = {
            "id": post_id,
            "link": f"https://example.com/{post_id}",
            "categories": payload.get("categories", []),
            "tags": payload.get("tags", []),
            "payload": {**payload, "content": enriched_content},
        }
        self.post_store[post_id] = {
            "id": post_id,
            "link": record["link"],
            "content": enriched_content,
            "excerpt": enriched_content[:200],
            "date": timestamp,
            "modified": timestamp,
            "meta": {},
        }
        self.created_posts.append(record)
        return record

    def create_or_update_post(self, payload):
        post_id = payload.get("id")
        if isinstance(post_id, int) and post_id in self.post_store:
            return self.update_post(post_id, payload)
        return self.create_post(payload)

    def update_post(self, post_id, payload):
        updated_content = payload.get("content")
        if post_id in self.post_store and updated_content:
            self.post_store[post_id]["content"] = updated_content
            self.post_store[post_id]["modified"] = datetime.utcnow().isoformat()
        if post_id in self.post_store and payload.get("meta"):
            self.post_store[post_id].setdefault("meta", {}).update(payload["meta"])
        record = {
            "id": post_id,
            "link": f"https://example.com/{post_id}",
            "categories": payload.get("categories", []),
            "tags": payload.get("tags", []),
            "payload": payload,
        }
        self.updated_posts.append(record)
        return record

    def get_post(self, post_id):
        stored = self.post_store.get(post_id, {})
        content = stored.get("content", "")
        return {
            "id": post_id,
            "content": {"rendered": content},
            "excerpt": {"rendered": stored.get("excerpt", "")},
            "link": stored.get("link"),
            "date": stored.get("date"),
            "modified": stored.get("modified"),
            "meta": stored.get("meta", {}),
        }

    def list_posts(self, **params):
        posts = []
        for post_id, stored in self.post_store.items():
            posts.append(
                {
                    "id": post_id,
                    "title": {"rendered": stored.get("payload", {}).get("title", "")},
                    "status": stored.get("payload", {}).get("status", "publish"),
                }
            )
        return posts

    def delete_post(self, post_id):
        if post_id in self.post_store:
            self.deleted_posts.append(post_id)
            self.post_store.pop(post_id, None)

    def update_settings(self, payload):
        self.settings_updates.append(payload)
        return payload

    def upload_media(self, filename, data, mime_type):
        return {"id": 999, "link": f"https://example.com/media/{filename}"}

    # Menu helpers ------------------------------------------------------
    def list_menus(self):
        return list(self.menus)

    def create_menu(self, name: str):
        self._menu_counter += 1
        menu = {"id": self._menu_counter, "name": name}
        self.menus.append(menu)
        self.menu_items.setdefault(menu["id"], [])
        return menu

    def list_menu_items(self, menu_id: int):
        return list(self.menu_items.get(menu_id, []))

    def create_menu_item(self, menu_id: int, *, title: str, object_id: int, order: int):
        self._menu_item_counter += 1
        item = {
            "id": self._menu_item_counter,
            "title": title,
            "object_id": object_id,
            "object": "category",
            "menu": menu_id,
            "menu_order": order,
        }
        self.menu_items.setdefault(menu_id, []).append(item)
        return item

    def test_connection(self):
        return {"name": "fake", "routes": []}

    def _enrich_content(self, text: str) -> str:
        words = text.split()
        if len(words) >= 120:
            return text
        filler = " ".join(["Expanded context" for _ in range(120)])
        return f"{text}\n\n{filler}"


def prepare_project(tmp_path: Path) -> Tuple[ProjectData, Path]:
    project_data = build_sample_project(tmp_path)
    manager = ProjectManager(base_directory=tmp_path)
    project_root = manager.create_project(project_data)
    generator = TopicalBlueprintGenerator(project_data, project_root)
    generator.generate()
    return project_data, project_root


class FakeCloudflareClient:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []
        self.ssl_modes: list[str] = []
        self.analytics_payload: dict[str, object] = {
            "totals": {"requests": {"all": 0, "cached": 0}, "threats": {"all": 0}}
        }
        self.analytics_requests: list[dict[str, object]] = []

    def ensure_dns_records(self, zone_name: str, records):
        self.records.append({"zone": zone_name, "records": list(records)})
        return True

    def set_ssl_mode(self, zone_name: str, mode: str):
        self.ssl_modes.append(mode)
        return True

    def fetch_analytics(self, zone_name: str, *, since_hours: int = 24):
        self.analytics_requests.append({"zone": zone_name, "since_hours": since_hours})
        return self.analytics_payload


class FakeCommandRunner:
    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.commands: list[list[str]] = []

    def run(self, command):
        self.commands.append(list(command))
        return self.succeed
