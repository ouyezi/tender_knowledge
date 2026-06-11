from src.db.session import Base, engine
from src.models import (  # noqa: F401
    audit_log,
    chapter_taxonomy,
    classification_reference,
    kb_clone_log,
    knowledge_base,
    product_category,
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
