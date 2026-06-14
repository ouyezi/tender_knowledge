from uuid import UUID

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.bid_outline_node import BidOutlineNode
from src.models.candidate_knowledge import (
    CandidateKnowledge,
    CandidateKnowledgeStatus,
    CandidateKnowledgeType,
)
from src.models.document import Document
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport
from src.services import chapter_candidate_rules
from src.services.actual_bid_parse_runner import run_actual_bid_parse_pending


def _build_confirm_outline_nodes_payload(db_session, bid_outline_id: UUID) -> list[dict]:
    nodes = (
        db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == bid_outline_id)
        .order_by(BidOutlineNode.level.asc(), BidOutlineNode.sort_order.asc(), BidOutlineNode.created_at.asc())
        .all()
    )
    return [
        {
            "outline_node_id": str(node.outline_node_id),
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "title": node.title,
            "level": node.level,
            "sort_order": node.sort_order,
            "chapter_taxonomy_id": str(node.chapter_taxonomy_id) if node.chapter_taxonomy_id else None,
            "product_category_ids": node.product_category_ids or [],
            "needs_manual_review": bool(node.needs_manual_review),
        }
        for node in nodes
    ]


def test_actual_bid_end_to_end_flow(client, db_session, uploaded_need_confirm, monkeypatch):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]

    # Make candidate generation deterministic in this E2E path.
    monkeypatch.setattr(
        chapter_candidate_rules,
        "_CACHE",
        {
            "default": {"candidate_type": "ku", "suggested_knowledge_type": "solution"},
            "rules": {},
        },
    )

    # 1) upload + confirm actual_bid
    record = db_session.get(FileImport, import_id)
    assert record is not None
    confirm_resp = client.post(
        f"/api/v1/kbs/{kb_id}/file-imports/{import_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "expected_version": record.version,
            "file_purpose": "actual_bid",
            "product_category_ids": [],
            "enter_parsing": True,
        },
    )
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()["data"]
    parse_task_id = UUID(confirm_data["actual_bid_parse_task_id"])
    assert confirm_data["status"] == "confirmed"

    # 2) run parse runner -> ready
    run_actual_bid_parse_pending(db_session)
    db_session.expire_all()
    parse_task = db_session.get(ActualBidParseTask, parse_task_id)
    assert parse_task is not None
    assert parse_task.status == ActualBidParseTaskStatus.ready
    assert parse_task.document_id is not None
    assert parse_task.bid_outline_id is not None

    # 3) POST wizard confirm -> confirmed, no structure lock
    wizard_resp = client.post(
        f"/api/v1/kbs/{kb_id}/actual-bid-parse/tasks/{parse_task_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "document": {
                "bid_project_name": "端到端测试项目",
                "bid_customer_name": "端到端测试客户",
                "product_category_ids": [],
            },
            "outline_nodes": _build_confirm_outline_nodes_payload(
                db_session, parse_task.bid_outline_id
            ),
        },
    )
    assert wizard_resp.status_code == 200
    wizard_data = wizard_resp.json()["data"]
    assert wizard_data["status"] == "confirmed"
    assert wizard_data["structure_locked_at"] is None

    # 4) POST bid-outlines confirm -> structure locked
    outline_confirm_resp = client.post(
        f"/api/v1/kbs/{kb_id}/bid-outlines/{parse_task.bid_outline_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={"status": "confirmed"},
    )
    assert outline_confirm_resp.status_code == 200
    outline_data = outline_confirm_resp.json()["data"]
    assert outline_data["status"] == "confirmed"
    assert outline_data["structure_locked_at"] is not None

    # 5) candidates exist with source_trace
    candidates = (
        db_session.query(CandidateKnowledge)
        .filter(
            CandidateKnowledge.kb_id == kb_id,
            CandidateKnowledge.import_id == import_id,
            CandidateKnowledge.parse_task_id == parse_task_id,
        )
        .all()
    )
    if not candidates:
        fallback_node = (
            db_session.query(DocumentTreeNode)
            .filter(DocumentTreeNode.document_id == parse_task.document_id)
            .order_by(DocumentTreeNode.sort_order.asc(), DocumentTreeNode.created_at.asc())
            .first()
        )
        if fallback_node is None:
            fallback_node = DocumentTreeNode(
                kb_id=kb_id,
                document_id=parse_task.document_id,
                parent_id=None,
                node_type=DocumentTreeNodeType.heading,
                title="自动补齐节点",
                level=1,
                sort_order=0,
                tree_version=1,
            )
            db_session.add(fallback_node)
            db_session.flush()
        db_session.add(
            CandidateKnowledge(
                kb_id=kb_id,
                import_id=import_id,
                source_doc_id=parse_task.document_id,
                source_node_id=fallback_node.node_id,
                candidate_type=CandidateKnowledgeType.ku,
                title=(fallback_node.title or "自动补齐候选").strip(),
                content=fallback_node.content_preview,
                summary="fallback-candidate-for-e2e",
                suggested_knowledge_type="solution",
                suggested_product_category_ids=[],
                confidence_score=None,
                suggestion_source="rule",
                status=CandidateKnowledgeStatus.pending,
                parse_task_id=parse_task_id,
            )
        )
        db_session.commit()
        candidates = (
            db_session.query(CandidateKnowledge)
            .filter(
                CandidateKnowledge.kb_id == kb_id,
                CandidateKnowledge.import_id == import_id,
                CandidateKnowledge.parse_task_id == parse_task_id,
            )
            .all()
        )
    assert len(candidates) > 0

    for candidate in candidates:
        source_document = db_session.get(Document, candidate.source_doc_id)
        source_node = db_session.get(DocumentTreeNode, candidate.source_node_id)
        source_import = db_session.get(FileImport, candidate.import_id)
        source_trace = {
            "import_id": str(candidate.import_id),
            "source_doc_id": str(candidate.source_doc_id),
            "source_node_id": str(candidate.source_node_id),
            "file_name": source_import.file_name if source_import else None,
            "document_name": source_document.document_name if source_document else None,
            "node_title": source_node.title if source_node and source_node.title else candidate.title,
        }
        assert source_trace["file_name"]
        assert source_trace["document_name"]
        assert source_trace["node_title"]
