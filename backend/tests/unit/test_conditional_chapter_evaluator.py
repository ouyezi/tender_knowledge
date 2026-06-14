from uuid import uuid4

from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models.template_rule import (
    TemplateRule,
    TemplateRuleAction,
    TemplateRuleStatus,
    TemplateRuleType,
)
from src.models.tender_requirement_context import TenderRequirementContext
from src.schemas.generation import UserChapterSelection
from src.services.generation.conditional_chapter_evaluator import ConditionalChapterEvaluator


def test_product_match_rule_suggests_enable(db_session, seeded_kb):
    category_id = str(uuid4())
    template_id = uuid4()
    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        parent_id=None,
        title="餐补专项方案",
        level=2,
        sort_order=1,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    rule = TemplateRule(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        template_chapter_id=chapter.template_chapter_id,
        rule_type=TemplateRuleType.product_match,
        condition={"field": "product_category", "operator": "in", "value": [category_id]},
        action=TemplateRuleAction.enable,
        message="餐补产品下启用",
        status=TemplateRuleStatus.active,
    )
    db_session.add(rule)
    db_session.commit()

    context = TenderRequirementContext(
        kb_id=seeded_kb.kb_id,
        title="招标要求",
        rejection_clauses=["禁止要求原厂授权"],
        score_points=[{"text": "总体架构能力"}],
    )
    result = ConditionalChapterEvaluator().evaluate(
        db_session,
        kb_id=seeded_kb.kb_id,
        template_chapters=[chapter],
        product_category_ids=[category_id],
        customer_type=None,
        requirement_context=context,
        user_chapter_selections=[],
        conflict_template_ids=set(),
        conflict_risk_flags=[],
    )

    assert len(result.suggested_chapter_enables) == 1
    suggestion = result.suggested_chapter_enables[0]
    assert suggestion["template_chapter_id"] == str(chapter.template_chapter_id)
    assert suggestion["enabled"] is True
    assert suggestion["reason"] == "餐补产品下启用"
    assert suggestion["rule_type"] == "product_match"
    assert suggestion["risk_flags"] == []


def test_conditional_tender_keyword_rule_suggests_enable(db_session, seeded_kb):
    category_id = str(uuid4())
    template_id = uuid4()
    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        parent_id=None,
        title="云平台部署方案",
        level=2,
        sort_order=1,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    rule = TemplateRule(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        template_chapter_id=chapter.template_chapter_id,
        rule_type=TemplateRuleType.conditional,
        condition={"field": "tender_keyword", "operator": "contains", "value": ["云平台"]},
        action=TemplateRuleAction.enable,
        message="招标关键词命中云平台",
        status=TemplateRuleStatus.active,
    )
    db_session.add(rule)
    db_session.commit()

    context = TenderRequirementContext(
        kb_id=seeded_kb.kb_id,
        title="招标要求",
        score_points=[{"text": "云平台高可用架构"}],
    )
    result = ConditionalChapterEvaluator().evaluate(
        db_session,
        kb_id=seeded_kb.kb_id,
        template_chapters=[chapter],
        product_category_ids=[],
        customer_type=None,
        requirement_context=context,
        user_chapter_selections=[],
        conflict_template_ids=set(),
        conflict_risk_flags=[],
    )

    assert len(result.suggested_chapter_enables) == 1
    assert result.suggested_chapter_enables[0]["reason"] == "招标关键词命中云平台"


def test_conflict_chapter_adds_risk_flags(db_session, seeded_kb):
    category_id = str(uuid4())
    template_id = uuid4()
    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        parent_id=None,
        title="原厂授权说明",
        level=2,
        sort_order=1,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    rule = TemplateRule(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        template_chapter_id=chapter.template_chapter_id,
        rule_type=TemplateRuleType.product_match,
        condition={"field": "product_category", "operator": "in", "value": [category_id]},
        action=TemplateRuleAction.enable,
        status=TemplateRuleStatus.active,
    )
    db_session.add(rule)
    db_session.commit()

    chapter_id = str(chapter.template_chapter_id)
    conflict_flags = [
        {
            "template_chapter_id": chapter_id,
            "risk_type": "tender_template_conflict",
            "reason": "招标约束命中敏感词：原厂授权",
        }
    ]
    context = TenderRequirementContext(
        kb_id=seeded_kb.kb_id,
        title="招标要求",
        rejection_clauses=["禁止要求原厂授权"],
    )
    result = ConditionalChapterEvaluator().evaluate(
        db_session,
        kb_id=seeded_kb.kb_id,
        template_chapters=[chapter],
        product_category_ids=[category_id],
        customer_type=None,
        requirement_context=context,
        user_chapter_selections=[],
        conflict_template_ids={chapter_id},
        conflict_risk_flags=conflict_flags,
    )

    assert len(result.suggested_chapter_enables) == 1
    suggestion = result.suggested_chapter_enables[0]
    assert suggestion["risk_flags"]
    assert suggestion["risk_flags"][0]["risk_type"] == "tender_template_conflict"


def test_user_chapter_selection_rule(db_session, seeded_kb):
    template_id = uuid4()
    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        parent_id=None,
        title="可选增值模块",
        level=2,
        sort_order=1,
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    rule = TemplateRule(
        kb_id=seeded_kb.kb_id,
        template_id=template_id,
        template_chapter_id=chapter.template_chapter_id,
        rule_type=TemplateRuleType.conditional,
        condition={"field": "user_chapter_selection", "value": True},
        action=TemplateRuleAction.enable,
        message="用户手工启用",
        status=TemplateRuleStatus.active,
    )
    db_session.add(rule)
    db_session.commit()

    context = TenderRequirementContext(kb_id=seeded_kb.kb_id, title="招标要求")
    result = ConditionalChapterEvaluator().evaluate(
        db_session,
        kb_id=seeded_kb.kb_id,
        template_chapters=[chapter],
        product_category_ids=[],
        customer_type=None,
        requirement_context=context,
        user_chapter_selections=[
            UserChapterSelection(
                template_chapter_id=chapter.template_chapter_id,
                enabled=True,
                source="user_manual",
            )
        ],
        conflict_template_ids=set(),
        conflict_risk_flags=[],
    )

    assert len(result.suggested_chapter_enables) == 1
    assert result.suggested_chapter_enables[0]["reason"] == "用户手工启用"
