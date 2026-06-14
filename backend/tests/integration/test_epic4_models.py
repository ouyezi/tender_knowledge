from uuid import uuid4

from src.models.candidate_confirm_audit_log import (
    CandidateConfirmAuditAction,
    CandidateConfirmAuditLog,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus


def test_create_knowledge_unit_with_candidate_source(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="epic4-ku-source.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{seeded_kb.kb_id}/epic4-ku-source.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    candidate_id = uuid4()
    ku = KnowledgeUnit(
        kb_id=seeded_kb.kb_id,
        title="云平台架构设计",
        content="正文",
        knowledge_type="solution",
        product_category_ids=[],
        import_id=file_import.import_id,
        candidate_id=candidate_id,
        published_by="admin",
        status=KnowledgeUnitStatus.published,
    )
    db_session.add(ku)
    db_session.add(
        CandidateConfirmAuditLog(
            kb_id=seeded_kb.kb_id,
            candidate_id=f"doc_{candidate_id}",
            action=CandidateConfirmAuditAction.publish,
            operator_id="admin",
            trace_id=uuid4(),
            detail={"confirm_as": "ku"},
        )
    )
    db_session.commit()
    assert ku.ku_id is not None
