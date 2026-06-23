import hashlib

from src.models.image_extraction_cache import ImageExtractionCache
from src.services.knowledge.image_extraction_cache_service import (
    compute_file_md5,
    get_or_create_extraction,
)


def test_compute_file_md5(tmp_path):
    path = tmp_path / "img.png"
    path.write_bytes(b"abc")
    assert compute_file_md5(path) == hashlib.md5(b"abc").hexdigest()


def test_get_or_create_extraction_cache_hit(db_session):
    row = ImageExtractionCache(
        md5_hash="abc123",
        caption="证书",
        ocr_text="ISO9001",
        extracted_facts={"confidence": "high"},
        vision_model="test",
    )
    db_session.add(row)
    db_session.commit()

    result = get_or_create_extraction(
        db_session,
        md5_hash="abc123",
        vision_fn=lambda: None,
        vision_model="test",
    )
    assert result["caption"] == "证书"
    assert result["from_cache"] is True
