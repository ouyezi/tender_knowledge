from sqlalchemy import text

from src.db.session import Base, engine
from src.models.classification_reference import ReferenceObjectType
from src.models import (  # noqa: F401
    audit_log,
    candidate_knowledge_stub,
    chapter_taxonomy,
    classification_reference,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
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
        _sync_missing_columns(conn)
