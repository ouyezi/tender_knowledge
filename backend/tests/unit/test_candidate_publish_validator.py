from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.models.product_category import CategoryStatus
from src.services.candidate_publish_validator import (
    PublishValidationError,
    validate_publish,
)
from tests.contract.test_file_import_confirm import _seed_active_category, _seed_active_taxonomy


def _mock_view(**kwargs):
    base = {
        "channel": "document",
        "candidate_type": "ku",
        "title": "默认标题",
        "content": "默认内容",
        "source_trace": {
            "source_doc_id": str(uuid4()),
            "source_node_id": str(uuid4()),
            "template_id": None,
        },
        "suggested_knowledge_type": "solution",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_ku_requires_knowledge_type():
    view = _mock_view(suggested_knowledge_type=None)
    with pytest.raises(PublishValidationError) as exc:
        validate_publish(
            db=None,
            kb_id=uuid4(),
            confirm_as="ku",
            payload={"title": "t", "content": "c"},
            view=view,
        )
    assert "knowledge_type" in str(exc.value)


def test_ku_requires_title_and_content():
    view = _mock_view(title=None, content=None)
    with pytest.raises(PublishValidationError) as title_exc:
        validate_publish(
            db=None,
            kb_id=uuid4(),
            confirm_as="ku",
            payload={"knowledge_type": "solution", "content": "x"},
            view=view,
        )
    assert "title" in str(title_exc.value)

    with pytest.raises(PublishValidationError) as content_exc:
        validate_publish(
            db=None,
            kb_id=uuid4(),
            confirm_as="ku",
            payload={"knowledge_type": "solution", "title": "x"},
            view=view,
        )
    assert "content" in str(content_exc.value)


def test_template_chapter_requires_template_id_for_template_channel():
    view = _mock_view(
        channel="template",
        candidate_type="template_chapter",
        source_trace={"template_id": None},
    )
    with pytest.raises(PublishValidationError) as exc:
        validate_publish(
            db=None,
            kb_id=uuid4(),
            confirm_as="template_chapter",
            payload={},
            view=view,
        )
    assert "template_id" in str(exc.value)


def test_validate_publish_rejects_inactive_taxonomy(db_session, seeded_kb):
    taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)
    taxonomy.status = CategoryStatus.inactive
    db_session.commit()

    view = _mock_view()
    with pytest.raises(PublishValidationError) as exc:
        validate_publish(
            db=db_session,
            kb_id=seeded_kb.kb_id,
            confirm_as="ku",
            payload={
                "knowledge_type": "solution",
                "title": "t",
                "content": "c",
                "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
            },
            view=view,
        )
    assert exc.value.code == "DEPRECATED_TAXONOMY"


def test_validate_publish_rejects_inactive_category(db_session, seeded_kb):
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    category.status = CategoryStatus.inactive
    db_session.commit()

    view = _mock_view()
    with pytest.raises(PublishValidationError) as exc:
        validate_publish(
            db=db_session,
            kb_id=seeded_kb.kb_id,
            confirm_as="ku",
            payload={
                "knowledge_type": "solution",
                "title": "t",
                "content": "c",
                "product_category_ids": [str(category.category_id)],
            },
            view=view,
        )
    assert "product_category_ids" in str(exc.value)
