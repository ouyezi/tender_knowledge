from __future__ import annotations

from typing import Any


def minimal_chunk_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "章节标题",
        "content": "正文内容 A B C",
        "summary": "摘要",
        "knowledge_type": "fact",
        "content_type": "text",
        "source_type": "bid",
        "file_name": "chunk-service.docx",
        "project_name": "测试项目",
        "page_start": 1,
        "page_end": 2,
        "char_start": 0,
        "char_end": 10,
        "parent_id": None,
        "need_parent_context": False,
        "block_type_code": "product_solution",
        "application_type_code": "preferred_reference",
        "business_line_codes": ["general"],
        "tags": ["tag-a"],
        "industries": ["ind-a"],
        "customer_types": ["cust-a"],
        "regions": ["region-a"],
        "issue_date": None,
        "expire_date": None,
        "status": "draft",
        "is_template": False,
        "template_type": None,
        "variables": [],
        "is_immutable": False,
        "exclusion_rules": [],
        "retrieval_weight": 1.0,
        "security_level": "internal",
        "owner": "tester",
        "review_status": "approved",
        "winning_flag": False,
        "edit_distance_avg": None,
    }
    payload.update(overrides)
    return payload


def minimal_chunk_orm_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "title": "测试知识",
        "content": "测试内容",
        "summary": "测试摘要",
        "knowledge_type": "fact",
        "content_type": "text",
        "source_type": "bid",
        "block_type_code": "product_solution",
        "application_type_code": "preferred_reference",
        "business_line_codes": ["general"],
        "tags": [],
        "industries": [],
        "customer_types": [],
        "regions": [],
        "status": "draft",
        "is_template": False,
        "variables": [],
        "is_immutable": False,
        "exclusion_rules": [],
        "retrieval_weight": 1.0,
        "security_level": "internal",
        "review_status": "approved",
        "winning_flag": False,
        "has_children": False,
        "children_count": 0,
    }
    kwargs.update(overrides)
    return kwargs
