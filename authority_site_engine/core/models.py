"""Dataclasses that describe the configuration of an Authority Site Engine project."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List

from .version import ENGINE_VERSION


def default_cta_templates() -> Dict[str, str]:
    """Return CTA templates keyed by placeholder name."""

    return {
        "CTA_TOP": (
            '<div class="affiliate-cta affiliate-cta-top">'
            "<p>{{cta_text}}</p>"
            '<a href="{{affiliate_url}}" class="affiliate-button" '
            'target="_blank" rel="nofollow sponsored">{{button_text}}</a>'
            "</div>"
        ),
        "CTA_BOTTOM": (
            '<div class="affiliate-cta affiliate-cta-bottom">'
            "<p>{{cta_text}}</p>"
            '<a href="{{affiliate_url}}" class="affiliate-button" '
            'target="_blank" rel="nofollow sponsored">{{button_text}}</a>'
            "</div>"
        ),
        "CTA_INLINE": (
            '<a class="affiliate-inline" href="{{affiliate_url}}" '
            'target="_blank" rel="nofollow sponsored">{{button_text}}</a>'
        ),
        "AFFILIATE_BOX": (
            '<div class="affiliate-cta affiliate-cta-box">'
            "<h3>{{offer_name}}</h3>"
            "<p>{{cta_text}}</p>"
            '<a href="{{affiliate_url}}" class="affiliate-button" '
            'target="_blank" rel="nofollow sponsored">{{button_text}}</a>'
            "</div>"
        ),
    }


def default_placeholder_usage() -> Dict[str, List[str]]:
    """Return default mapping of placeholders to post types."""

    return {
        "CTA_TOP": ["affiliate_review", "amazon_roundup"],
        "CTA_BOTTOM": ["affiliate_review", "amazon_roundup", "info"],
        "CTA_INLINE": ["info", "supporting", "pillar"],
        "AFFILIATE_BOX": ["affiliate_review", "amazon_roundup"],
    }


def default_schema_post_type_map() -> Dict[str, Dict[str, bool]]:
    """Return schema toggles per logical post type."""

    return {
        "pillar": {"article": True, "faq": False, "product": False, "review": False},
        "supporting": {"article": True, "faq": False, "product": False, "review": False},
        "info": {"article": True, "faq": False, "product": False, "review": False},
        "affiliate_review": {
            "article": True,
            "product": True,
            "review": True,
            "faq": False,
        },
        "amazon_roundup": {
            "article": True,
            "product": False,
            "review": False,
            "faq": False,
        },
    }


@dataclass
class BasicSiteInfo:
    project_name: str
    niche: str
    domain_name: str
    wp_admin_url: str
    wp_username: str
    wp_password: str
    wp_credential_id: str = ""


@dataclass
class CloudflareHostInfo:
    cloudflare_email: str
    cloudflare_api_key: str
    ssh_host: str = ""
    ssh_username: str = ""
    ssh_password: str = ""
    dns_records: List[Dict[str, str]] = field(default_factory=list)
    credential_id: str = ""


@dataclass
class ContentStructureSettings:
    pillar_posts: int
    supporting_posts_per_pillar: int
    informational_posts: int
    affiliate_product_posts: int
    amazon_roundup_posts: int
    custom_product_posts: int


@dataclass
class CategorySettings:
    suggestions: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)


@dataclass
class ProductLists:
    affiliate_products: List[str] = field(default_factory=list)
    amazon_products: List[str] = field(default_factory=list)
    custom_products: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AffiliateLinkSet:
    cpa_links: List[str] = field(default_factory=list)
    amazon_links: List[str] = field(default_factory=list)
    custom_links: List[str] = field(default_factory=list)
    geo_targeted: Dict[str, str] = field(default_factory=dict)
    backup_url: str = ""
    offers: List["AffiliateOffer"] = field(default_factory=list)
    cta_templates: Dict[str, str] = field(default_factory=default_cta_templates)
    placeholder_post_types: Dict[str, List[str]] = field(default_factory=default_placeholder_usage)
    max_ctas_per_post: int = 3
    rotation_enabled: bool = True
    geo_redirector_url: str = ""


@dataclass
class AffiliateOffer:
    """Affiliate offer metadata for CTA rendering and rotation."""

    offer_id: str
    name: str
    base_url: str
    network_type: str = "custom"
    allowed_countries: List[str] = field(default_factory=list)
    blocked_countries: List[str] = field(default_factory=list)
    weight: int = 1
    product_names: List[str] = field(default_factory=list)
    post_types: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class PostingPreferences:
    post_immediately: bool
    scheduling_interval_hours: int
    drip_posting: bool
    publish_sequence: List[str] = field(default_factory=list)


@dataclass
class ZimmWriterTemplate:
    name: str
    template_path: str
    description: str = ""


@dataclass
class ZimmWriterSettings:
    templates: List[ZimmWriterTemplate] = field(default_factory=list)


@dataclass
class LinkingRules:
    """Configuration flags for the internal linking engine."""

    supporting_to_pillar: bool = True
    pillar_to_supporting: bool = True
    informational_to_pillar: bool = True
    informational_to_supporting: bool = True
    affiliate_to_pillar: bool = True
    affiliate_to_affiliate: bool = False
    amazon_roundup_to_pillar: bool = True
    allow_cross_topic_links: bool = False
    max_links_per_post: int = 8
    min_links_per_post: int = 2
    allow_cross_pillar_links: bool = False
    allow_info_to_affiliate: bool = False
    allow_affiliate_to_info: bool = False
    use_further_reading_blocks: bool = True
    minimum_word_count_for_linking: int = 150
    allow_sidebar_blocks: bool = False
    skip_posts_older_than_days: int = 0


@dataclass
class SchemaSettings:
    """Configuration for the schema engine."""

    inject_method: str = "content"  # "content" or "meta"
    prefer_existing_schema: bool = False
    site_name: str = ""
    site_url: str = ""
    publisher_logo_url: str = ""
    default_author_name: str = ""
    default_author_type: str = "Person"  # or "Organization"
    breadcrumb_enabled: bool = True
    faq_detection_enabled: bool = False
    schema_meta_key: str = "ase_schema_json"
    post_type_schema: Dict[str, Dict[str, bool]] = field(
        default_factory=default_schema_post_type_map
    )
    marker_start: str = "<!-- ASE_SCHEMA_START -->"
    marker_end: str = "<!-- ASE_SCHEMA_END -->"


def default_sitemap_paths() -> List[str]:
    return ["/wp-sitemap.xml", "/sitemap_index.xml"]


@dataclass
class HealthMonitoringSettings:
    """Configuration for the lightweight health monitor."""

    enable_http_checks: bool = True
    http_sample_size: int = 3
    enable_ssl_check: bool = True
    enable_sitemap_check: bool = True
    enable_linking_check: bool = True
    enable_content_stats: bool = True
    enable_cloudflare_stats: bool = False
    http_timeout: int = 15
    cloudflare_hours: int = 24


@dataclass
class AutomationTaskConfig:
    """Simple enable + interval toggle for a scheduled task."""

    enabled: bool = True
    interval_hours: int = 24


def _task(default_enabled: bool, hours: int) -> AutomationTaskConfig:
    return AutomationTaskConfig(enabled=default_enabled, interval_hours=hours)


@dataclass
class AutomationSettings:
    """Configuration for the daily automation scheduler."""

    automation_enabled: bool = False
    throttle_seconds: float = 0.0
    log_retention_days: int = 30
    health_check: AutomationTaskConfig = field(
        default_factory=lambda: _task(True, 24)
    )
    affiliate_check: AutomationTaskConfig = field(
        default_factory=lambda: _task(True, 48)
    )
    sitemap_ping: AutomationTaskConfig = field(
        default_factory=lambda: _task(False, 168)
    )
    linking_maintenance: AutomationTaskConfig = field(
        default_factory=lambda: _task(False, 168)
    )
    content_review: AutomationTaskConfig = field(
        default_factory=lambda: _task(True, 24)
    )
    cloudflare_stats: AutomationTaskConfig = field(
        default_factory=lambda: _task(False, 24)
    )
    log_cleanup: AutomationTaskConfig = field(
        default_factory=lambda: _task(True, 720)
    )


@dataclass
class DeploymentSettings:
    configure_cloudflare: bool = True
    enforce_https: bool = True
    cloudflare_ssl_mode: str = "full"
    install_wordpress: bool = False
    install_theme: bool = True
    install_plugins: bool = True
    deploy_content: bool = True
    run_category_builder: bool = True
    run_internal_linking: bool = True
    run_affiliate: bool = True
    run_schema: bool = True
    ping_sitemaps: bool = True
    sitemap_paths: List[str] = field(default_factory=default_sitemap_paths)
    theme_slug: str = ""
    theme_zip_url: str = ""
    plugin_slugs: List[str] = field(default_factory=list)
    plugin_zip_urls: List[str] = field(default_factory=list)
    wp_cli_path: str = "wp"
    strict_mode: bool = False
    site_title: str = ""
    admin_email: str = ""
    timezone: str = "UTC"
    permalink_structure: str = "/%postname%/"


@dataclass
class ProjectData:
    basic_info: BasicSiteInfo
    cloudflare: CloudflareHostInfo
    content_structure: ContentStructureSettings
    categories: CategorySettings
    product_lists: ProductLists
    affiliate_links: AffiliateLinkSet
    posting_preferences: PostingPreferences
    zimmwriter: ZimmWriterSettings
    linking_rules: LinkingRules
    schema: SchemaSettings
    deployment: DeploymentSettings
    health: HealthMonitoringSettings
    automation: AutomationSettings
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> Dict[str, object]:
        """Return the project data as a serializable dictionary."""
        payload = asdict(self)
        payload["engine_version"] = getattr(self, "engine_version", ENGINE_VERSION)
        basic = payload.get("basic_info", {})
        if "wp_password" in basic:
            basic["wp_password"] = ""
        cloudflare = payload.get("cloudflare", {})
        if "cloudflare_api_key" in cloudflare:
            cloudflare["cloudflare_api_key"] = ""
        return payload


@dataclass
class ProjectSummary:
    """Lightweight snapshot for quickly listing projects in the GUI."""

    project_name: str
    domain: str
    niche: str
    status: str
    last_health_check: str
    automation_enabled: bool
    health_status: str = ""
    project_root: str = ""
