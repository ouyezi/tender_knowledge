from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS


def test_seed_has_all_dimensions():
    dimensions = {row["dimension"] for row in KNOWLEDGE_TAXONOMY_SEED_ROWS}
    assert dimensions == {"block_type", "application_type", "business_line", "dynamic_type"}


def test_block_type_has_two_levels():
    block_rows = [r for r in KNOWLEDGE_TAXONOMY_SEED_ROWS if r["dimension"] == "block_type"]
    assert any(r["level"] == 1 for r in block_rows)
    assert any(r["level"] == 2 for r in block_rows)
    child = next(r for r in block_rows if r["code"] == "qualification_sub_brand")
    assert child["parent_code"] == "qualification_document"
