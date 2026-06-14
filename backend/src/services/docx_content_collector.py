from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.docx_block_reader import (
    iter_document_blocks,
    open_docx,
    paragraph_has_image,
    sanitize_block_text,
    table_text,
)


@dataclass
class RawBlock:
    index: int
    block_type: str
    text: str
    style_name: str | None
    has_image: bool


@dataclass
class CollectResult:
    blocks: list[RawBlock]


def collect_content(path: str | Path) -> CollectResult:
    file_path = Path(path)
    doc = open_docx(file_path)
    blocks: list[RawBlock] = []
    block_index = 0
    for block_type, block in iter_document_blocks(doc):
        if block_type == "paragraph":
            paragraph = block
            text = (paragraph.text or "").strip()
            has_image = paragraph_has_image(paragraph)
            if not text and not has_image:
                continue
            blocks.append(
                RawBlock(
                    index=block_index,
                    block_type="paragraph",
                    text=sanitize_block_text(text),
                    style_name=getattr(paragraph.style, "name", None),
                    has_image=has_image,
                )
            )
            block_index += 1
            continue
        if block_type == "table":
            text = table_text(block).strip()
            if not text:
                continue
            blocks.append(
                RawBlock(
                    index=block_index,
                    block_type="table",
                    text=sanitize_block_text(text),
                    style_name=None,
                    has_image=False,
                )
            )
            block_index += 1
            continue
        blocks.append(
            RawBlock(
                index=block_index,
                block_type="other",
                text=getattr(block, "tag", "unknown"),
                style_name=None,
                has_image=False,
            )
        )
        block_index += 1
    return CollectResult(blocks=blocks)
