"""Niche-agnostic topical blueprint generator for Authority Site Engine projects."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from ..core.models import ProjectData


@dataclass
class TopicalBlueprint:
    """Container for the generated blueprint artifacts."""

    pillars: List[str]
    supporting_topics: Dict[str, List[str]]
    informational_topics: List[str]
    affiliate_reviews: List[str]
    amazon_roundups: List[str]
    categories: List[str]
    topic_graph: Dict[str, object]


class TopicalBlueprintGenerator:
    """Create CSVs and JSON maps that represent the full topic hierarchy."""

    def __init__(self, project_data: ProjectData, project_root: Path) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.outputs_dir = self.project_root / "outputs"
        self.csv_dir = self.outputs_dir / "csv"
        self.topic_graph_path = self.outputs_dir / "topic_graph.json"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.niche = project_data.basic_info.niche.strip() or "Authority Site"
        self.niche_title = self.niche.title()
        self.keywords = self._keywords_from_niche(self.niche)

    def generate(self) -> TopicalBlueprint:
        content = self.project_data.content_structure
        pillar_count = max(1, content.pillar_posts)
        supporting_per_pillar = max(1, content.supporting_posts_per_pillar)
        info_count = max(content.informational_posts, pillar_count * supporting_per_pillar)

        pillars = self._generate_pillars(pillar_count)
        supporting_topics = {
            pillar: self._generate_supporting_topics(pillar, supporting_per_pillar)
            for pillar in pillars
        }
        informational_topics = self._generate_informational_topics(info_count, pillars)
        affiliate_reviews = self._generate_affiliate_reviews()
        amazon_roundups = self._generate_amazon_roundups()
        categories = self._categories()

        topic_graph = self._build_topic_graph(
            pillars,
            supporting_topics,
            informational_topics,
            affiliate_reviews,
            amazon_roundups,
            categories,
        )

        blueprint = TopicalBlueprint(
            pillars=pillars,
            supporting_topics=supporting_topics,
            informational_topics=informational_topics,
            affiliate_reviews=affiliate_reviews,
            amazon_roundups=amazon_roundups,
            categories=categories,
            topic_graph=topic_graph,
        )

        self._write_csvs(blueprint)
        self.topic_graph_path.write_text(json.dumps(topic_graph, indent=2), encoding="utf-8")
        return blueprint

    # ------------------------------------------------------------------
    def _keywords_from_niche(self, niche: str) -> List[str]:
        words = [word for word in re.split(r"[^a-z0-9]+", niche.lower()) if word]
        return words or ["authority", "topic"]

    def _generate_pillars(self, count: int) -> List[str]:
        templates = [
            "Essential {keyword} Foundations",
            "{keyword} Strategies & Systems",
            "Innovations in {keyword}",
            "{keyword} Buyer & Planning Guides",
            "{keyword} Troubleshooting & Optimization",
            "Future of {keyword} Applications",
            "{keyword} Lifestyle & Adoption",
            "{keyword} Operations & Maintenance",
        ]
        pillars: List[str] = []
        for index in range(count):
            template = templates[index % len(templates)]
            keyword = self.keywords[index % len(self.keywords)].title()
            pillars.append(template.format(keyword=keyword))
        return pillars

    def _generate_supporting_topics(self, pillar: str, count: int) -> List[str]:
        patterns = [
            "How does {keyword} improve {pillar}?",
            "Step-by-step plan for {action} {keyword} within {pillar}",
            "Common mistakes when {action} {keyword} for {pillar}",
            "Comparing {keyword} options for better {pillar}",
            "What experts say about {keyword} and {pillar}",
            "{pillar}: troubleshooting {keyword} challenges",
            "What does it cost to implement {keyword} for {pillar}?",
            "Metrics to track when evaluating {keyword} in {pillar}",
            "Beginner guide to {keyword} in {pillar}",
            "Advanced tactics for leveraging {keyword} in {pillar}",
        ]
        actions = ["deploying", "choosing", "using", "testing", "optimizing"]
        topics: List[str] = []
        for idx in range(count):
            keyword = self.keywords[idx % len(self.keywords)].title()
            pattern = patterns[idx % len(patterns)]
            action = actions[idx % len(actions)]
            topics.append(
                pattern.format(
                    keyword=keyword,
                    pillar=pillar,
                    action=action,
                )
            )
        return topics

    def _generate_informational_topics(self, count: int, pillars: Iterable[str]) -> List[str]:
        patterns = [
            "What is the history of {keyword}?",
            "{keyword} checklist for busy teams",
            "Seasonal trends shaping {keyword}",
            "Beginner FAQ: {keyword}",
            "Field report: real-world {keyword} examples",
            "Science behind {keyword}",
            "Budget planning for {keyword}",
            "Expert interviews about {keyword}",
            "Glossary of {keyword} concepts",
            "Comparing legacy vs modern {keyword} approaches",
            "{keyword} myths debunked",
            "Measuring ROI from {keyword}",
            "How to present {keyword} insights to stakeholders",
            "Local vs global considerations for {keyword}",
            "{keyword} templates and worksheets",
        ]
        info_topics: List[str] = []
        pillar_list = list(pillars) or [self.niche_title]
        for idx in range(count):
            pattern = patterns[idx % len(patterns)]
            keyword = pillar_list[idx % len(pillar_list)]
            info_topics.append(pattern.format(keyword=keyword))
        return info_topics

    def _generate_affiliate_reviews(self) -> List[str]:
        requested = max(0, self.project_data.content_structure.affiliate_product_posts)
        if requested == 0:
            return []
        products = self.project_data.product_lists.affiliate_products or [f"Signature {self.niche_title} Pick"]
        variants = ["", "Deep Dive", "User Impressions", "Performance Test", "Pros & Cons"]
        titles: List[str] = []
        for idx in range(requested):
            name = products[idx % len(products)].strip() or self.niche_title
            variant = variants[idx % len(variants)]
            suffix = f" - {variant}" if variant else ""
            titles.append(f"{name} Review{suffix}: Honest {self.niche_title} Breakdown")
        return titles

    def _generate_amazon_roundups(self) -> List[str]:
        requested = max(0, self.project_data.content_structure.amazon_roundup_posts)
        if requested == 0:
            return []
        products = self.project_data.product_lists.amazon_products or [self.niche_title]
        patterns = [
            "Best {keyword} Picks Under $50",
            "Top 10 {keyword} Products on Amazon",
            "5 Best {keyword} Options for Beginners",
            "{keyword} Gift Guide: Editor's Picks",
            "Most Durable {keyword} Bundles Online",
            "{keyword} Upgrades Worth the Hype",
        ]
        titles: List[str] = []
        for idx in range(requested):
            product = products[idx % len(products)]
            keyword = product.strip() or self.niche_title
            pattern = patterns[idx % len(patterns)]
            titles.append(pattern.format(keyword=keyword))
        return titles

    def _categories(self) -> List[str]:
        categories = [c for c in self.project_data.categories.categories if c.strip()]
        if categories:
            return categories
        suggestions = [c for c in self.project_data.categories.suggestions if c.strip()]
        if suggestions:
            return suggestions[:4]
        base = self.niche_title
        return [
            f"{base} Fundamentals",
            f"{base} Guides",
            f"{base} Products",
            f"{base} Trends",
        ]

    def _build_topic_graph(
        self,
        pillars: List[str],
        supporting_topics: Dict[str, List[str]],
        informational_topics: List[str],
        affiliate_reviews: List[str],
        amazon_roundups: List[str],
        categories: List[str],
    ) -> Dict[str, object]:
        linking = self.project_data.linking_rules
        pillar_count = len(pillars) or 1
        info_chunks = self._chunk(informational_topics, pillar_count)
        affiliate_chunks = self._chunk(affiliate_reviews, pillar_count)
        amazon_chunks = self._chunk(amazon_roundups, pillar_count)

        graph_pillars = []
        for index, pillar in enumerate(pillars or [self.niche_title]):
            graph_pillars.append(
                {
                    "title": pillar,
                    "category": categories[index % len(categories)] if categories else "",
                    "supporting": supporting_topics.get(pillar, []),
                    "informational": info_chunks[index],
                    "affiliate_reviews": affiliate_chunks[index],
                    "amazon_roundups": amazon_chunks[index],
                    "linking": {
                        "supporting_to_pillar": linking.supporting_to_pillar,
                        "pillar_to_supporting": linking.pillar_to_supporting,
                        "informational_to_pillar": linking.informational_to_pillar,
                        "informational_to_supporting": linking.informational_to_supporting,
                        "affiliate_to_pillar": linking.affiliate_to_pillar,
                        "amazon_roundup_to_pillar": linking.amazon_roundup_to_pillar,
                        "allow_cross_topic_links": linking.allow_cross_topic_links,
                    },
                }
            )

        graph = {
            "niche": self.niche,
            "categories": categories,
            "pillars": graph_pillars,
            "linking_rules": {
                "affiliate_to_affiliate": self.project_data.linking_rules.affiliate_to_affiliate,
            },
        }
        return graph

    def _write_csvs(self, blueprint: TopicalBlueprint) -> None:
        self._write_csv(
            self.csv_dir / "pillar_posts.csv",
            [(title, self._category_for_index(idx, blueprint.categories), "Pillar overview") for idx, title in enumerate(blueprint.pillars)],
        )
        supporting_rows = []
        for pillar in blueprint.pillars:
            for topic in blueprint.supporting_topics[pillar]:
                supporting_rows.append((topic, pillar, "Supporting article"))
        self._write_csv(self.csv_dir / "supporting_posts.csv", supporting_rows)

        info_rows = [
            (topic, self._category_for_index(idx, blueprint.categories), "Informational coverage")
            for idx, topic in enumerate(blueprint.informational_topics)
        ]
        self._write_csv(self.csv_dir / "info_posts.csv", info_rows)

        affiliate_rows = [
            (title, "Product Reviews", "Affiliate review focus") for title in blueprint.affiliate_reviews
        ]
        self._write_csv(self.csv_dir / "affiliate_product_reviews.csv", affiliate_rows)

        amazon_rows = [
            (title, "Amazon Roundups", "Roundup keyword") for title in blueprint.amazon_roundups
        ]
        self._write_csv(self.csv_dir / "amazon_roundups.csv", amazon_rows)

    def _write_csv(self, path: Path, rows: Iterable[tuple[str, str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Title", "Category", "Instructions"])
            for row in rows:
                writer.writerow(row)

    def _category_for_index(self, idx: int, categories: List[str]) -> str:
        if not categories:
            return self.niche_title
        return categories[idx % len(categories)]

    def _chunk(self, items: List[str], chunk_count: int) -> List[List[str]]:
        chunk_count = max(1, chunk_count)
        result: List[List[str]] = [[] for _ in range(chunk_count)]
        for idx, item in enumerate(items):
            result[idx % chunk_count].append(item)
        return result


__all__ = ["TopicalBlueprint", "TopicalBlueprintGenerator"]
