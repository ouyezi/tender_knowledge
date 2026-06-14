from uuid import UUID

from fastapi.testclient import TestClient

from src.main import app
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.chapter_pattern import ChapterPattern
from src.models.chapter_pattern_mining_task import (
    ChapterPatternMiningTask,
    ChapterPatternMiningTaskStatus,
)
from src.models.document import Document, DocumentSourceType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateType
from src.models.template_chapter import TemplateChapter
from src.services.chapter_pattern_miner import run_chapter_pattern_mining_pending


def _seed_outline_and_template_chapters(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="mining-source.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path=f"{seeded_kb.kb_id}/mining-source.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="mining-source.docx",
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="测试目录",
        created_by="admin",
    )
    db_session.add(outline)
    db_session.flush()

    node_a = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=["pc-a"],
    )
    node_b = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=1,
        product_category_ids=["pc-b"],
    )
    db_session.add_all([node_a, node_b])
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=file_import.import_id,
        template_name="模板A",
        template_type=TemplateType.technical_bid,
        created_by="admin",
    )
    db_session.add(template)
    db_session.flush()

    template_chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=["pc-c"],
    )
    db_session.add(template_chapter)
    db_session.commit()


def test_chapter_pattern_mining_task_and_listing(api_client, db_session, seeded_kb):
    client = TestClient(app)
    _seed_outline_and_template_chapters(db_session, seeded_kb)

    trigger = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/chapter-patterns/mine",
        headers={"X-Operator-Id": "admin"},
        json={"min_frequency": 2, "include_template_chapters": True},
    )
    assert trigger.status_code == 202
    mining_task_id = UUID(trigger.json()["data"]["mining_task_id"])
    run_chapter_pattern_mining_pending(db_session)

    detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/chapter-patterns/mine/tasks/{mining_task_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    task_payload = detail.json()["data"]
    assert task_payload["status"] in {"pending", "running", "completed"}

    db_task = (
        db_session.query(ChapterPatternMiningTask)
        .filter(ChapterPatternMiningTask.mining_task_id == mining_task_id)
        .one()
    )
    assert db_task.status in {
        ChapterPatternMiningTaskStatus.pending,
        ChapterPatternMiningTaskStatus.running,
        ChapterPatternMiningTaskStatus.completed,
    }

    pattern_rows = db_session.query(ChapterPattern).filter(ChapterPattern.kb_id == seeded_kb.kb_id).all()
    assert len(pattern_rows) >= 1
    assert any(row.pattern_name == "技术方案" for row in pattern_rows)
    assert any(row.frequency >= 2 for row in pattern_rows)

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/chapter-patterns",
        headers={"X-Operator-Id": "admin"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert any(item["pattern_name"] == "技术方案" for item in items)
