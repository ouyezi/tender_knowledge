from __future__ import annotations

from typing import Any


def minimal_chunk_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "章节标题",
        "content": "正文内容 A B C",
        "summary": "摘要",
        "knowledge_type": "fact",
        "content_type": "text",
        "file_name": "chunk-service.docx",
        "block_type_code": "product_solution",
        "application_type_code": "preferred_reference",
        "business_line_codes": ["general"],
        "tags": ["tag-a"],
        "regions": ["region-a"],
        "certificate_number": None,
        "certificate_date": None,
        "expire_date": None,
        "status": "draft",
        "is_template": False,
        "template_type": None,
        "security_level": "internal",
        "owner": "tester",
        "review_status": "approved",
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
        "block_type_code": "product_solution",
        "application_type_code": "preferred_reference",
        "business_line_codes": ["general"],
        "tags": [],
        "regions": [],
        "certificate_number": None,
        "certificate_date": None,
        "status": "draft",
        "is_template": False,
        "security_level": "internal",
        "review_status": "approved",
        "has_children": False,
        "children_count": 0,
    }
    kwargs.update(overrides)
    return kwargs
