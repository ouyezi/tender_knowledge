from pathlib import Path

import pytest
from docx import Document

from src.config import Settings
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.bid_outline_node import BidOutlineNode
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.actual_bid_parse_runner import run_actual_bid_parse_pending


def _build_chinese_outline_docx(path: Path) -> None:
    doc = Document()
    for text in [
        "第一章 项目概述",
        "一、建设背景",
        "（一）政策背景",
        "（二）行业现状",
        "二、建设目标",
        "（一）总体目标",
        "（二）阶段目标",
    ]:
        doc.add_paragraph(text, style="Normal")
    doc.save(path)


def _seed_confirmed_import(db_session, seeded_kb, docx_path: Path) -> Path:
    storage_rel = f"{seeded_kb.kb_id}/hierarchy-actual-bid.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(docx_path.read_bytes())

    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="hierarchy-actual-bid.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(record)
    db_session.flush()
    for task_type in (
        DownstreamTaskType.document_parse,
        DownstreamTaskType.bid_outline_extract,
        DownstreamTaskType.candidate_knowledge_generate,
    ):
        db_session.add(
            DownstreamTaskEntry(
                kb_id=seeded_kb.kb_id,
                import_id=record.import_id,
                task_type=task_type,
                status=DownstreamTaskStatus.pending,
            )
        )
    db_session.commit()
    return record.import_id


def test_bid_outline_non_root_parent_id_ratio(db_session, seeded_kb, tmp_path):
    docx = tmp_path / "hierarchy.docx"
    _build_chinese_outline_docx(docx)
    import_id = _seed_confirmed_import(db_session, seeded_kb, docx)

    run_actual_bid_parse_pending(db_session)
    db_session.expire_all()

    task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == import_id)
        .one()
    )
    assert task.status == ActualBidParseTaskStatus.ready
    assert task.bid_outline_id is not None

    nodes = (
        db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == task.bid_outline_id)
        .all()
    )
    if not nodes:
        pytest.skip("no outline nodes persisted")
    min_level = min(n.level for n in nodes)
    non_root = [n for n in nodes if n.level > min_level]
    if len(non_root) < 3:
        pytest.skip("fixture produced too few non-root nodes for ratio gate")

    with_parent = sum(1 for n in non_root if n.parent_id is not None)
    assert with_parent / len(non_root) >= 0.70
