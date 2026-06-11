import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ClassificationType(str, enum.Enum):
    product_category = "product_category"
    chapter_taxonomy = "chapter_taxonomy"


class ReferenceObjectType(str, enum.Enum):
    ku = "ku"
    wiki = "wiki"
    template = "template"
    template_chapter = "template_chapter"
    bid_outline = "bid_outline"
    manual_asset = "manual_asset"
    candidate_knowledge = "candidate_knowledge"
    file_import = "file_import"


class ClassificationReference(Base):
    __tablename__ = "classification_references"
    __table_args__ = (
        Index(
            "ix_classification_refs_lookup",
            "kb_id",
            "classification_type",
            "classification_id",
            "object_type",
        ),
    )

    reference_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    classification_type: Mapped[ClassificationType] = mapped_column(
        Enum(ClassificationType), nullable=False
    )
    classification_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    object_type: Mapped[ReferenceObjectType] = mapped_column(
        Enum(ReferenceObjectType), nullable=False
    )
    object_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
