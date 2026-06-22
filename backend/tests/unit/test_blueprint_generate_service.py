from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.knowledge.blueprint_generate_service import (
    BlueprintGenerateFailedError,
    BlueprintGenerateTimeoutError,
    NoChildNodesError,
    _chat_with_timeout,
    _estimate_max_tokens,
    generate_blueprint_draft,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"

MOCK_LLM_JSON = {
    "outline_title": "供应链方案通用大纲",
    "overall_strategy": "强调仓配能力",
    "usual_page_range": "5-8页",
    "related_regulations": ["ISO9001"],
    "common_mistakes": "忽视应急预案",
    "template_style": "formal",
    "nodes": [
        {
            "node_title": "总体设计",
            "node_level": 1,
            "children": [],
            "purpose": "p",
            "writing_goal": "g",
            "writing_hint": "h",
            "required_flag": True,
            "recommended_flag": False,
            "content_type": "text",
            "keyword_hint": ["供应链"],
        }
    ],
}


def _seed_file_import(db_session, kb_id):
    row = FileImport(
        kb_id=kb_id,
        file_name="blueprint-generate.docx",
        file_type=FileType.docx,
        file_size=2048,
        storage_path="/tmp/blueprint-generate.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _seed_document_tree(db_session, kb_id):
    file_import = _seed_file_import(db_session, kb_id)
    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="blueprint-generate.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    root_id = uuid4()
    leaf_id = uuid4()
    root = DocumentTreeNode(
        node_id=root_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="第一章 总体方案",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    leaf = DocumentTreeNode(
        node_id=leaf_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=root_id,
        node_type=DocumentTreeNodeType.heading,
        title="1.1 子章节",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    db_session.add_all([root, leaf])
    db_session.commit()
    return document, root, leaf


def test_generate_maps_importance_and_node_code(db_session, seeded_kb, monkeypatch):
    document, root, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **kw: json.dumps(MOCK_LLM_JSON, ensure_ascii=False),
    )

    result = generate_blueprint_draft(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=root.node_id,
    )

    assert result["name"] == "供应链方案通用大纲"
    assert result["nodes"][0]["node_title"] == "第一章 总体方案"
    assert result["nodes"][0]["node_level"] == 1
    assert result["nodes"][0]["node_code"] == "1"
    assert result["nodes"][0]["children"][0]["importance_level"] == "required"
    assert result["nodes"][0]["children"][0]["node_code"] == "1.1"
    assert result["source_chapter_title"] == "第一章 总体方案"
    assert result["source_doc_id"] == str(document.document_id)
    assert result["source_node_id"] == str(root.node_id)


def test_estimate_max_tokens_scales_with_subtree_size():
    assert _estimate_max_tokens(subtree_node_count=6) == 2792
    assert _estimate_max_tokens(subtree_node_count=100) == 20480


MOCK_LLM_JSON_V11 = {
    **MOCK_LLM_JSON,
    "suggested_structure_md": "## 技术方案模块\n- 映射：1.1 技术方案",
    "nodes": [
        {
            **MOCK_LLM_JSON["nodes"][0],
            "content_description": "描述总体架构与部署方式。",
            "tender_response_hint": "需响应技术规格书中的架构要求。",
        }
    ],
}


def test_generate_returns_generation_extraction_fields(db_session, seeded_kb, monkeypatch):
    document, root, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **kw: json.dumps(MOCK_LLM_JSON_V11, ensure_ascii=False),
    )

    result = generate_blueprint_draft(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=root.node_id,
    )

    assert result["suggested_structure_md"].startswith("## 技术方案")
    root_node = result["nodes"][0]
    child = root_node["children"][0]
    assert child["content_description"] == "描述总体架构与部署方式。"
    assert child["tender_response_hint"] == "需响应技术规格书中的架构要求。"


def test_wraps_mid_level_llm_nodes_under_source_root(db_session, seeded_kb, monkeypatch):
    document, root, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **kw: json.dumps(
            {
                "outline_title": "企业资质",
                "nodes": [
                    {
                        "node_title": "2.1子章节",
                        "node_level": 3,
                        "children": [],
                        "required_flag": True,
                        "recommended_flag": False,
                    },
                    {
                        "node_title": "2.2子章节",
                        "node_level": 3,
                        "children": [],
                        "required_flag": False,
                        "recommended_flag": True,
                    },
                ],
            },
            ensure_ascii=False,
        ),
    )

    result = generate_blueprint_draft(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=root.node_id,
    )

    assert result["nodes"][0]["node_title"] == "第一章 总体方案"
    assert result["nodes"][0]["node_level"] == 1
    assert len(result["nodes"][0]["children"]) == 2
    assert result["nodes"][0]["children"][0]["node_level"] == 2
    assert result["nodes"][0]["children"][0]["node_code"] == "1.1"


def test_generate_rejects_when_llm_not_configured(db_session, seeded_kb, monkeypatch):
    document, root, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr("src.services.knowledge.blueprint_generate_service.settings.llm_api_key", None)

    with pytest.raises(BlueprintGenerateFailedError, match="llm not configured"):
        generate_blueprint_draft(
            db_session,
            kb_id=seeded_kb.kb_id,
            doc_id=document.document_id,
            node_id=root.node_id,
        )


def test_generate_rejects_leaf_node(db_session, seeded_kb):
    document, _, leaf = _seed_document_tree(db_session, seeded_kb.kb_id)

    with pytest.raises(NoChildNodesError):
        generate_blueprint_draft(
            db_session,
            kb_id=seeded_kb.kb_id,
            doc_id=document.document_id,
            node_id=leaf.node_id,
        )


def test_generate_failed_on_bad_json(db_session, seeded_kb, monkeypatch):
    document, root, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **kw: "not-json",
    )

    with pytest.raises(BlueprintGenerateFailedError):
        generate_blueprint_draft(
            db_session,
            kb_id=seeded_kb.kb_id,
            doc_id=document.document_id,
            node_id=root.node_id,
        )


def test_chat_with_timeout_raises_on_direct_timeout(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("urllib.request.urlopen", _raise_timeout)

    with pytest.raises(BlueprintGenerateTimeoutError):
        _chat_with_timeout(system_prompt="s", user_prompt="u", max_tokens=1024)
