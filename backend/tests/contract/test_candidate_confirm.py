from uuid import UUID

from src.models.chapter_pattern import ChapterPattern
from src.models.candidate_knowledge import CandidateKnowledgeType
from src.models.product_category import ProductCategory
from src.models.template_chapter import TemplateChapter
from tests.contract.test_candidates_list import _seed_document_candidate, _seed_template_candidate
from tests.contract.test_file_import_confirm import _seed_active_category, _seed_active_taxonomy


def test_confirm_candidate_as_ku(client, db_session, seeded_kb):
    taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"

    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "ku",
            "knowledge_type": "solution",
            "title": "云平台架构设计",
            "content": "完整正文内容",
            "product_category_ids": [str(category.category_id)],
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
            "searchable": True,
            "review_comment": "publish ku",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "ku"
    assert data["confirmed_object_id"]
    assert data["idempotent"] is False


def test_confirm_candidate_as_wiki(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.candidate_type = CandidateKnowledgeType.wiki
    db_session.commit()
    cid = f"doc_{candidate.candidate_id}"

    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "wiki",
            "title": "Wiki 标题",
            "content": "Wiki 内容",
            "wiki_type": "faq",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "wiki"
    assert data["confirmed_object_id"]


def test_confirm_candidate_as_template_chapter(client, db_session, seeded_kb):
    stub, *_ = _seed_template_candidate(db_session, seeded_kb)
    stub.candidate_type = CandidateKnowledgeType.template_chapter
    db_session.commit()
    cid = f"tpl_{stub.stub_id}"

    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "template_chapter",
            "title": "模板章节A",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "template_chapter"
    assert data["confirmed_object_id"]
    row = db_session.get(TemplateChapter, UUID(data["confirmed_object_id"]))
    assert row is not None


def test_confirm_candidate_as_manual_asset(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.candidate_type = CandidateKnowledgeType.manual_asset
    db_session.commit()
    cid = f"doc_{candidate.candidate_id}"

    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "manual_asset",
            "title": "资料附件",
            "content": "附件内容",
            "asset_type": "text",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "manual_asset"
    assert data["confirmed_object_id"]


def test_confirm_candidate_as_chapter_pattern(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.candidate_type = CandidateKnowledgeType.chapter_pattern
    db_session.commit()
    cid = f"doc_{candidate.candidate_id}"

    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "chapter_pattern",
            "title": "通用方案章节模式",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "chapter_pattern"
    pattern = db_session.get(ChapterPattern, UUID(data["confirmed_object_id"]))
    assert pattern is not None
    assert pattern.status.value == "confirmed"


def test_confirm_candidate_as_product_category(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.candidate_type = CandidateKnowledgeType.product_category
    db_session.commit()
    cid = f"doc_{candidate.candidate_id}"

    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "product_category",
            "title": "Data Governance Product",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "product_category"
    category = db_session.get(ProductCategory, UUID(data["confirmed_object_id"]))
    assert category is not None
    assert category.category_code == "data-governance-product"


def test_confirm_candidate_as_ignore(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"
    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={"confirm_as": "ignore", "review_comment": "不需要入库"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "rejected"
    assert data["confirmed_object_type"] == "ignore"
    assert data["confirmed_object_id"] is None


def test_confirm_ku_idempotent_republish(client, db_session, seeded_kb):
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"
    payload = {
        "confirm_as": "ku",
        "knowledge_type": "solution",
        "title": "云平台架构设计",
        "content": "完整正文内容",
        "product_category_ids": [str(category.category_id)],
    }

    first = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json=payload,
    )
    assert first.status_code == 200
    first_data = first.json()["data"]

    second = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json=payload,
    )
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["idempotent"] is True
    assert second_data["confirmed_object_id"] == first_data["confirmed_object_id"]
