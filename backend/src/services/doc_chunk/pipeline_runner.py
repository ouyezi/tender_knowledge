from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from doc_chunk.api import run_pipeline

from src.config import Settings

_STAGE_MESSAGES = {
    "extract": "提取文档正文与图片",
    "outline": "生成目录树",
    "tree": "构建文档结构树",
    "chunk": "章节分块",
    "enrich": "章节分类与元数据",
    "outline_refine": "优化目录结构",
}


def run_doc_chunk_pipeline(
    docx_path: Path,
    workspace: Path,
    *,
    on_progress: Callable[[str, dict], None] | None = None,
) -> None:
    settings = Settings()

    def _wrapped(stage: str, payload: dict) -> None:
        if on_progress is None:
            return
        message = payload.get("message") or _STAGE_MESSAGES.get(stage, stage)
        on_progress(stage, {**payload, "message": message})

    promote_headings = settings.doc_chunk_promote_headings
    if promote_headings not in {"off", "auto"}:
        promote_headings = "auto"

    run_pipeline(
        docx_path,
        workspace,
        overwrite=True,
        skip_refine=True,
        skip_enrich=settings.doc_chunk_skip_enrich,
        promote_headings=promote_headings,  # type: ignore[arg-type]
        on_progress=_wrapped,
    )
