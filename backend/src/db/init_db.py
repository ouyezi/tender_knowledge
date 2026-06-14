from sqlalchemy import text

from src.db.session import Base, engine
from src.models.bid_outline import BidOutlineExtractStrategy
from src.models.candidate_confirm_audit_log import CandidateConfirmAuditAction
from src.models.candidate_knowledge import CandidateKnowledgeStatus, CandidateKnowledgeType
from src.models.candidate_knowledge_stub import CandidateKnowledgeStubStatus
from src.models.classification_reference import ReferenceObjectType
from src.models.import_audit_log import ImportAuditAction
from src.models import (  # noqa: F401
    actual_bid_audit_log,
    actual_bid_parse_task,
    audit_log,
    bid_outline,
    bid_outline_node,
    bid_outline_structure_diff,
    candidate_confirm_audit_log,
    candidate_knowledge,
    candidate_knowledge_stub,
    chapter_pattern,
    chapter_pattern_mining_task,
    chapter_taxonomy,
    classification_reference,
    document,
    document_parse_suggestion,
    document_tree_node,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
    knowledge_unit,
    manual_asset,
    product_category,
    template,
    template_audit_log,
    template_chapter,
    template_library,
    template_material,
    template_parse_suggestion,
    template_parse_task,
    template_publish_snapshot,
    template_rule,
    template_structure_diff,
    template_variable,
    wiki,
)


def _sync_postgres_enum(conn, type_name: str, values: list[str]) -> None:
    rows = conn.execute(
        text(
            "SELECT enumlabel FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = :type_name"
        ),
        {"type_name": type_name},
    )
    existing = {row[0] for row in rows}
    for value in values:
        if value in existing:
            continue
        conn.execute(text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'"))
        existing.add(value)


def _sync_missing_columns(conn) -> None:
    conn.execute(
        text(
            "ALTER TABLE template_parse_tasks "
            "ADD COLUMN IF NOT EXISTS llm_progress JSONB"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE import_audit_logs "
            "ALTER COLUMN import_id DROP NOT NULL"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE import_audit_logs "
            "DROP CONSTRAINT IF EXISTS import_audit_logs_import_id_fkey"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE import_audit_logs "
            "ADD CONSTRAINT import_audit_logs_import_id_fkey "
            "FOREIGN KEY (import_id) REFERENCES file_imports(import_id) "
            "ON DELETE SET NULL"
        )
    )
    for stmt in (
        "ALTER TABLE candidate_knowledge_stubs "
        "ADD COLUMN IF NOT EXISTS suggested_knowledge_type VARCHAR(64)",
        "ALTER TABLE candidate_knowledge_stubs "
        "ADD COLUMN IF NOT EXISTS suggestion_source VARCHAR(16)",
        "ALTER TABLE candidate_knowledge_stubs "
        "ADD COLUMN IF NOT EXISTS classification_confidence DOUBLE PRECISION",
        "ALTER TABLE candidate_knowledge_stubs "
        "ADD COLUMN IF NOT EXISTS chunk_ref VARCHAR(256)",
    ):
        conn.execute(text(stmt))


def _sync_epic4_columns(conn) -> None:
    """Add Epic 4 confirm-workbench columns to existing PostgreSQL tables."""
    candidate_epic4_columns = (
        "confirmed_object_type VARCHAR(64)",
        "confirmed_object_id UUID",
        "searchable BOOLEAN",
        "usage_hint VARCHAR(256)",
        "review_comment TEXT",
        "merged_into_id UUID",
        "split_from_id UUID",
        "lineage JSONB DEFAULT '{}'::jsonb",
        "last_publish_error TEXT",
        "publish_attempt_count INTEGER DEFAULT 0",
        "updated_by VARCHAR(128)",
    )
    for column in candidate_epic4_columns:
        conn.execute(
            text(f"ALTER TABLE candidate_knowledges ADD COLUMN IF NOT EXISTS {column}")
        )

    stub_epic4_columns = (
        "epic4_batch_id UUID",
        "confirmed_object_type VARCHAR(64)",
        "confirmed_object_id UUID",
        "searchable BOOLEAN",
        "usage_hint VARCHAR(256)",
        "review_comment TEXT",
        "merged_into_id UUID",
        "split_from_id UUID",
        "lineage JSONB DEFAULT '{}'::jsonb",
        "last_publish_error TEXT",
        "publish_attempt_count INTEGER DEFAULT 0",
        "updated_by VARCHAR(128)",
    )
    for column in stub_epic4_columns:
        conn.execute(
            text(f"ALTER TABLE candidate_knowledge_stubs ADD COLUMN IF NOT EXISTS {column}")
        )

    conn.execute(
        text(
            "UPDATE candidate_knowledges SET lineage = '{}'::jsonb "
            "WHERE lineage IS NULL"
        )
    )
    conn.execute(
        text(
            "UPDATE candidate_knowledge_stubs SET lineage = '{}'::jsonb "
            "WHERE lineage IS NULL"
        )
    )
    conn.execute(
        text(
            "UPDATE candidate_knowledges SET publish_attempt_count = 0 "
            "WHERE publish_attempt_count IS NULL"
        )
    )
    conn.execute(
        text(
            "UPDATE candidate_knowledge_stubs SET publish_attempt_count = 0 "
            "WHERE publish_attempt_count IS NULL"
        )
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        _sync_postgres_enum(
            conn,
            "referenceobjecttype",
            [member.value for member in ReferenceObjectType],
        )
        _sync_postgres_enum(
            conn,
            "importauditaction",
            [member.value for member in ImportAuditAction],
        )
        _sync_postgres_enum(
            conn,
            "bidoutlineextractstrategy",
            [member.value for member in BidOutlineExtractStrategy],
        )
        _sync_postgres_enum(
            conn,
            "candidateknowledgetype",
            [member.value for member in CandidateKnowledgeType],
        )
        _sync_postgres_enum(
            conn,
            "candidateknowledgestatus",
            [member.value for member in CandidateKnowledgeStatus],
        )
        _sync_postgres_enum(
            conn,
            "candidateknowledgestubstatus",
            [member.value for member in CandidateKnowledgeStubStatus],
        )
        _sync_postgres_enum(
            conn,
            "candidateconfirmauditaction",
            [member.value for member in CandidateConfirmAuditAction],
        )
        _sync_missing_columns(conn)
        _sync_epic4_columns(conn)
