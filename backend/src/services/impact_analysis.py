from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.classification_reference import ClassificationReference, ClassificationType


def get_report(
    db: Session,
    kb_id: UUID,
    classification_type: ClassificationType | str,
    classification_id: UUID,
) -> dict:
    if isinstance(classification_type, str):
        classification_type = ClassificationType(classification_type)

    rows = db.execute(
        select(
            ClassificationReference.object_type,
            func.count().label("count"),
        )
        .where(
            ClassificationReference.kb_id == kb_id,
            ClassificationReference.classification_type == classification_type,
            ClassificationReference.classification_id == classification_id,
        )
        .group_by(ClassificationReference.object_type)
    ).all()

    by_type = {row.object_type.value: row.count for row in rows}
    return {
        "classification_type": classification_type.value,
        "classification_id": str(classification_id),
        "total_count": sum(by_type.values()),
        "by_object_type": by_type,
    }
