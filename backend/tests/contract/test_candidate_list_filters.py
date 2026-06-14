from uuid import uuid4

from tests.contract.test_candidates_list import (
    _seed_document_candidate,
    _seed_template_candidate,
)
from tests.contract.test_file_import_confirm import (
    _seed_active_category,
    _seed_active_taxonomy,
)


def test_list_candidates_filter_by_chapter_taxonomy(client, db_session, seeded_kb):
    taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)
    other_taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)

    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.suggested_chapter_taxonomy_id = taxonomy.taxonomy_id
    db_session.commit()

    stub, *_ = _seed_template_candidate(db_session, seeded_kb)
    stub.chapter_taxonomy_id = other_taxonomy.taxonomy_id
    db_session.commit()

    matched = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"chapter_taxonomy_id": str(taxonomy.taxonomy_id)},
        headers={"X-Operator-Id": "admin"},
    )
    assert matched.status_code == 200
    ids = {item["candidate_id"] for item in matched.json()["data"]["items"]}
    assert f"doc_{candidate.candidate_id}" in ids
    assert f"tpl_{stub.stub_id}" not in ids

    unmatched = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"chapter_taxonomy_id": str(uuid4())},
        headers={"X-Operator-Id": "admin"},
    )
    assert unmatched.status_code == 200
    assert unmatched.json()["data"]["total"] == 0


def test_list_candidates_filter_by_product_category(client, db_session, seeded_kb):
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    other_category = _seed_active_category(db_session, seeded_kb.kb_id)

    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.suggested_product_category_ids = [str(category.category_id)]
    db_session.commit()

    stub, *_ = _seed_template_candidate(db_session, seeded_kb)
    stub.product_category_ids = [str(other_category.category_id)]
    db_session.commit()

    doc_match = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"product_category_id": str(category.category_id)},
        headers={"X-Operator-Id": "admin"},
    )
    assert doc_match.status_code == 200
    doc_ids = {item["candidate_id"] for item in doc_match.json()["data"]["items"]}
    assert f"doc_{candidate.candidate_id}" in doc_ids
    assert f"tpl_{stub.stub_id}" not in doc_ids

    tpl_match = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"product_category_id": str(other_category.category_id)},
        headers={"X-Operator-Id": "admin"},
    )
    assert tpl_match.status_code == 200
    tpl_ids = {item["candidate_id"] for item in tpl_match.json()["data"]["items"]}
    assert f"tpl_{stub.stub_id}" in tpl_ids
    assert f"doc_{candidate.candidate_id}" not in tpl_ids


def test_list_candidates_filter_by_confidence_min(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.confidence_score = 0.88
    db_session.commit()

    stub, *_ = _seed_template_candidate(db_session, seeded_kb)
    stub.classification_confidence = 0.66
    db_session.commit()

    high_confidence = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"confidence_min": 0.7},
        headers={"X-Operator-Id": "admin"},
    )
    assert high_confidence.status_code == 200
    high_ids = {item["candidate_id"] for item in high_confidence.json()["data"]["items"]}
    assert f"doc_{candidate.candidate_id}" in high_ids
    assert f"tpl_{stub.stub_id}" not in high_ids

    low_confidence = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"confidence_min": 0.5},
        headers={"X-Operator-Id": "admin"},
    )
    assert low_confidence.status_code == 200
    assert low_confidence.json()["data"]["total"] == 2
