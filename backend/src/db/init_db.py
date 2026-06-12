from src.db.session import Base, engine
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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
