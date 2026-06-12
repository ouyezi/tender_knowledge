from src.models.chapter_taxonomy import ChapterTaxonomy, CategoryStatus
from src.services.classification_rule_index import (
    load_classification_index,
    match_chapter_taxonomy,
)


def test_match_chapter_taxonomy_by_title_keyword(db_session, seeded_kb):
    tax = ChapterTaxonomy(
        kb_id=seeded_kb.kb_id,
        standard_name="售后服务方案",
        taxonomy_code="after_sales",
        status=CategoryStatus.active,
        path="/after_sales",
        depth=0,
    )
    db_session.add(tax)
    db_session.commit()
    index = load_classification_index(db_session, kb_id=seeded_kb.kb_id)
    hit = match_chapter_taxonomy("1. 售后服务方案", index=index)
    assert hit is not None
    assert hit.taxonomy_id == tax.taxonomy_id
