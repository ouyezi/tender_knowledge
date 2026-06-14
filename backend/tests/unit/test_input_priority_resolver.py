from uuid import uuid4

from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.tender_requirement_context import TenderRequirementContext
from src.schemas.generation import UserChapterSelection
from src.services.generation.input_priority_resolver import InputPriorityResolver


def test_input_priority_resolver_builds_layers_and_catalog():
    context = TenderRequirementContext(
        kb_id=uuid4(),
        title="招标要求",
        outline_structure={"sections": ["技术方案"]},
        outline_nodes=[{"title": "技术方案", "level": 1, "sort_order": 0}],
        score_points=[{"text": "总体架构能力"}],
        rejection_clauses=["禁止要求原厂授权"],
    )
    keep_template_id = str(uuid4())
    drop_template_id = str(uuid4())
    suggestion = ModuleAssemblySuggestion(
        kb_id=uuid4(),
        trace_id=uuid4(),
        target_outline_node={"title": "技术方案", "level": 1, "sort_order": 0},
        suggested_template_chapter_ids=[keep_template_id, drop_template_id],
        knowledge_pack_snapshot=[
            {
                "object_type": "ku",
                "object_id": str(uuid4()),
                "title": "历史架构方案",
                "excerpt": "采用分层架构",
            }
        ],
        match_score=0.9,
        coverage_rate=0.9,
        score_detail={},
    )

    resolved = InputPriorityResolver().resolve(
        requirement_context=context,
        suggestion=suggestion,
        target_outline_node={"title": "技术方案", "level": 1, "sort_order": 0},
        user_chapter_selections=[
            UserChapterSelection(template_chapter_id=uuid4(), enabled=True, source="user_manual")
        ],
        resolved_variables={"project_name": "智慧园区一期"},
        conflict_template_ids={drop_template_id},
    )

    ref_ids = [item.ref_id for item in resolved.source_catalog]
    assert "TREQ-RC-0" in ref_ids
    assert "TREQ-SP-0" in ref_ids
    assert "VAR-project_name" in ref_ids
    assert any(ref.startswith("SRC-") for ref in ref_ids)
    assert not any(item.object_id == drop_template_id for item in resolved.source_catalog)
    assert resolved.layers["template_hints"]
