from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.models.image_extraction_cache import ImageExtractionCache


def compute_file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def get_or_create_extraction(
    db: Session,
    *,
    md5_hash: str,
    vision_fn: Callable[[], dict[str, Any] | None],
    vision_model: str,
) -> dict[str, Any]:
    row = db.get(ImageExtractionCache, md5_hash)
    if row is not None:
        return {
            "caption": row.caption,
            "ocr_text": row.ocr_text,
            "extracted_facts": row.extracted_facts,
            "from_cache": True,
        }

    extracted = vision_fn()
    if extracted is None:
        return {
            "caption": None,
            "ocr_text": None,
            "extracted_facts": None,
            "from_cache": False,
        }

    row = ImageExtractionCache(
        md5_hash=md5_hash,
        caption=extracted.get("caption"),
        ocr_text=extracted.get("ocr_text"),
        extracted_facts=extracted.get("extracted_facts"),
        vision_model=vision_model,
    )
    db.add(row)
    db.flush()
    return {
        "caption": extracted.get("caption"),
        "ocr_text": extracted.get("ocr_text"),
        "extracted_facts": extracted.get("extracted_facts"),
        "from_cache": False,
    }
