"""Internal linking engine for Authority Site Engine projects."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.extensions import get_extension_manager
from ..core.models import ProjectData
from ..core.task_state import TaskStateTracker
from ..core.wp_client import WordPressRestClient

AFFILIATE_TYPES = {"affiliate_review", "amazon_roundup"}


@dataclass
class PostRecord:
    """Lightweight representation of a WordPress post from the post map."""

    post_id: int
    post_title: str
    post_type: str
    post_url: str
    category_ids: List[int]
    tag_ids: List[int]
    scheduled_date: Optional[str]


@dataclass
class LinkInstruction:
    """Description of a planned internal link."""

    source: PostRecord
    target: PostRecord
    anchor_text: str
    relation: str

    def to_dict(self, position: str) -> Dict[str, object]:
        return {
            "source_post_id": self.source.post_id,
            "source_post_title": self.source.post_title,
            "target_post_id": self.target.post_id,
            "target_post_title": self.target.post_title,
            "target_post_url": self.target.post_url,
            "anchor_text": self.anchor_text,
            "link_position_type": position,
            "relation": self.relation,
        }


class InternalLinkingEngine:
    """Apply hierarchical internal linking using the WordPress REST API."""

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
        self.topic_graph_path = self.outputs_dir / "topic_graph.json"
        self.post_map_path = self.content_dir / "post_map.json"
        self.link_map_path = self.content_dir / "link_map.json"
        self.log_file = self.logs_dir / "internal_linking.log"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or self._configure_logger()
        if client is None:
            info = project_data.basic_info
            client = WordPressRestClient(info.wp_admin_url, info.wp_username, info.wp_password, logger=self.logger)
        self.client = client
        self.rules = project_data.linking_rules
        self.task_state = TaskStateTracker(project_root, "internal_linking")
        self.link_counts: Dict[int, int] = {}
        self.link_pairs: set[Tuple[int, int]] = set()
        self.anchor_registry: Dict[int, int] = {}
        self.post_lookup: Dict[int, PostRecord] = {}
        self.posts_by_type: Dict[str, List[PostRecord]] = {}
        self.title_lookup: Dict[Tuple[str, Optional[str]], PostRecord] = {}
        self.post_to_pillar: Dict[int, int] = {}

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"internal_linking.{self.project_data.basic_info.project_name}")
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
        """Plan and optionally apply all internal links."""

        topic_graph = self._load_topic_graph()
        post_records = self._load_post_map()
        self._index_posts(post_records)
        plan = self._build_plan(topic_graph)
        existing_entries: List[Dict[str, object]] = []
        if self.link_map_path.exists():
            existing_entries = json.loads(self.link_map_path.read_text(encoding="utf-8"))
        if partial and existing_entries:
            processed_sources = {entry.get("source_post_id") for entry in existing_entries}
            plan = [
                instruction
                for instruction in plan
                if instruction.source.post_id not in processed_sources
            ]
        if not plan:
            self.logger.info("No links planned; writing empty link map")
            self.link_map_path.write_text("[]", encoding="utf-8")
            return []

        if dry_run:
            planned_entries = [instruction.to_dict(position="planned") for instruction in plan]
            self.link_map_path.write_text(json.dumps(planned_entries, indent=2), encoding="utf-8")
            return planned_entries

        grouped = self._group_plan(plan)
        self.task_state.start(len(grouped), resume=resume)
        start_index = self.task_state.resume_index() if resume else 0
        try:
            applied_entries = self._apply_plan(grouped, start_index)
        except Exception as exc:
            self.task_state.mark_error(str(exc))
            raise
        self.task_state.complete()
        replace = not partial and start_index == 0
        merged = self._merge_entries(existing_entries, applied_entries, replace=replace)
        self.link_map_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        self.logger.info("Applied %s internal links", len(applied_entries))
        get_extension_manager(self.project_root).emit(
            "on_linking_completed", project=self.project_data, link_map=merged
        )
        return applied_entries

    # ------------------------------------------------------------------
    def _load_topic_graph(self) -> Dict[str, object]:
        if not self.topic_graph_path.exists():
            raise FileNotFoundError("topic_graph.json not found. Run the blueprint generator first.")
        return json.loads(self.topic_graph_path.read_text(encoding="utf-8"))

    def _load_post_map(self) -> List[PostRecord]:
        if not self.post_map_path.exists():
            raise FileNotFoundError("post_map.json not found. Run the posting engine first.")
        entries = json.loads(self.post_map_path.read_text(encoding="utf-8"))
        records: List[PostRecord] = []
        for entry in entries:
            post_id = entry.get("post_id")
            if not post_id:
                continue
            records.append(
                PostRecord(
                    post_id=post_id,
                    post_title=entry.get("post_title", ""),
                    post_type=entry.get("post_type", ""),
                    post_url=entry.get("post_url", ""),
                    category_ids=entry.get("category_ids", []),
                    tag_ids=entry.get("tag_ids", []),
                    scheduled_date=entry.get("scheduled_date"),
                )
            )
        return records

    def _index_posts(self, posts: Sequence[PostRecord]) -> None:
        for record in posts:
            self.post_lookup[record.post_id] = record
            self.posts_by_type.setdefault(record.post_type, []).append(record)
            key = self._normalize(record.post_title)
            self.title_lookup.setdefault((key, None), record)
            self.title_lookup[(key, record.post_type)] = record
            self.link_counts.setdefault(record.post_id, 0)

    # ------------------------------------------------------------------
    def _build_plan(self, topic_graph: Dict[str, object]) -> List[LinkInstruction]:
        plan: List[LinkInstruction] = []
        pillars = topic_graph.get("pillars", []) or []
        for pillar_node in pillars:
            pillar_record = self._find_post(pillar_node.get("title", ""), "pillar")
            supporting_records = self._records_for_titles(pillar_node.get("supporting", []), "supporting")
            info_records = self._records_for_titles(pillar_node.get("informational", []), "info")
            affiliate_records = self._records_for_titles(pillar_node.get("affiliate_reviews", []), "affiliate_review")
            amazon_records = self._records_for_titles(pillar_node.get("amazon_roundups", []), "amazon_roundup")

            if pillar_record:
                self.post_to_pillar[pillar_record.post_id] = pillar_record.post_id
            for child in supporting_records + info_records + affiliate_records + amazon_records:
                if pillar_record:
                    self.post_to_pillar[child.post_id] = pillar_record.post_id

            if self.rules.supporting_to_pillar and pillar_record:
                for supporting in supporting_records:
                    plan.extend(self._queue_link(supporting, pillar_record, "supporting_to_pillar"))

            if self.rules.pillar_to_supporting and pillar_record:
                plan.extend(
                    self._links_from_parent(pillar_record, supporting_records, "pillar_to_supporting")
                )

            if info_records:
                if self.rules.informational_to_pillar and pillar_record:
                    for info_post in info_records:
                        plan.extend(self._queue_link(info_post, pillar_record, "info_to_pillar"))
                if self.rules.informational_to_supporting:
                    for info_post in info_records:
                        plan.extend(
                            self._links_from_children(info_post, supporting_records[:3], "info_to_supporting")
                        )

            if affiliate_records and pillar_record and self.rules.affiliate_to_pillar:
                for affiliate in affiliate_records:
                    plan.extend(self._queue_link(affiliate, pillar_record, "affiliate_to_pillar"))
                    if self.rules.allow_affiliate_to_info:
                        plan.extend(
                            self._links_from_children(affiliate, info_records[:1], "affiliate_to_info")
                        )

            if amazon_records and pillar_record and self.rules.amazon_roundup_to_pillar:
                for roundup in amazon_records:
                    plan.extend(self._queue_link(roundup, pillar_record, "amazon_to_pillar"))
                    plan.extend(
                        self._links_from_children(roundup, supporting_records[:2], "amazon_to_supporting")
                    )

            if affiliate_records and self.rules.allow_info_to_affiliate:
                for info_post in info_records:
                    plan.extend(
                        self._links_from_children(info_post, affiliate_records[:1], "info_to_affiliate")
                    )

        return plan

    def _records_for_titles(self, titles: Iterable[str], post_type: Optional[str]) -> List[PostRecord]:
        records: List[PostRecord] = []
        for title in titles or []:
            record = self._find_post(title, post_type)
            if record:
                records.append(record)
            else:
                self.logger.debug("No post found for title '%s' (%s)", title, post_type)
        return records

    def _find_post(self, title: str, post_type: Optional[str]) -> Optional[PostRecord]:
        if not title:
            return None
        key = self._normalize(title)
        if post_type:
            record = self.title_lookup.get((key, post_type))
            if record:
                return record
        return self.title_lookup.get((key, None))

    # ------------------------------------------------------------------
    def _queue_link(self, source: PostRecord, target: PostRecord, relation: str) -> List[LinkInstruction]:
        if not self._can_link(source, target):
            return []
        anchor_text = self._next_anchor_text(target)
        instruction = LinkInstruction(source=source, target=target, anchor_text=anchor_text, relation=relation)
        self.link_counts[source.post_id] += 1
        self.link_pairs.add((source.post_id, target.post_id))
        return [instruction]

    def _links_from_parent(self, source: PostRecord, children: List[PostRecord], relation: str) -> List[LinkInstruction]:
        instructions: List[LinkInstruction] = []
        for child in children:
            if self.link_counts.get(source.post_id, 0) >= self.rules.max_links_per_post:
                break
            instructions.extend(self._queue_link(source, child, relation))
        return instructions

    def _links_from_children(self, source: PostRecord, targets: List[PostRecord], relation: str) -> List[LinkInstruction]:
        instructions: List[LinkInstruction] = []
        for target in targets:
            instructions.extend(self._queue_link(source, target, relation))
        return instructions

    def _can_link(self, source: PostRecord, target: PostRecord) -> bool:
        if source.post_id == target.post_id:
            return False
        if self.link_counts.get(source.post_id, 0) >= self.rules.max_links_per_post:
            return False
        if (source.post_id, target.post_id) in self.link_pairs:
            return False
        if source.post_type in AFFILIATE_TYPES and target.post_type in AFFILIATE_TYPES:
            if not self.rules.affiliate_to_affiliate:
                return False
        if not self.rules.allow_cross_pillar_links:
            source_parent = self.post_to_pillar.get(source.post_id)
            target_parent = self.post_to_pillar.get(target.post_id)
            if source_parent and target_parent and source_parent != target_parent:
                return False
        if not self._is_post_recent(source):
            return False
        if source.post_type == "info" and target.post_type in AFFILIATE_TYPES:
            return self.rules.allow_info_to_affiliate
        if source.post_type in AFFILIATE_TYPES and target.post_type == "info":
            return self.rules.allow_affiliate_to_info
        return True

    def _is_post_recent(self, record: PostRecord) -> bool:
        days = self.rules.skip_posts_older_than_days
        if not days or days <= 0:
            return True
        if not record.scheduled_date:
            return True
        try:
            scheduled = datetime.fromisoformat(record.scheduled_date)
        except ValueError:
            return True
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        return scheduled >= threshold

    def _next_anchor_text(self, target: PostRecord) -> str:
        variants = [
            target.post_title,
            f"learn more about {target.post_title}",
            f"{target.post_title} guide",
            f"explore {target.post_title}",
        ]
        index = self.anchor_registry.get(target.post_id, 0)
        anchor = variants[index % len(variants)]
        self.anchor_registry[target.post_id] = index + 1
        return anchor

    # ------------------------------------------------------------------
    def _group_plan(self, plan: List[LinkInstruction]) -> Dict[int, List[LinkInstruction]]:
        grouped: Dict[int, List[LinkInstruction]] = {}
        for instruction in plan:
            grouped.setdefault(instruction.source.post_id, []).append(instruction)
        return grouped

    def _apply_plan(
        self,
        grouped_plan: Dict[int, List[LinkInstruction]],
        start_index: int,
    ) -> List[Dict[str, object]]:
        entries: List[Dict[str, object]] = []
        source_ids = list(grouped_plan.keys())
        for idx, source_id in enumerate(source_ids):
            if idx < start_index:
                continue
            instructions = grouped_plan[source_id]
            record = self.post_lookup.get(source_id)
            if not record:
                self.task_state.advance(idx)
                continue
            current_count = len(instructions)
            if current_count < self.rules.min_links_per_post:
                self.logger.warning(
                    "Post %s planned with %s links (below minimum %s)",
                    record.post_title,
                    current_count,
                    self.rules.min_links_per_post,
                )
            try:
                post = self.client.get_post(source_id)
            except Exception as exc:  # pragma: no cover - network errors mocked in tests
                self.logger.error("Failed to fetch post %s: %s", source_id, exc)
                continue
            content = self._extract_content(post)
            if self._word_count(content) < self.rules.minimum_word_count_for_linking:
                self.logger.info(
                    "Skipping post %s due to minimum word count", record.post_title
                )
                continue
            updated_content, placements = self._insert_links(content, instructions)
            if not placements:
                continue
            try:
                self.client.update_post(source_id, {"content": updated_content})
            except Exception as exc:  # pragma: no cover
                self.logger.error("Failed to update post %s: %s", source_id, exc)
                self.task_state.advance(idx)
                continue
            for instruction, position in placements:
                entry = instruction.to_dict(position=position)
                entries.append(entry)
            self.task_state.advance(idx)
        return entries

    def _merge_entries(
        self,
        existing: List[Dict[str, object]],
        new_entries: List[Dict[str, object]],
        *,
        replace: bool,
    ) -> List[Dict[str, object]]:
        if replace:
            return new_entries
        seen: Dict[tuple, Dict[str, object]] = {}
        for entry in existing + new_entries:
            key = (
                entry.get("source_post_id"),
                entry.get("target_post_id"),
                entry.get("anchor_text"),
            )
            seen[key] = entry
        return list(seen.values())

    def _extract_content(self, post_payload: Dict[str, object]) -> str:
        content = post_payload.get("content")
        if isinstance(content, dict):
            rendered = content.get("rendered")
            if isinstance(rendered, str):
                return rendered
        if isinstance(content, str):
            return content
        return ""

    def _word_count(self, content: str) -> int:
        return len(re.findall(r"\w+", content))

    def _insert_links(
        self, content: str, instructions: Sequence[LinkInstruction]
    ) -> Tuple[str, List[Tuple[LinkInstruction, str]]]:
        paragraphs = content.split("\n")
        placements: List[Tuple[LinkInstruction, str]] = []
        leftover: List[LinkInstruction] = []
        para_index = 0
        for instruction in instructions:
            inserted = False
            for idx in range(para_index, len(paragraphs)):
                paragraph = paragraphs[idx]
                if not self._paragraph_can_host(paragraph):
                    continue
                anchor_html = self._anchor_html(instruction)
                paragraphs[idx] = paragraph + f" {self._link_sentence(anchor_html)}"
                placements.append((instruction, "inline"))
                para_index = idx + 1
                inserted = True
                break
            if not inserted:
                leftover.append(instruction)
        if leftover:
            block = self._further_reading_block(leftover)
            paragraphs.append(block)
            placements.extend([(instruction, "further_reading") for instruction in leftover])
        return "\n".join(paragraphs), placements

    def _paragraph_can_host(self, paragraph: str) -> bool:
        text = paragraph.strip()
        if len(text) < 60:
            return False
        if "<a " in text.lower():
            return False
        if text.lower().startswith("<h"):
            return False
        return True

    def _anchor_html(self, instruction: LinkInstruction) -> str:
        return f'<a href="{instruction.target.post_url}">{instruction.anchor_text}</a>'

    def _link_sentence(self, anchor_html: str) -> str:
        return f"Learn more in {anchor_html}."

    def _further_reading_block(self, instructions: Sequence[LinkInstruction]) -> str:
        if self.rules.use_further_reading_blocks:
            items = "".join(
                f"<li>{self._anchor_html(instruction)}</li>" for instruction in instructions
            )
            container = "aside" if self.rules.allow_sidebar_blocks else "section"
            return (
                f"<{container} class=\"ase-further-reading\">"
                f"<h3>Further Reading</h3><ul>{items}</ul>"
                f"</{container}>"
            )
        return "\n".join(self._link_sentence(self._anchor_html(instruction)) for instruction in instructions)

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())


__all__ = ["InternalLinkingEngine", "PostRecord", "LinkInstruction"]
