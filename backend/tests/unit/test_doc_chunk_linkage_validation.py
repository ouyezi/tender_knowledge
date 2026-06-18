# backend/tests/unit/test_doc_chunk_linkage_validation.py
from src.services.doc_chunk.linkage_validation import (
    chunk_matches_outline_entry,
    titles_compatible,
)


def test_titles_compatible_ignores_punctuation_and_spaces():
    assert titles_compatible("（六）承诺书", "承诺书")
    assert titles_compatible("1. 技术方案", "技术方案")


def test_titles_compatible_rejects_unrelated():
    assert not titles_compatible("承诺书", "领取招标文件")


def test_titles_compatible_strips_list_number_prefix():
    assert titles_compatible(
        "总公司授权分支机构参与项目投标授权书",
        "1.总公司授权分支机构参与项目投标授权书",
    )


def test_chunk_matches_outline_entry_requires_original_node_id():
    assert chunk_matches_outline_entry(
        outline_node_id="n1",
        chunk_payload={"original_node_ids": ["n1"]},
    )
    assert not chunk_matches_outline_entry(
        outline_node_id="n1",
        chunk_payload={"original_node_ids": ["n2"]},
    )
