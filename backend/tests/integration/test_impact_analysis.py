import time
import uuid

from src.models.classification_reference import (
    ClassificationReference,
    ClassificationType,
    ReferenceObjectType,
)
from src.services import kb_service, product_category_service
from src.services.impact_analysis import get_report


def test_get_report_aggregates_by_object_type(db_session):
    kb = kb_service.create_kb(db_session, "impact-kb")
    category = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="福利产品",
        category_code="welfare",
    )

    for _ in range(5):
        db_session.add(
            ClassificationReference(
                kb_id=kb.kb_id,
                classification_type=ClassificationType.product_category,
                classification_id=category.category_id,
                object_type=ReferenceObjectType.ku,
                object_id=uuid.uuid4(),
            )
        )
    for _ in range(3):
        db_session.add(
            ClassificationReference(
                kb_id=kb.kb_id,
                classification_type=ClassificationType.product_category,
                classification_id=category.category_id,
                object_type=ReferenceObjectType.candidate_knowledge,
                object_id=uuid.uuid4(),
            )
        )
    db_session.commit()

    start = time.perf_counter()
    report = get_report(
        db_session,
        kb.kb_id,
        ClassificationType.product_category,
        category.category_id,
    )
    elapsed = time.perf_counter() - start

    assert report["total_count"] == 8
    assert report["by_object_type"]["ku"] == 5
    assert report["by_object_type"]["candidate_knowledge"] == 3
    assert elapsed < 3
