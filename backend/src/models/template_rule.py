import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateRuleType(str, enum.Enum):
    required = "required"
    optional = "optional"
    product_match = "product_match"
    conditional = "conditional"
    mutex = "mutex"
    asset_reserved = "asset_reserved"


class TemplateRuleAction(str, enum.Enum):
    enable = "enable"
    disable = "disable"
    warn = "warn"
    require_asset = "require_asset"


class TemplateRuleStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class TemplateRule(Base):
    __tablename__ = "template_rules"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=False
    )
    template_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_chapters.template_chapter_id"), nullable=True
    )
    rule_type: Mapped[TemplateRuleType] = mapped_column(Enum(TemplateRuleType), nullable=False)
    condition: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    action: Mapped[TemplateRuleAction] = mapped_column(
        Enum(TemplateRuleAction), nullable=False, default=TemplateRuleAction.enable
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TemplateRuleStatus] = mapped_column(
        Enum(TemplateRuleStatus), nullable=False, default=TemplateRuleStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
