from unittest.mock import patch
from uuid import uuid4

import pytest

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.services.knowledge.entry_tree_refine_service import (
    EntryTreeRefineError,
    _batch_nodes,
    _compact_change_to_patch,
    _merge_outline_nodes,
    _parse_llm_outline_response,
    _partition_nodes_by_section_no,
    refine_entry_document_tree,
)


def test_batch_nodes_splits_by_size():
    nodes = [
        {"node_id": "n1", "title": "A"},
        {"node_id": "n2", "title": "B"},
        {"node_id": "n3", "title": "C"},
    ]
    assert _batch_nodes(nodes, batch_size=2) == [
        [{"node_id": "n1", "title": "A"}, {"node_id": "n2", "title": "B"}],
        [{"node_id": "n3", "title": "C"}],
    ]


def test_partition_nodes_by_section_no():
    nodes = [
        {"node_id": "n1", "title": "评分索引表10", "level": 3, "parent_id": None, "sort_order": 0},
        {"node_id": "n2", "title": "1投标函11", "level": 3, "parent_id": None, "sort_order": 1},
    ]
    numbered, targets = _partition_nodes_by_section_no(nodes)
    assert len(numbered) == 1 and numbered[0]["node_id"] == "n2"
    assert len(targets) == 1 and targets[0]["node_id"] == "n1"


def test_merge_outline_nodes_ignores_title_changes():
    outline = {
        "nodes": [{"node_id": "n1", "title": "1投标函11", "level": 3, "parent_id": None, "sort_order": 0}]
    }
    refined = [{"node_id": "n1", "title": "投标函", "level": 1, "parent_id": None, "sort_order": 0}]
    merged = _merge_outline_nodes(outline, refined, preserve_titles=True)
    assert merged["nodes"][0]["title"] == "1投标函11"
    assert merged["nodes"][0]["level"] == 1


def test_parse_llm_outline_response_applies_structure_only_changes():
    base_nodes = {
        "n1": {
            "node_id": "n1",
            "title": "评分索引表10",
            "level": 3,
            "parent_id": None,
            "sort_order": 0,
        }
    }
    nodes, summary = _parse_llm_outline_response(
        '{"changes":[["n1",null,1,null,0]],"summary":"调层级"}',
        known_node_ids={"n1"},
        base_nodes=base_nodes,
        structure_only=True,
    )
    assert summary == "调层级"
    assert nodes == [
        {
            "node_id": "n1",
            "level": 1,
            "parent_id": None,
            "sort_order": 0,
        }
    ]


def test_parse_llm_outline_response_ignores_unknown_change_ids():
    nodes, summary = _parse_llm_outline_response(
        '{"changes":[["missing",null,1,null,0]],"summary":"x"}',
        known_node_ids={"n1"},
        base_nodes={"n1": {"node_id": "n1", "title": "x", "level": 1, "parent_id": None, "sort_order": 0}},
    )
    assert summary == "x"
    assert nodes == []


def test_parse_llm_outline_response_rejects_missing_changes():
    with pytest.raises(EntryTreeRefineError):
        _parse_llm_outline_response(
            '{"nodes":[["n1","章节",1,null,0]],"change_summary":"x"}',
            known_node_ids={"n1"},
        )


def test_compact_change_to_patch_ignores_invalid_parent():
    base_nodes = {
        "n1": {"node_id": "n1", "title": "父", "level": 1, "parent_id": None, "sort_order": 0},
        "n2": {"node_id": "n2", "title": "子", "level": 2, "parent_id": "n1", "sort_order": 1},
    }
    patch = _compact_change_to_patch(
        ["n2", None, None, "missing", None],
        known_node_ids={"n1", "n2"},
        base_nodes=base_nodes,
    )
    assert patch == {
        "node_id": "n2",
        "level": 2,
        "parent_id": None,
        "sort_order": 1,
    }


def test_refine_entry_document_tree_falls_back_when_llm_returns_none(db_session, seeded_kb, tmp_path, monkeypatch):
    from src.services.doc_chunk.outline_store import persist_outline, persist_outline_node_map
    from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType

    doc_id = uuid4()
    import_id = uuid4()
    node_id = uuid4()
    db_session.add(
        Document(
            document_id=doc_id,
            kb_id=seeded_kb.kb_id,
            import_id=import_id,
            document_name="demo.docx",
            source_type=DocumentSourceType.actual_bid,
            parse_status=DocumentParseStatus.ready,
            tree_version=1,
        )
    )
    db_session.add(
        DocumentTreeNode(
            node_id=node_id,
            kb_id=seeded_kb.kb_id,
            document_id=doc_id,
            parent_id=None,
            node_type=DocumentTreeNodeType.heading,
            title="评分索引表10",
            level=1,
            sort_order=1,
            tree_version=1,
        )
    )
    db_session.flush()

    outline_payload = {
        "schema_version": "1.0",
        "nodes": [
            {
                "node_id": "n1",
                "title": "评分索引表10",
                "level": 3,
                "parent_id": None,
                "sort_order": 1,
            }
        ],
    }
    persist_outline(document_id=doc_id, outline_payload=outline_payload, storage_root=tmp_path)
    persist_outline_node_map(
        document_id=doc_id,
        outline_node_to_tree_id={"n1": node_id},
        storage_root=tmp_path,
    )

    monkeypatch.setattr("src.services.knowledge.entry_tree_refine_service.load_outline", lambda **_: outline_payload)
    monkeypatch.setattr(
        "src.services.knowledge.entry_tree_refine_service.load_outline_node_map",
        lambda **_: {"n1": node_id},
    )
    monkeypatch.setattr(
        "src.services.knowledge.entry_tree_refine_service.repair_document_tree_headings",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr("src.services.knowledge.entry_tree_refine_service.is_llm_available", lambda: True)

    with patch("src.services.knowledge.entry_tree_refine_service.chat_completion", return_value=None) as mock_chat:
        result = refine_entry_document_tree(db_session, kb_id=seeded_kb.kb_id, doc_id=doc_id)

    mock_chat.assert_called_once()
    assert mock_chat.call_args.kwargs["model"] == "qwen-plus"
    assert result["engine"] == "repair"
    assert result["llm_updated_nodes"] == 0
    assert "目录修复" in result["change_summary"]
