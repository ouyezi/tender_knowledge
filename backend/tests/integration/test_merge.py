import uuid

import pytest
from sqlalchemy import select

from src.models.classification_reference import (
    ClassificationReference,
    ClassificationType,
    ReferenceObjectType,
)
from src.models.product_category import CategoryStatus
from src.services import kb_service, product_category_service
from src.services.merge_service import MergeError, merge_product_category, migrate_references


def test_merge_rejects_when_source_has_children(db_session):
    kb = kb_service.create_kb(db_session, "merge-kb")
    parent = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="父分类",
        category_code="parent",
    )
    product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="子分类",
        category_code="child",
        parent_id=parent.category_id,
    )
    other = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="其他",
        category_code="other",
    )

    with pytest.raises(MergeError) as exc:
        merge_product_category(db_session, source=parent, target=other)
    assert exc.value.code == "HAS_CHILDREN"


def test_merge_migrates_references_and_dedupes(db_session):
    kb = kb_service.create_kb(db_session, "merge-ref-kb")
    source = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="源",
        category_code="source",
    )
    target = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="目标",
        category_code="target",
    )

    shared_object_id = uuid.uuid4()
    db_session.add(
        ClassificationReference(
            kb_id=kb.kb_id,
            classification_type=ClassificationType.product_category,
            classification_id=source.category_id,
            object_type=ReferenceObjectType.ku,
            object_id=shared_object_id,
        )
    )
    db_session.add(
        ClassificationReference(
            kb_id=kb.kb_id,
            classification_type=ClassificationType.product_category,
            classification_id=target.category_id,
            object_type=ReferenceObjectType.ku,
            object_id=shared_object_id,
        )
    )
    unique_object_id = uuid.uuid4()
    db_session.add(
        ClassificationReference(
            kb_id=kb.kb_id,
            classification_type=ClassificationType.product_category,
            classification_id=source.category_id,
            object_type=ReferenceObjectType.wiki,
            object_id=unique_object_id,
        )
    )
    db_session.commit()

    result = merge_product_category(db_session, source=source, target=target)
    assert result["migrated_reference_count"] == 1
    assert source.status == CategoryStatus.merged
    assert source.merged_into_id == target.category_id

    refs = list(
        db_session.scalars(
            select(ClassificationReference).where(
                ClassificationReference.kb_id == kb.kb_id,
                ClassificationReference.classification_type
                == ClassificationType.product_category,
                ClassificationReference.classification_id == target.category_id,
            )
        ).all()
    )
    # dedupe: only target refs remain (ku shared + wiki migrated)
    object_ids = {r.object_id for r in refs}
    assert shared_object_id in object_ids
    assert unique_object_id in object_ids


def test_migrate_references_count(db_session):
    kb = kb_service.create_kb(db_session, "migrate-kb")
    source = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="源2",
        category_code="source2",
    )
    target = product_category_service.create_category(
        db_session,
        kb.kb_id,
        category_name="目标2",
        category_code="target2",
    )
    db_session.add(
        ClassificationReference(
            kb_id=kb.kb_id,
            classification_type=ClassificationType.product_category,
            classification_id=source.category_id,
            object_type=ReferenceObjectType.ku,
            object_id=uuid.uuid4(),
        )
    )
    db_session.commit()

    count = migrate_references(
        db_session,
        kb.kb_id,
        ClassificationType.product_category,
        source.category_id,
        target.category_id,
    )
    assert count == 1
