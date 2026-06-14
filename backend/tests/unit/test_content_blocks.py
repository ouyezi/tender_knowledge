# backend/tests/unit/test_content_blocks.py
import json

from src.services.content_blocks import (
    blocks_v1,
    content_excerpt,
    parse_content,
)


def test_blocks_v1_serializes_paragraph():
    payload = blocks_v1([{"type": "paragraph", "text": "hello"}])
    parsed = json.loads(payload)
    assert parsed["format"] == "blocks_v1"
    assert parsed["blocks"][0]["text"] == "hello"


def test_content_excerpt_from_blocks():
    payload = blocks_v1(
        [
            {"type": "paragraph", "text": "第一段正文"},
            {"type": "table", "text": "A | B"},
        ]
    )
    assert content_excerpt(payload, max_len=10) == "第一段正文"


def test_content_excerpt_empty_blocks():
    assert content_excerpt(blocks_v1([]), max_len=120) == "（仅标题）"


def test_parse_content_plain_fallback():
    doc = parse_content("legacy plain text")
    assert doc.format == "plain"
    assert doc.plain_text == "legacy plain text"
