from src.db.session import Base, engine
from src.models import (  # noqa: F401
    audit_log,
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
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
