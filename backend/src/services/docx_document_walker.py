from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time
from collections.abc import Callable

from src.services.docx_block_reader import open_docx
from src.services.docx_content_collector import collect_content
from src.services.docx_hierarchy_inferrer import InferResult, infer_hierarchy
from src.services.docx_tree_materializer import WalkedNode, materialize_walk_result

logger = logging.getLogger(__name__)


@dataclass
class DocumentWalkResult:
    nodes: list[WalkedNode]
    used_flat_fallback: bool = False
    needs_manual_review: bool = False
    infer_result: InferResult | None = None


def _iter_paragraph_texts_from_fallback(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def walk_document(
    path: str | Path,
    *,
    on_block_progress: Callable[[int], None] | None = None,
    block_progress_interval: int = 200,
) -> DocumentWalkResult:
    file_path = Path(path)
    file_size = file_path.stat().st_size if file_path.exists() else 0
    logger.info(
        "walk_document START path=%s size_mb=%.1f",
        file_path,
        file_size / (1024 * 1024),
    )
    started = time.perf_counter()

    try:
        logger.info("walk_document opening docx path=%s", file_path)
        open_started = time.perf_counter()
        open_docx(file_path)
        logger.info(
            "walk_document docx opened path=%s elapsed_ms=%d",
            file_path,
            int((time.perf_counter() - open_started) * 1000),
        )
    except Exception:
        logger.exception("walk_document docx open failed, using text fallback path=%s", file_path)
        fallback_started = time.perf_counter()
        fallback_texts = _iter_paragraph_texts_from_fallback(file_path)
        logger.info(
            "walk_document text fallback lines=%d elapsed_ms=%d path=%s",
            len(fallback_texts),
            int((time.perf_counter() - fallback_started) * 1000),
            file_path,
        )
        fallback_nodes = [
            WalkedNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=None,
                section_temp_id=None,
                node_type="paragraph",
                text=text,
                level=1,
                sort_order=idx,
                is_outline_node=False,
                needs_manual_review=True,
            )
            for idx, text in enumerate(fallback_texts)
        ]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.warning(
            "walk_document DONE via text_fallback nodes=%d elapsed_ms=%d path=%s",
            len(fallback_nodes),
            elapsed_ms,
            file_path,
        )
        return DocumentWalkResult(
            nodes=fallback_nodes,
            used_flat_fallback=True,
            needs_manual_review=True,
        )

    block_count = 0
    collected = collect_content(file_path)
    for _block in collected.blocks:
        block_count += 1
        if (
            on_block_progress is not None
            and block_progress_interval > 0
            and block_count % block_progress_interval == 0
        ):
            on_block_progress(block_count)

    inferred = infer_hierarchy(collected.blocks)
    materialized = materialize_walk_result(collected.blocks, inferred)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if materialized.used_flat_fallback:
        logger.warning(
            "walk_document DONE no_heading flat_fallback nodes=%d blocks=%d elapsed_ms=%d path=%s",
            len(materialized.nodes),
            block_count,
            elapsed_ms,
            file_path,
        )
    else:
        logger.info(
            "walk_document DONE nodes=%d blocks=%d elapsed_ms=%d path=%s",
            len(materialized.nodes),
            block_count,
            elapsed_ms,
            file_path,
        )
    return DocumentWalkResult(
        nodes=materialized.nodes,
        used_flat_fallback=materialized.used_flat_fallback,
        needs_manual_review=materialized.needs_manual_review,
        infer_result=inferred,
    )
