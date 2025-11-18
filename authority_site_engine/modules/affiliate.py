"""Affiliate Link Engine for Authority Site Engine projects."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from ..core.deployment_manager import resolve_wordpress_connection
from ..core.models import AffiliateOffer, ProjectData
from ..core.task_state import TaskStateTracker
from ..core.wp_client import WordPressRestClient

PLACEHOLDER_ORDER = ["CTA_TOP", "CTA_INLINE", "AFFILIATE_BOX", "CTA_BOTTOM"]
TEMPLATE_TOKEN_RE = re.compile(r"{{\s*(\w+)\s*}}")


@dataclass
class ReplacementRecord:
    """Summary of a CTA replacement for logging/testing."""

    placeholder: str
    offer_id: str
    affiliate_url: str
    template_preview: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "placeholder": self.placeholder,
            "offer_id": self.offer_id,
            "affiliate_url": self.affiliate_url,
            "template_preview": self.template_preview,
        }


class AffiliateLinkEngine:
    """Replace CTA placeholders with affiliate offers in a niche-agnostic way."""

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        client: WordPressRestClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.post_map_path = self.content_dir / "post_map.json"
        self.category_map_path = self.content_dir / "category_map.json"
        self.cta_map_path = self.content_dir / "cta_map.json"
        self.log_file = self.logs_dir / "affiliate_engine.log"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or self._configure_logger()
        self.task_state = TaskStateTracker(project_root, "affiliate")
        if client is None:
            connection = resolve_wordpress_connection(project_data)
            client = WordPressRestClient(
                connection.site_url,
                connection.username,
                connection.password,
                api_root=connection.api_base_url,
                logger=self.logger,
            )
        self.client = client
        self.category_lookup = self._load_category_lookup()
        self.affiliates = project_data.affiliate_links

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(
            f"affiliate_engine.{self.project_data.basic_info.project_name}"
        )
        logger.setLevel(logging.INFO)
        if logger.handlers:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    # ------------------------------------------------------------------
    def run(
        self,
        *,
        dry_run: bool = False,
        partial: bool = False,
        resume: bool = True,
    ) -> List[Dict[str, object]]:
        """Replace placeholders for every post in the post map."""

        post_map = self._load_post_map()
        cta_map = self._load_cta_map()
        if partial and cta_map:
            processed_ids = {int(key) for key in cta_map.keys()}
            post_map = [entry for entry in post_map if entry.get("post_id") not in processed_ids]
        self.task_state.start(len(post_map), resume=resume)
        start_index = self.task_state.resume_index() if resume else 0
        results: List[Dict[str, object]] = []
        try:
            for index, entry in enumerate(post_map):
                if index < start_index:
                    continue
                post_id = entry.get("post_id")
                post_type = entry.get("post_type", "")
                if not post_id:
                    self.task_state.advance(index)
                    continue
                allowed_placeholders = self._allowed_placeholders(post_type)
                if not allowed_placeholders:
                    self.task_state.advance(index)
                    continue
                replacements = self._process_post(entry, allowed_placeholders, dry_run=dry_run)
                if replacements:
                    results.append(
                        {
                            "post_id": post_id,
                            "post_title": entry.get("post_title"),
                            "post_type": post_type,
                            "replacements": [record.to_dict() for record in replacements],
                        }
                    )
                    cta_map[str(post_id)] = [record.to_dict() for record in replacements]
                self.task_state.advance(index)
        except Exception as exc:
            self.task_state.mark_error(str(exc))
            raise
        self.task_state.complete()
        self._save_cta_map(cta_map)
        if not results:
            self.logger.info("Affiliate engine completed with no replacements")
        else:
            self.logger.info("Affiliate engine updated %s posts", len(results))
        return results

    # ------------------------------------------------------------------
    def _allowed_placeholders(self, post_type: str) -> List[str]:
        allowed: List[str] = []
        mapping = self.affiliates.placeholder_post_types or {}
        for placeholder, post_types in mapping.items():
            if not post_types or post_type in post_types:
                allowed.append(placeholder)
        return allowed

    def _load_post_map(self) -> List[Dict[str, object]]:
        if not self.post_map_path.exists():
            raise FileNotFoundError("post_map.json not found. Run the posting engine first.")
        return json.loads(self.post_map_path.read_text(encoding="utf-8"))

    def _load_category_lookup(self) -> Dict[int, str]:
        if not self.category_map_path.exists():
            return {}
        data = json.loads(self.category_map_path.read_text(encoding="utf-8"))
        assignments = data.get("assignments", [])
        lookup: Dict[int, str] = {}
        for entry in assignments:
            post_id = entry.get("post_id")
            if not post_id:
                continue
            lookup[post_id] = entry.get("category_name", "")
        return lookup

    def _load_cta_map(self) -> Dict[str, List[Dict[str, object]]]:
        if not self.cta_map_path.exists():
            return {}
        return json.loads(self.cta_map_path.read_text(encoding="utf-8"))

    def _save_cta_map(self, payload: Dict[str, List[Dict[str, object]]]) -> None:
        self.cta_map_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    def _process_post(
        self,
        entry: Dict[str, object],
        allowed_placeholders: Sequence[str],
        *,
        dry_run: bool,
    ) -> List[ReplacementRecord]:
        post_id = int(entry["post_id"])
        response = self.client.get_post(post_id)
        rendered = response.get("content", {}).get("rendered", "")
        updated_content, replacements = self._inject_ctas(
            rendered,
            entry,
            allowed_placeholders,
        )
        if not replacements:
            return []
        if dry_run:
            self.logger.info(
                "Planned %s CTA replacements for post %s", len(replacements), post_id
            )
            return replacements
        self.client.update_post(post_id, {"content": updated_content})
        self.logger.info(
            "Updated post %s with %s CTA replacements", post_id, len(replacements)
        )
        return replacements

    def _inject_ctas(
        self,
        content: str,
        entry: Dict[str, object],
        allowed_placeholders: Sequence[str],
    ) -> tuple[str, List[ReplacementRecord]]:
        max_ctas = max(1, self.affiliates.max_ctas_per_post or 1)
        replacements: List[ReplacementRecord] = []
        working = content
        used = 0
        for placeholder in PLACEHOLDER_ORDER:
            if placeholder not in allowed_placeholders:
                continue
            marker = f"[{placeholder}]"
            template = self.affiliates.cta_templates.get(placeholder)
            if not template:
                continue
            while marker in working and used < max_ctas:
                offer = self._select_offer(entry, placeholder)
                url = offer["affiliate_url"]
                html = self._render_template(template, entry, offer)
                working = working.replace(marker, html, 1)
                replacements.append(
                    ReplacementRecord(
                        placeholder=placeholder,
                        offer_id=offer["offer_id"],
                        affiliate_url=url,
                        template_preview=html[:120],
                    )
                )
                used += 1
            if used >= max_ctas:
                break
        return working, replacements

    # ------------------------------------------------------------------
    def _select_offer(self, entry: Dict[str, object], placeholder: str) -> Dict[str, str]:
        offers = self.affiliates.offers
        title = (entry.get("post_title") or "").lower()
        category = (self.category_lookup.get(entry.get("post_id")) or "").lower()
        post_type = entry.get("post_type", "")
        if not offers:
            url = self._fallback_url()
            return {
                "offer_id": "fallback",
                "name": "Fallback Offer",
                "affiliate_url": url,
            }

        scored: List[tuple[int, AffiliateOffer]] = []
        for offer in offers:
            if offer.post_types and post_type not in offer.post_types:
                continue
            score = 0
            if offer.product_names:
                for product_name in offer.product_names:
                    if product_name.lower() in title:
                        score += 5
                        break
            if category and offer.categories:
                normalized = {c.lower() for c in offer.categories}
                if category in normalized:
                    score += 2
            if not offer.post_types:
                score += 1
            scored.append((score, offer))
        if not scored:
            scored = [(0, offer) for offer in offers]
        best_score = max(score for score, _ in scored)
        candidates = [offer for score, offer in scored if score == best_score]
        chosen = self._weighted_choice(candidates, entry, placeholder)
        return {
            "offer_id": chosen.offer_id,
            "name": chosen.name,
            "affiliate_url": self._build_affiliate_url(chosen),
        }

    def _weighted_choice(
        self,
        offers: Sequence[AffiliateOffer],
        entry: Dict[str, object],
        placeholder: str,
    ) -> AffiliateOffer:
        if not offers:
            raise ValueError("No offers available for selection")
        if not self.affiliates.rotation_enabled or len(offers) == 1:
            return offers[0]
        total = sum(max(1, offer.weight) for offer in offers)
        seed = abs(hash((entry.get("post_id"), placeholder)))
        pick = seed % total
        cumulative = 0
        for offer in sorted(offers, key=lambda item: item.offer_id):
            cumulative += max(1, offer.weight)
            if pick < cumulative:
                return offer
        return offers[0]

    def _build_affiliate_url(self, offer: AffiliateOffer) -> str:
        redirector = (self.affiliates.geo_redirector_url or "").strip()
        if redirector:
            separator = "&" if "?" in redirector else "?"
            return f"{redirector}{separator}offer={offer.offer_id}"
        return offer.base_url

    def _fallback_url(self) -> str:
        if self.affiliates.backup_url:
            return self.affiliates.backup_url
        for pool in (self.affiliates.cpa_links, self.affiliates.amazon_links, self.affiliates.custom_links):
            if pool:
                return pool[0]
        return "https://example.com"

    # ------------------------------------------------------------------
    def _render_template(
        self,
        template: str,
        entry: Dict[str, object],
        offer: Dict[str, str],
    ) -> str:
        context = {
            "offer_name": offer.get("name") or "Affiliate Offer",
            "affiliate_url": offer["affiliate_url"],
            "button_text": "Check Latest Offer",
            "cta_text": self._cta_text(entry, offer),
            "niche_name": self.project_data.basic_info.niche,
            "product_name": offer.get("name") or "",
            "post_title": entry.get("post_title", ""),
            "project_name": self.project_data.basic_info.project_name,
        }

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return context.get(key, "")

        return TEMPLATE_TOKEN_RE.sub(replace, template)

    def _cta_text(self, entry: Dict[str, object], offer: Dict[str, str]) -> str:
        niche = self.project_data.basic_info.niche or "this niche"
        title = entry.get("post_title") or offer.get("name") or "this product"
        return f"Discover why {title} is a top pick for {niche}."


__all__ = ["AffiliateLinkEngine", "ReplacementRecord"]
