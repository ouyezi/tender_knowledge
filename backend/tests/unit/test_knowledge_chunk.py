from src.services.docx_outline_parser import OutlineNode
from src.services.knowledge_chunk import (
    ChunkClassificationResult,
    build_knowledge_chunks,
    merge_classifications_into_suggestion,
)


def test_build_knowledge_chunks_from_outline_and_materials():
    nodes = [
        OutlineNode(
            temp_id="n1",
            parent_temp_id=None,
            title="1. 售后服务方案",
            level=1,
            sort_order=0,
            needs_manual_review=False,
        ),
    ]
    materials = [
        {
            "temp_id": "m1",
            "chapter_temp_id": "n1",
            "title": "固定说明",
            "content": "我们提供7x24支持",
            "material_type": "fixed_paragraph",
        },
    ]
    chunks = build_knowledge_chunks(outline_nodes=nodes, materials=materials, candidates=[])
    assert len(chunks) == 2
    assert chunks[0].chunk_type == "chapter"
    assert chunks[0].chunk_ref == "n1"
    assert chunks[1].chunk_type == "material"
    assert chunks[1].parent_chunk_ref == "n1"


def test_merge_classifications_writes_block_fields():
    tree = [{"temp_id": "n1", "title": "售后服务", "level": 1, "sort_order": 0}]
    materials = [{"temp_id": "m1", "chapter_temp_id": "n1", "title": "段"}]
    chunks = build_knowledge_chunks(
        outline_nodes=[
            OutlineNode(
                temp_id="n1",
                parent_temp_id=None,
                title="售后服务",
                level=1,
                sort_order=0,
                needs_manual_review=False,
            )
        ],
        materials=materials,
        candidates=[],
    )
    results = {
        chunks[0].chunk_ref: ChunkClassificationResult(
            suggested_product_category_ids=[],
            suggested_chapter_taxonomy_id=None,
            suggested_knowledge_type=None,
            classification_confidence=0.8,
            suggestion_source="rule",
            classification_rationale="标题命中",
        )
    }
    merged = merge_classifications_into_suggestion(
        suggested_chapter_tree=tree,
        suggested_materials=materials,
        suggested_candidates=[],
        chunks=chunks,
        results=results,
    )
    assert merged["suggested_chapter_tree"][0]["classification_confidence"] == 0.8
    assert merged["suggested_chapter_tree"][0]["suggestion_source"] == "rule"
