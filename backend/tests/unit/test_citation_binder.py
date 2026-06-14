from src.schemas.generation import SourceCatalogEntry
from src.services.generation.citation_binder import CitationBinder


def test_citation_binder_binds_refs_and_variables():
    catalog = [
        SourceCatalogEntry(
            ref_id="SRC-001",
            type="ku",
            object_id="ku-1",
            title="历史方案",
            excerpt="分层架构",
        ),
        SourceCatalogEntry(
            ref_id="VAR-project_name",
            type="variable",
            object_id="project_name",
            title="变量 project_name",
            excerpt="智慧园区一期",
        ),
    ]
    paragraphs = [
        {"text": "项目 {{project_name}} 采用分层架构", "source_ref_ids": ["SRC-001"]},
    ]

    bound = CitationBinder().bind(
        llm_paragraphs=paragraphs,
        catalog=catalog,
        resolved_variables={"project_name": "智慧园区一期"},
    )

    assert bound[0]["text"] == "项目 智慧园区一期 采用分层架构"
    refs = [c["ref_id"] for c in bound[0]["citations"]]
    assert "SRC-001" in refs
    assert "VAR-project_name" in refs


def test_citation_binder_falls_back_to_tender_source():
    catalog = [
        SourceCatalogEntry(
            ref_id="TREQ-SP-0",
            type="tender_requirement",
            object_id="score_point:0",
            title="评分点 0",
            excerpt="总体架构能力",
        )
    ]
    paragraphs = [{"text": "补齐引用", "source_ref_ids": []}]
    bound = CitationBinder().bind(
        llm_paragraphs=paragraphs,
        catalog=catalog,
        resolved_variables={},
    )
    assert bound[0]["citations"][0]["ref_id"] == "TREQ-SP-0"
