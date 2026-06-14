from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from src.services.docx_block_reader import (
    iter_document_blocks,
    open_docx,
    paragraph_has_image,
    table_text,
)


@dataclass(frozen=True)
class ExtractedImage:
    asset_id: UUID
    storage_path: str
    mime_type: str
    source_block_index: int


def extract_docx_images(
    docx_path: str | Path,
    *,
    storage_root: Path,
    kb_id: UUID,
    document_id: UUID,
) -> list[ExtractedImage]:
    file_path = Path(docx_path)
    doc = open_docx(file_path)
    extracted: list[ExtractedImage] = []
    block_index = 0

    for block_type, block in iter_document_blocks(doc):
        if block_type == "paragraph":
            paragraph = block
            text = (paragraph.text or "").strip()
            has_image = paragraph_has_image(paragraph)
            if not text and not has_image:
                continue
            if has_image:
                for run in paragraph.runs:
                    if "graphic" not in run._element.xml and "drawing" not in run._element.xml:
                        continue
                    blips = run._element.xpath(".//a:blip")
                    for blip in blips:
                        embed = blip.get(
                            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                        )
                        if not embed:
                            continue
                        try:
                            part = doc.part.related_parts[embed]
                        except KeyError:
                            continue
                        blob = part.blob
                        ext = mimetypes.guess_extension(part.content_type) or ".bin"
                        asset_id = uuid4()
                        rel_path = Path(str(kb_id)) / "media" / str(document_id) / f"{asset_id}{ext}"
                        abs_path = storage_root / rel_path
                        abs_path.parent.mkdir(parents=True, exist_ok=True)
                        abs_path.write_bytes(blob)
                        extracted.append(
                            ExtractedImage(
                                asset_id=asset_id,
                                storage_path=str(rel_path).replace("\\", "/"),
                                mime_type=part.content_type or "application/octet-stream",
                                source_block_index=block_index,
                            )
                        )
            block_index += 1
            continue

        if block_type == "table":
            if not table_text(block).strip():
                continue
            block_index += 1
            continue

        block_index += 1

    return extracted
