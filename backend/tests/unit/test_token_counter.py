from __future__ import annotations

from src.services.knowledge.token_counter import count_tokens


def test_count_tokens_empty():
    assert count_tokens("") == 0
    assert count_tokens("   ") == 0


def test_count_tokens_chinese_text():
    assert count_tokens("知识库管理系统") == 7


def test_count_tokens_mixed_chinese_and_english():
    assert count_tokens("知识库 knowledge base") == 5


def test_count_tokens_english_words():
    assert count_tokens("hello world test") == 3
