from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.models.bid_outline_node import BidOutlineNode
from src.models.chapter_pattern import ChapterPattern, ChapterPatternStatus
from src.models.chapter_pattern_mining_task import (
    ChapterPatternMiningTask,
    ChapterPatternMiningTaskStatus,
)
from src.models.template_chapter import TemplateChapter
from src.services.alias_registry import normalize


class ChapterPatternMiningServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_request_config(
    task: ChapterPatternMiningTask,
) -> tuple[int, bool]:
    payload = task.result_summary if isinstance(task.result_summary, dict) else {}
    min_frequency = payload.get("requested_min_frequency", 2)
    include_template_chapters = payload.get("include_template_chapters", True)
    try:
        min_frequency = max(int(min_frequency), 2)
    except (TypeError, ValueError):
        min_frequency = 2
    return min_frequency, bool(include_template_chapters)


def enqueue_chapter_pattern_mining(
    db: Session,
    *,
    kb_id: uuid.UUID,
    operator_id: str,
    min_frequency: int = 2,
    include_template_chapters: bool = True,
) -> ChapterPatternMiningTask:
    running = (
        db.query(ChapterPatternMiningTask)
        .filter(
            ChapterPatternMiningTask.kb_id == kb_id,
            ChapterPatternMiningTask.status.in_(
                [ChapterPatternMiningTaskStatus.pending, ChapterPatternMiningTaskStatus.running]
            ),
        )
        .first()
    )
    if running is not None:
        raise ChapterPatternMiningServiceError(
            "Chapter pattern mining is already in progress",
            code="MINING_IN_PROGRESS",
            status_code=409,
        )

    task = ChapterPatternMiningTask(
        kb_id=kb_id,
        status=ChapterPatternMiningTaskStatus.pending,
        result_summary={
            "requested_min_frequency": max(int(min_frequency), 2),
            "include_template_chapters": bool(include_template_chapters),
        },
        created_by=operator_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _mine_for_task(db: Session, task: ChapterPatternMiningTask) -> None:
    min_frequency, include_template_chapters = _extract_request_config(task)
    task.status = ChapterPatternMiningTaskStatus.running
    task.started_at = _now()
    task.finished_at = None
    task.error_message = None
    db.flush()

    outline_nodes = (
        db.query(BidOutlineNode)
        .filter(BidOutlineNode.kb_id == task.kb_id)
        .order_by(BidOutlineNode.created_at.asc())
        .all()
    )
    template_chapters: list[TemplateChapter] = []
    if include_template_chapters:
        template_chapters = (
            db.query(TemplateChapter)
            .filter(TemplateChapter.kb_id == task.kb_id, TemplateChapter.ignored.is_(False))
            .order_by(TemplateChapter.created_at.asc())
            .all()
        )

    outline_children: dict[uuid.UUID, list[str]] = defaultdict(list)
    for node in outline_nodes:
        if node.parent_id is None:
            continue
        normalized = normalize(node.title or "")
        if not normalized:
            continue
        outline_children[node.parent_id].append(node.title.strip())

    template_children: dict[uuid.UUID, list[str]] = defaultdict(list)
    for chapter in template_chapters:
        if chapter.parent_id is None:
            continue
        normalized = normalize(chapter.title or "")
        if not normalized:
            continue
        template_children[chapter.parent_id].append(chapter.title.strip())

    clusters: dict[tuple[str, str], dict[str, Any]] = {}

    def add_occurrence(
        *,
        chapter_taxonomy_id: uuid.UUID | None,
        title: str | None,
        source_outline_id: uuid.UUID | None,
        source_template_chapter_id: uuid.UUID | None,
        product_category_ids: list[Any] | None,
        child_titles: list[str] | None,
    ) -> None:
        normalized_title = normalize(title or "")
        if not normalized_title:
            return
        taxonomy_key = str(chapter_taxonomy_id) if chapter_taxonomy_id else "__none__"
        cluster_key = (taxonomy_key, normalized_title)
        cluster = clusters.setdefault(
            cluster_key,
            {
                "pattern_name": (title or "").strip() or normalized_title,
                "chapter_taxonomy_id": chapter_taxonomy_id,
                "source_outline_ids": set(),
                "source_template_chapter_ids": set(),
                "product_category_ids": set(),
                "child_counter": Counter(),
                "frequency": 0,
            },
        )
        cluster["frequency"] += 1
        if source_outline_id:
            cluster["source_outline_ids"].add(str(source_outline_id))
        if source_template_chapter_id:
            cluster["source_template_chapter_ids"].add(str(source_template_chapter_id))
        for category_id in product_category_ids or []:
            cluster["product_category_ids"].add(str(category_id))
        for child_title in child_titles or []:
            normalized_child = normalize(child_title)
            if not normalized_child:
                continue
            cluster["child_counter"][child_title.strip()] += 1

    for node in outline_nodes:
        add_occurrence(
            chapter_taxonomy_id=node.chapter_taxonomy_id,
            title=node.title,
            source_outline_id=node.bid_outline_id,
            source_template_chapter_id=None,
            product_category_ids=node.product_category_ids or [],
            child_titles=outline_children.get(node.outline_node_id, []),
        )

    for chapter in template_chapters:
        add_occurrence(
            chapter_taxonomy_id=chapter.chapter_taxonomy_id,
            title=chapter.title,
            source_outline_id=None,
            source_template_chapter_id=chapter.template_chapter_id,
            product_category_ids=chapter.product_category_ids or [],
            child_titles=template_children.get(chapter.template_chapter_id, []),
        )

    patterns_created = 0
    for cluster in clusters.values():
        if int(cluster["frequency"]) < min_frequency:
            continue
        common_child_chapters = [
            title
            for title, count in cluster["child_counter"].most_common()
            if count >= 2
        ]
        db.add(
            ChapterPattern(
                kb_id=task.kb_id,
                pattern_name=str(cluster["pattern_name"]),
                chapter_taxonomy_id=cluster["chapter_taxonomy_id"],
                product_category_ids=sorted(cluster["product_category_ids"]),
                common_child_chapters=common_child_chapters,
                source_outline_ids=sorted(cluster["source_outline_ids"]),
                source_template_chapter_ids=sorted(cluster["source_template_chapter_ids"]),
                frequency=int(cluster["frequency"]),
                status=ChapterPatternStatus.candidate,
                mining_task_id=task.mining_task_id,
            )
        )
        patterns_created += 1

    task.status = ChapterPatternMiningTaskStatus.completed
    task.finished_at = _now()
    task.result_summary = {
        "patterns_created": patterns_created,
        "clusters_scanned": len(clusters),
        "min_frequency": min_frequency,
        "include_template_chapters": include_template_chapters,
    }
    db.commit()


def run_chapter_pattern_mining_once(db: Session) -> bool:
    task = (
        db.query(ChapterPatternMiningTask)
        .filter(ChapterPatternMiningTask.status == ChapterPatternMiningTaskStatus.pending)
        .order_by(ChapterPatternMiningTask.created_at.asc())
        .first()
    )
    if task is None:
        return False
    try:
        _mine_for_task(db, task)
    except Exception as exc:
        task.status = ChapterPatternMiningTaskStatus.failed
        task.error_message = str(exc)
        task.finished_at = _now()
        db.commit()
    return True


def run_chapter_pattern_mining_pending(db: Session) -> None:
    while run_chapter_pattern_mining_once(db):
        pass


def run_chapter_pattern_mining_in_new_session() -> None:
    try:
        db = SessionLocal()
    except Exception:
        return
    try:
        run_chapter_pattern_mining_pending(db)
    except Exception:
        db.rollback()
    finally:
        db.close()
