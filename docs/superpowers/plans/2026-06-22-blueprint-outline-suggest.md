# Blueprint Outline Suggest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付蓝图详情页「目录建议」全栈能力：无状态 `POST /blueprints/suggest-outline` API + 右侧 50% Drawer，结合多蓝图经验与用户自由文本需求，由 LLM 生成可查看的独立目录建议树。

**Architecture:** 新建独立 `blueprint_outline_suggest_service`（不修改 `blueprint_generate_service`）；从 DB 只读加载蓝图详情并精简为 LLM 上下文；一次性 LLM 调用 + JSON 校验；前端 Drawer + 只读结果树。V1 不落库。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pytest; React 18, TypeScript, Ant Design 5.

**Design spec:** `docs/superpowers/specs/2026-06-22-blueprint-outline-suggest-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/config.py` | 新增 `blueprint_suggest_*` 配置项 |
| `.env.example` | 文档化新环境变量 |
| `backend/src/api/schemas/blueprints.py` | `SuggestOutlineRequest` / `SuggestOutlineNode` / `SuggestOutlineResponse` |
| `backend/src/services/knowledge/blueprint_outline_suggest_service.py` | 上下文组装、LLM 调用、解析校验（新建） |
| `backend/src/api/routes/blueprints.py` | `POST /suggest-outline` 路由 |
| `backend/tests/unit/test_blueprint_config.py` | 新配置默认值 |
| `backend/tests/unit/test_blueprint_outline_suggest_service.py` | 服务单元测试（新建） |
| `backend/tests/integration/test_blueprint_api.py` | suggest-outline 集成测试 |
| `frontend/src/services/blueprints.ts` | 类型 + `suggestBlueprintOutline()` |
| `frontend/src/components/Blueprint/BlueprintOutlineSuggestTree.tsx` | 结果树展示（新建） |
| `frontend/src/components/Blueprint/BlueprintOutlineSuggestDrawer.tsx` | Drawer 容器（新建） |
| `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx` | 「目录建议」按钮与状态 |

---

## Task 1: 配置项

**Files:**
- Modify: `backend/src/config.py`
- Modify: `.env.example`
- Modify: `backend/tests/unit/test_blueprint_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_blueprint_config.py — append:

def test_blueprint_suggest_defaults():
    assert settings.blueprint_suggest_model == settings.blueprint_generate_model
    assert settings.blueprint_suggest_timeout_sec == 120
    assert settings.blueprint_suggest_max_tokens == 8192
    assert settings.blueprint_suggest_max_blueprints == 5
    assert settings.blueprint_suggest_requirement_max == 2000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_config.py::test_blueprint_suggest_defaults -v`

Expected: FAIL with `AttributeError: blueprint_suggest_model`

- [ ] **Step 3: Add settings**

```python
# backend/src/config.py — after blueprint_generate_max_tokens:
    blueprint_suggest_model: str = "qwen3.6-flash"
    blueprint_suggest_timeout_sec: int = 120
    blueprint_suggest_max_tokens: int = 8192
    blueprint_suggest_max_blueprints: int = 5
    blueprint_suggest_requirement_max: int = 2000
```

```bash
# .env.example — after BLUEPRINT_GENERATE_MODEL=
BLUEPRINT_SUGGEST_MODEL=qwen3.6-flash
BLUEPRINT_SUGGEST_TIMEOUT_SEC=120
BLUEPRINT_SUGGEST_MAX_TOKENS=8192
BLUEPRINT_SUGGEST_MAX_BLUEPRINTS=5
BLUEPRINT_SUGGEST_REQUIREMENT_MAX=2000
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/config.py .env.example backend/tests/unit/test_blueprint_config.py
git commit -m "feat: add blueprint outline suggest config settings"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Modify: `backend/src/api/schemas/blueprints.py`

- [ ] **Step 1: Add request/response models**

```python
# backend/src/api/schemas/blueprints.py — append:

class SuggestOutlineRequest(BaseModel):
    blueprint_ids: list[UUID] = Field(min_length=1)
    requirement_description: str = Field(min_length=1)


class SuggestOutlineNode(BaseModel):
    title: str
    content_suggestion: str
    importance: str
    split_reason: str | None = None
    no_split_reason: str | None = None
    children: list["SuggestOutlineNode"] = Field(default_factory=list)


SuggestOutlineNode.model_rebuild()


class SuggestOutlineResponse(BaseModel):
    outline_title: str
    summary: str
    nodes: list[SuggestOutlineNode] = Field(default_factory=list)
```

- [ ] **Step 2: Verify import**

Run: `cd backend && ../.venv/bin/python -c "from src.api.schemas.blueprints import SuggestOutlineRequest, SuggestOutlineResponse; print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/schemas/blueprints.py
git commit -m "feat: add suggest-outline pydantic schemas"
```

---

## Task 3: 服务 — 上下文精简与节点校验

**Files:**
- Create: `backend/src/services/knowledge/blueprint_outline_suggest_service.py`
- Create: `backend/tests/unit/test_blueprint_outline_suggest_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_blueprint_outline_suggest_service.py
from src.services.knowledge.blueprint_outline_suggest_service import (
    compact_blueprint_detail,
    validate_suggest_node,
    validate_suggest_nodes,
    OutlineSuggestValidationError,
)

SAMPLE_DETAIL = {
    "name": "供应链蓝图",
    "description": "模块概要",
    "scenario_tags": ["物流"],
    "product_tags": ["WMS"],
    "industry_tags": ["制造"],
    "suggested_structure_md": "结构说明",
    "nodes": [
        {
            "node_title": "总体设计",
            "importance_level": "required",
            "content_description": "写总体思路",
            "tender_response_hint": "响应评分",
            "children": [],
        }
    ],
}


def test_compact_blueprint_detail_uses_short_keys():
    compact = compact_blueprint_detail(SAMPLE_DETAIL)
    assert compact["name"] == "供应链蓝图"
    assert compact["nodes"][0]["t"] == "总体设计"
    assert compact["nodes"][0]["imp"] == "required"
    assert compact["nodes"][0]["cd"] == "写总体思路"
    assert "node_title" not in compact["nodes"][0]


def test_validate_suggest_node_leaf_requires_no_split_reason():
    node = {
        "title": "总体设计",
        "content_suggestion": "写思路",
        "importance": "required",
        "split_reason": None,
        "no_split_reason": "单章即可覆盖",
        "children": [],
    }
    assert validate_suggest_node(node, depth=1)["title"] == "总体设计"


def test_validate_suggest_node_parent_requires_split_reason():
    node = {
        "title": "技术方案",
        "content_suggestion": "技术内容",
        "importance": "required",
        "split_reason": "按评分点拆分",
        "no_split_reason": None,
        "children": [
            {
                "title": "架构",
                "content_suggestion": "架构说明",
                "importance": "required",
                "split_reason": None,
                "no_split_reason": "不宜再拆",
                "children": [],
            }
        ],
    }
    result = validate_suggest_node(node, depth=1)
    assert len(result["children"]) == 1


def test_validate_suggest_node_rejects_missing_reason():
    node = {
        "title": "技术方案",
        "content_suggestion": "技术内容",
        "importance": "required",
        "split_reason": None,
        "no_split_reason": None,
        "children": [],
    }
    try:
        validate_suggest_node(node, depth=1)
        assert False, "expected OutlineSuggestValidationError"
    except OutlineSuggestValidationError:
        pass


def test_validate_suggest_node_rejects_depth_over_limit():
    deep = {
        "title": "L1",
        "content_suggestion": "c",
        "importance": "required",
        "split_reason": "r",
        "no_split_reason": None,
        "children": [
            {
                "title": "L2",
                "content_suggestion": "c",
                "importance": "required",
                "split_reason": "r",
                "no_split_reason": None,
                "children": [
                    {
                        "title": "L3",
                        "content_suggestion": "c",
                        "importance": "required",
                        "split_reason": "r",
                        "no_split_reason": None,
                        "children": [
                            {
                                "title": "L4",
                                "content_suggestion": "c",
                                "importance": "required",
                                "split_reason": "r",
                                "no_split_reason": None,
                                "children": [
                                    {
                                        "title": "L5",
                                        "content_suggestion": "c",
                                        "importance": "required",
                                        "split_reason": None,
                                        "no_split_reason": "too deep",
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    try:
        validate_suggest_nodes([deep])
        assert False, "expected OutlineSuggestValidationError"
    except OutlineSuggestValidationError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_outline_suggest_service.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement compact + validate helpers**

```python
# backend/src/services/knowledge/blueprint_outline_suggest_service.py
from __future__ import annotations

import json
from typing import Any

from src.services.knowledge.blueprint_field_utils import truncate_blueprint_field

MAX_STRUCTURE_MD_CONTEXT = 800
MAX_NODE_TEXT_CONTEXT = 200
MAX_SUGGEST_DEPTH = 4

_SYSTEM_PROMPT = (
    "你是标书目录顾问。根据目录蓝图经验与用户目录需求，输出全新有序目录建议 JSON。\n"
    "规则：\n"
    "1. 生成独立新大纲，非蓝图节点镜像。\n"
    "2. 标题不含序号前缀。\n"
    "3. 有 children 时填 split_reason，叶子节点填 no_split_reason，二者互斥。\n"
    "4. importance 取值 required | recommended | optional。\n"
    "5. 只返回 JSON，不要 markdown 包裹。\n"
    "Schema：\n"
    '{"outline_title":"标题","summary":"整体说明","nodes":[{"title":"章节",'
    '"content_suggestion":"内容建议","importance":"required",'
    '"split_reason":"拆分理由或null","no_split_reason":"不拆分理由或null","children":[]}]}'
)


class OutlineSuggestValidationError(Exception):
    pass


class OutlineSuggestTimeoutError(Exception):
    pass


class OutlineSuggestFailedError(Exception):
    pass


def compact_blueprint_detail(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": detail.get("name") or "",
        "description": detail.get("description") or "",
        "scenario_tags": detail.get("scenario_tags") or [],
        "product_tags": detail.get("product_tags") or [],
        "industry_tags": detail.get("industry_tags") or [],
        "suggested_structure_md": truncate_blueprint_field(
            detail.get("suggested_structure_md"),
            max_len=MAX_STRUCTURE_MD_CONTEXT,
        )
        or "",
        "nodes": [_compact_node(node) for node in detail.get("nodes") or []],
    }


def _compact_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "t": (node.get("node_title") or "").strip(),
        "imp": node.get("importance_level") or "optional",
        "cd": truncate_blueprint_field(node.get("content_description"), max_len=MAX_NODE_TEXT_CONTEXT) or "",
        "tr": truncate_blueprint_field(node.get("tender_response_hint"), max_len=MAX_NODE_TEXT_CONTEXT) or "",
        "children": [_compact_node(child) for child in node.get("children") or []],
    }


def build_suggest_user_prompt(*, blueprints: list[dict[str, Any]], requirement: str) -> str:
    payload = json.dumps(blueprints, ensure_ascii=False, separators=(",", ":"))
    return f"【目录蓝图经验】\n{payload}\n\n【用户目录需求】\n{requirement.strip()}"


def validate_suggest_nodes(nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(nodes, list) or not nodes:
        raise OutlineSuggestValidationError("nodes missing")
    return [validate_suggest_node(node, depth=1) for node in nodes]


def validate_suggest_node(node: Any, *, depth: int) -> dict[str, Any]:
    if depth > MAX_SUGGEST_DEPTH:
        raise OutlineSuggestValidationError("max depth exceeded")
    if not isinstance(node, dict):
        raise OutlineSuggestValidationError("node must be object")

    title = str(node.get("title") or "").strip()
    content_suggestion = str(node.get("content_suggestion") or "").strip()
    importance = str(node.get("importance") or node.get("imp") or "").strip()
    if not title or not content_suggestion:
        raise OutlineSuggestValidationError("title or content_suggestion missing")
    if importance not in {"required", "recommended", "optional"}:
        raise OutlineSuggestValidationError("invalid importance")

    children_raw = node.get("children") or []
    if not isinstance(children_raw, list):
        raise OutlineSuggestValidationError("children must be list")

    split_reason = _optional_text(node.get("split_reason"))
    no_split_reason = _optional_text(node.get("no_split_reason"))

    if children_raw:
        if not split_reason or no_split_reason:
            raise OutlineSuggestValidationError("parent must have split_reason only")
    else:
        if not no_split_reason or split_reason:
            raise OutlineSuggestValidationError("leaf must have no_split_reason only")

    children = [validate_suggest_node(child, depth=depth + 1) for child in children_raw]
    return {
        "title": title,
        "content_suggestion": content_suggestion,
        "importance": importance,
        "split_reason": split_reason,
        "no_split_reason": no_split_reason,
        "children": children,
    }


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_outline_suggest_service.py -v`

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_outline_suggest_service.py backend/tests/unit/test_blueprint_outline_suggest_service.py
git commit -m "feat: add blueprint outline suggest compact and validation helpers"
```

---

## Task 4: 服务 — LLM 调用与 suggest_outline 入口

**Files:**
- Modify: `backend/src/services/knowledge/blueprint_outline_suggest_service.py`
- Modify: `backend/tests/unit/test_blueprint_outline_suggest_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to test_blueprint_outline_suggest_service.py
import json
from uuid import uuid4
from unittest.mock import MagicMock

from src.services.knowledge.blueprint_outline_suggest_service import (
    OutlineSuggestFailedError,
    parse_and_validate_llm_response,
    suggest_outline,
)
from src.services.knowledge.blueprint_service import BlueprintNotFoundError

MOCK_SUGGEST_JSON = json.dumps(
    {
        "outline_title": "政务云建议目录",
        "summary": "突出安全与实施",
        "nodes": [
            {
                "title": "技术方案",
                "content_suggestion": "写技术内容",
                "importance": "required",
                "split_reason": "按评分点拆分",
                "no_split_reason": None,
                "children": [
                    {
                        "title": "总体架构",
                        "content_suggestion": "写架构",
                        "importance": "required",
                        "split_reason": None,
                        "no_split_reason": "不宜再拆",
                        "children": [],
                    }
                ],
            }
        ],
    },
    ensure_ascii=False,
)


def test_parse_and_validate_llm_response_ok():
    result = parse_and_validate_llm_response(MOCK_SUGGEST_JSON)
    assert result["outline_title"] == "政务云建议目录"
    assert result["nodes"][0]["children"][0]["no_split_reason"] == "不宜再拆"


def test_parse_and_validate_llm_response_invalid_json():
    try:
        parse_and_validate_llm_response("not-json")
        assert False
    except OutlineSuggestFailedError:
        pass


def test_suggest_outline_happy_path(monkeypatch):
    db = MagicMock()
    kb_id = uuid4()
    blueprint_id = uuid4()

    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service.settings.llm_enabled",
        True,
    )
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service.get_blueprint_detail",
        lambda _db, *, kb_id, blueprint_id: SAMPLE_DETAIL | {"blueprint_id": str(blueprint_id)},
    )
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service._chat_with_timeout",
        lambda **_: MOCK_SUGGEST_JSON,
    )

    result = suggest_outline(
        db,
        kb_id=kb_id,
        blueprint_ids=[blueprint_id],
        requirement_description="政务云项目，突出安全合规",
    )
    assert result["outline_title"] == "政务云建议目录"


def test_suggest_outline_blueprint_not_found(monkeypatch):
    db = MagicMock()
    kb_id = uuid4()
    blueprint_id = uuid4()

    def _raise(*_args, **_kwargs):
        raise BlueprintNotFoundError

    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service.get_blueprint_detail",
        _raise,
    )

    try:
        suggest_outline(
            db,
            kb_id=kb_id,
            blueprint_ids=[blueprint_id],
            requirement_description="需求",
        )
        assert False
    except BlueprintNotFoundError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_outline_suggest_service.py::test_parse_and_validate_llm_response_ok -v`

Expected: FAIL with `cannot import name 'parse_and_validate_llm_response'`

- [ ] **Step 3: Implement LLM + suggest_outline**

在 `blueprint_outline_suggest_service.py` 追加（对齐 `blueprint_generate_service._chat_with_timeout` / `_parse_llm_json` 模式，但使用 `blueprint_suggest_*` 配置）：

```python
import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.services.knowledge.blueprint_service import BlueprintNotFoundError, get_blueprint_detail

logger = logging.getLogger(__name__)


def suggest_outline(
    db: Session,
    *,
    kb_id: UUID,
    blueprint_ids: list[UUID],
    requirement_description: str,
) -> dict[str, Any]:
    if not settings.llm_enabled:
        raise OutlineSuggestFailedError("llm not configured")

    requirement = requirement_description.strip()
    if not requirement:
        raise OutlineSuggestFailedError("requirement_description empty")
    if len(requirement) > settings.blueprint_suggest_requirement_max:
        raise OutlineSuggestFailedError("requirement_description too long")
    if not blueprint_ids:
        raise OutlineSuggestFailedError("blueprint_ids empty")
    if len(blueprint_ids) > settings.blueprint_suggest_max_blueprints:
        raise OutlineSuggestFailedError("too many blueprint_ids")

    compact_contexts: list[dict[str, Any]] = []
    for blueprint_id in blueprint_ids:
        try:
            detail = get_blueprint_detail(db, kb_id=kb_id, blueprint_id=blueprint_id)
        except BlueprintNotFoundError:
            raise
        compact_contexts.append(compact_blueprint_detail(detail))

    user_prompt = build_suggest_user_prompt(blueprints=compact_contexts, requirement=requirement)
    raw = _chat_with_timeout(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    return parse_and_validate_llm_response(raw)


def parse_and_validate_llm_response(raw: str) -> dict[str, Any]:
    parsed = _parse_llm_json(raw)
    if parsed is None:
        raise OutlineSuggestFailedError("invalid llm json")

    outline_title = str(parsed.get("outline_title") or parsed.get("title") or "").strip()
    summary = str(parsed.get("summary") or parsed.get("desc") or "").strip()
    if not outline_title or not summary:
        raise OutlineSuggestFailedError("outline_title or summary missing")

    try:
        nodes = validate_suggest_nodes(parsed.get("nodes"))
    except OutlineSuggestValidationError as exc:
        raise OutlineSuggestFailedError(str(exc)) from exc

    return {
        "outline_title": outline_title,
        "summary": summary,
        "nodes": nodes,
    }


def _chat_with_timeout(*, system_prompt: str, user_prompt: str) -> str:
    model = settings.blueprint_suggest_model
    timeout_sec = settings.blueprint_suggest_timeout_sec
    max_tokens = settings.blueprint_suggest_max_tokens
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"])
    except TimeoutError as exc:
        raise OutlineSuggestTimeoutError("outline suggest timed out") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise OutlineSuggestTimeoutError("outline suggest timed out") from exc
        raise OutlineSuggestFailedError("llm request failed") from exc
    except (urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise OutlineSuggestFailedError("llm response malformed") from exc
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("outline suggest llm elapsed_ms=%.1f model=%s", elapsed_ms, model)


def _parse_llm_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
```

- [ ] **Step 4: Run all service unit tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_outline_suggest_service.py -v`

Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_outline_suggest_service.py backend/tests/unit/test_blueprint_outline_suggest_service.py
git commit -m "feat: add blueprint outline suggest LLM service"
```

---

## Task 5: API 路由与集成测试

**Files:**
- Modify: `backend/src/api/routes/blueprints.py`
- Modify: `backend/tests/integration/test_blueprint_api.py`

- [ ] **Step 1: Write the failing integration tests**

```python
# backend/tests/integration/test_blueprint_api.py — append:

MOCK_SUGGEST_JSON = """
{
  "outline_title": "供应链建议目录",
  "summary": "按需求组织章节",
  "nodes": [{
    "title": "总体设计",
    "content_suggestion": "写总体设计思路。",
    "importance": "required",
    "split_reason": null,
    "no_split_reason": "单章覆盖即可。",
    "children": []
  }]
}
""".strip()


def _create_blueprint_for_suggest(client, kb_id, db_session):
    document, parent, _ = _seed_document_tree(db_session, kb_id)
    payload = _build_manual_payload(
        document.document_id,
        parent.node_id,
        name="建议测试蓝图",
        description="用于 suggest-outline",
    )
    create_resp = client.post(f"/api/v1/kbs/{kb_id}/blueprints", json=payload)
    assert create_resp.status_code == 201
    return create_resp.json()["data"]["blueprint_id"]


def test_suggest_outline_happy_path(client, db_session, seeded_kb, monkeypatch):
    blueprint_id = _create_blueprint_for_suggest(client, seeded_kb.kb_id, db_session)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service._chat_with_timeout",
        lambda **_: MOCK_SUGGEST_JSON,
    )
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/suggest-outline",
        json={
            "blueprint_ids": [blueprint_id],
            "requirement_description": "需要突出供应链安全与实施计划",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["outline_title"] == "供应链建议目录"
    assert data["nodes"][0]["no_split_reason"] == "单章覆盖即可。"


def test_suggest_outline_empty_requirement(client, db_session, seeded_kb):
    blueprint_id = _create_blueprint_for_suggest(client, seeded_kb.kb_id, db_session)
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/suggest-outline",
        json={"blueprint_ids": [blueprint_id], "requirement_description": "   "},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


def test_suggest_outline_blueprint_not_found(client, seeded_kb):
    missing_id = str(uuid4())
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/suggest-outline",
        json={
            "blueprint_ids": [missing_id],
            "requirement_description": "测试需求",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "blueprint_not_found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_blueprint_api.py::test_suggest_outline_happy_path -v`

Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Add route handler**

```python
# backend/src/api/routes/blueprints.py — add imports:
from src.api.schemas.blueprints import SuggestOutlineRequest
from src.services.knowledge.blueprint_outline_suggest_service import (
    OutlineSuggestFailedError,
    OutlineSuggestTimeoutError,
    suggest_outline,
)

# Add route BEFORE /{blueprint_id} routes to avoid path conflict:
@router.post("/suggest-outline")
def suggest_outline_api(
    kb_id: UUID,
    body: SuggestOutlineRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    requirement = body.requirement_description.strip()
    if not requirement:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "requirement_description is required", trace_id=get_trace_id()),
        )
    if len(requirement) > settings.blueprint_suggest_requirement_max:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "requirement_description too long", trace_id=get_trace_id()),
        )
    if len(body.blueprint_ids) > settings.blueprint_suggest_max_blueprints:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "too many blueprint_ids", trace_id=get_trace_id()),
        )

    try:
        result = suggest_outline(
            db,
            kb_id=kb_id,
            blueprint_ids=body.blueprint_ids,
            requirement_description=requirement,
        )
    except BlueprintNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("blueprint_not_found", "Blueprint not found", trace_id=get_trace_id()),
        )
    except OutlineSuggestTimeoutError:
        return JSONResponse(
            status_code=504,
            content=error("outline_suggest_timeout", "Outline suggest timed out", trace_id=get_trace_id()),
        )
    except OutlineSuggestFailedError as exc:
        message = str(exc)
        if message == "llm not configured":
            return JSONResponse(
                status_code=503,
                content=error("llm_not_configured", "LLM is not configured", trace_id=get_trace_id()),
            )
        if message in {"requirement_description empty", "requirement_description too long", "blueprint_ids empty", "too many blueprint_ids"}:
            return JSONResponse(
                status_code=400,
                content=error("invalid_request", message, trace_id=get_trace_id()),
            )
        logger.warning("outline suggest failed kb_id=%s reason=%s", kb_id, exc)
        return JSONResponse(
            status_code=502,
            content=error("outline_suggest_failed", "Outline suggest failed", trace_id=get_trace_id()),
        )
    return success(result, trace_id=get_trace_id())
```

同时在 `blueprints.py` 顶部补充 `from src.config import settings`。

- [ ] **Step 4: Run integration tests**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_blueprint_api.py -k suggest_outline -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/blueprints.py backend/tests/integration/test_blueprint_api.py
git commit -m "feat: add POST /blueprints/suggest-outline API"
```

---

## Task 6: 前端 API Client

**Files:**
- Modify: `frontend/src/services/blueprints.ts`

- [ ] **Step 1: Add types and API function**

```typescript
// frontend/src/services/blueprints.ts — append after BlueprintDraft interface region:

export interface SuggestOutlineRequest {
  blueprint_ids: string[];
  requirement_description: string;
}

export interface SuggestOutlineNode {
  title: string;
  content_suggestion: string;
  importance: ImportanceLevel;
  split_reason: string | null;
  no_split_reason: string | null;
  children: SuggestOutlineNode[];
}

export interface SuggestOutlineResult {
  outline_title: string;
  summary: string;
  nodes: SuggestOutlineNode[];
}

export async function suggestBlueprintOutline(
  kbId: string,
  body: SuggestOutlineRequest,
): Promise<SuggestOutlineResult> {
  return apiRequest<SuggestOutlineResult>(`/api/v1/kbs/${kbId}/blueprints/suggest-outline`, {
    method: "POST",
    body,
  });
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run typecheck`

Expected: PASS（若项目无 typecheck 脚本，用 `npx tsc --noEmit`）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/blueprints.ts
git commit -m "feat: add suggestBlueprintOutline API client"
```

---

## Task 7: 结果树组件

**Files:**
- Create: `frontend/src/components/Blueprint/BlueprintOutlineSuggestTree.tsx`

- [ ] **Step 1: Create tree component**

```tsx
// frontend/src/components/Blueprint/BlueprintOutlineSuggestTree.tsx
import { Tag, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import type { SuggestOutlineNode } from "../../services/blueprints";
import { getImportanceLevelLabel } from "../../constants/blueprintMeta";

const { Text, Paragraph } = Typography;

interface BlueprintOutlineSuggestTreeProps {
  nodes: SuggestOutlineNode[];
}

function renderNodeMeta(node: SuggestOutlineNode) {
  const hasChildren = (node.children?.length ?? 0) > 0;
  const reason = hasChildren ? node.split_reason : node.no_split_reason;
  const reasonLabel = hasChildren ? "拆分理由" : "不拆分理由";

  return (
    <div style={{ marginTop: 4, marginBottom: 8 }}>
      <Paragraph style={{ marginBottom: 4 }} type="secondary">
        {node.content_suggestion}
      </Paragraph>
      {reason ? (
        <Text type="secondary">
          {reasonLabel}：{reason}
        </Text>
      ) : null}
    </div>
  );
}

function toTreeData(nodes: SuggestOutlineNode[], parentPath = ""): DataNode[] {
  return nodes.map((node, index) => {
    const path = parentPath ? `${parentPath}-${index}` : String(index);
    const title = node.title?.trim() || "(未命名章节)";
    return {
      key: path,
      title: (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span>{title}</span>
          <Tag>{getImportanceLevelLabel(node.importance)}</Tag>
        </span>
      ),
      children: toTreeData(node.children ?? [], path),
    };
  });
}

export default function BlueprintOutlineSuggestTree({ nodes }: BlueprintOutlineSuggestTreeProps) {
  const treeData = toTreeData(nodes);

  return (
    <div>
      <Tree
        defaultExpandAll
        treeData={treeData}
        titleRender={(node) => (
          <div>
            {node.title as React.ReactNode}
            {renderNodeMeta(
              // recover node by key path
              nodes[
                Number(String(node.key).split("-")[0])
              ] /* simplified: use index walk below */
            )}
          </div>
        )}
      />
    </div>
  );
}
```

**实现注意：** `titleRender` 需通过 key path 递归定位 `SuggestOutlineNode`。推荐实现辅助函数：

```tsx
function getNodeByPath(nodes: SuggestOutlineNode[], path: string): SuggestOutlineNode | undefined {
  const parts = path.split("-").map((part) => Number(part));
  let current: SuggestOutlineNode[] = nodes;
  let found: SuggestOutlineNode | undefined;
  for (const index of parts) {
    found = current[index];
    if (!found) return undefined;
    current = found.children ?? [];
  }
  return found;
}

// titleRender:
titleRender={(node) => {
  const item = getNodeByPath(nodes, String(node.key));
  if (!item) return node.title;
  return (
    <div>
      {node.title as React.ReactNode}
      {renderNodeMeta(item)}
    </div>
  );
}}
```

并在文件顶部 `import type { ReactNode } from "react"`，将 `React.ReactNode` 换为 `ReactNode`。

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Blueprint/BlueprintOutlineSuggestTree.tsx
git commit -m "feat: add BlueprintOutlineSuggestTree component"
```

---

## Task 8: Drawer 组件

**Files:**
- Create: `frontend/src/components/Blueprint/BlueprintOutlineSuggestDrawer.tsx`

- [ ] **Step 1: Create drawer**

```tsx
// frontend/src/components/Blueprint/BlueprintOutlineSuggestDrawer.tsx
import { Alert, Button, Drawer, Empty, Input, Space, Spin, Typography, message } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../services/apiClient";
import {
  suggestBlueprintOutline,
  type SuggestOutlineResult,
} from "../../services/blueprints";
import BlueprintOutlineSuggestTree from "./BlueprintOutlineSuggestTree";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;
const MAX_REQUIREMENT_LEN = 2000;

interface BlueprintOutlineSuggestDrawerProps {
  open: boolean;
  kbId?: string;
  blueprintId?: string;
  onClose: () => void;
}

export default function BlueprintOutlineSuggestDrawer({
  open,
  kbId,
  blueprintId,
  onClose,
}: BlueprintOutlineSuggestDrawerProps) {
  const [requirement, setRequirement] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SuggestOutlineResult>();
  const [errorText, setErrorText] = useState<string>();
  const openRef = useRef(open);

  useEffect(() => {
    openRef.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) {
      setRequirement("");
      setResult(undefined);
      setErrorText(undefined);
      setLoading(false);
    }
  }, [open]);

  const handleGenerate = useCallback(async () => {
    const trimmed = requirement.trim();
    if (!trimmed) {
      message.warning("请输入目录需求描述");
      return;
    }
    if (!kbId || !blueprintId) {
      return;
    }

    setLoading(true);
    setErrorText(undefined);
    setResult(undefined);
    try {
      const data = await suggestBlueprintOutline(kbId, {
        blueprint_ids: [blueprintId],
        requirement_description: trimmed,
      });
      if (!openRef.current) {
        return;
      }
      setResult(data);
    } catch (error) {
      if (!openRef.current) {
        return;
      }
      if (error instanceof ApiError) {
        if (error.status === 504) {
          setErrorText("生成超时，请精简需求后重试");
        } else {
          setErrorText(error.message || "生成失败，请稍后重试");
        }
      } else {
        setErrorText((error as Error).message || "生成失败，请稍后重试");
      }
    } finally {
      if (openRef.current) {
        setLoading(false);
      }
    }
  }, [blueprintId, kbId, requirement]);

  return (
    <Drawer
      title="目录建议"
      placement="right"
      width="50%"
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div>
          <Text strong>目录需求描述</Text>
          <TextArea
            rows={6}
            maxLength={MAX_REQUIREMENT_LEN}
            showCount
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            placeholder="描述项目背景、招标要求、希望突出的章节、评分关注点等……"
            disabled={loading}
          />
        </div>
        <Button type="primary" onClick={() => void handleGenerate()} loading={loading}>
          生成建议
        </Button>

        <div style={{ minHeight: 240 }}>
          {errorText ? <Alert type="error" message={errorText} showIcon /> : null}
          {loading ? <Spin style={{ display: "block", marginTop: 24 }} /> : null}
          {!loading && !result && !errorText ? (
            <Empty description="填写需求后点击「生成建议」" />
          ) : null}
          {result ? (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div>
                <Text strong>{result.outline_title}</Text>
                <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  {result.summary}
                </Paragraph>
              </div>
              <BlueprintOutlineSuggestTree nodes={result.nodes} />
            </Space>
          ) : null}
        </div>
      </Space>
    </Drawer>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Blueprint/BlueprintOutlineSuggestDrawer.tsx
git commit -m "feat: add BlueprintOutlineSuggestDrawer"
```

---

## Task 9: 详情页集成

**Files:**
- Modify: `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx`

- [ ] **Step 1: Wire button and drawer**

```tsx
// BlueprintDetailPage.tsx — add imports:
import BlueprintOutlineSuggestDrawer from "../../components/Blueprint/BlueprintOutlineSuggestDrawer";

// add state:
const [suggestOpen, setSuggestOpen] = useState(false);

// in Card extra Space, before 返回列表:
<Button onClick={() => setSuggestOpen(true)}>目录建议</Button>

// before closing </Space> of page root:
<BlueprintOutlineSuggestDrawer
  open={suggestOpen}
  kbId={selectedKbId}
  blueprintId={id}
  onClose={() => setSuggestOpen(false)}
/>
```

- [ ] **Step 2: Manual smoke test**

1. 启动后端与前端
2. 打开任一蓝图详情页
3. 点击「目录建议」→ Drawer 从右侧展开占 50%
4. 空需求点击生成 → 前端 warning
5. 填写需求 + mock/真实 LLM → 展示标题、summary、树形结果

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Knowledge/BlueprintDetailPage.tsx
git commit -m "feat: add outline suggest entry on blueprint detail page"
```

---

## Task 10: 全量验证

- [ ] **Step 1: Run backend tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_config.py tests/unit/test_blueprint_outline_suggest_service.py tests/integration/test_blueprint_api.py -v`

Expected: ALL PASS

- [ ] **Step 2: Run frontend typecheck**

Run: `cd frontend && npx tsc --noEmit`

Expected: PASS

- [ ] **Step 3: Final commit if any fixups**

```bash
git status
# commit any remaining fixups with message:
# fix: address outline suggest review findings
```

---

## Spec Coverage Checklist

| Spec 要求 | 对应 Task |
|-----------|-----------|
| POST `/suggest-outline` | Task 5 |
| `blueprint_ids[]` 多蓝图 | Task 4–5（V1 UI 传单个） |
| 自由文本需求 ≤2000 | Task 4–5, Task 8 |
| 无状态不落库 | Task 4（无 DB 写） |
| split/no_split 互斥校验 | Task 3 |
| 深度 ≤4 校验 | Task 3 |
| 错误码 400/404/502/503/504 | Task 5 |
| 独立 suggest 服务 | Task 3–4 |
| `blueprint_suggest_*` 配置 | Task 1 |
| Drawer 50% 右侧 | Task 8 |
| 详情页按钮 | Task 9 |
| 结果树展示 | Task 7 |
| 关闭 Drawer 丢弃状态 | Task 8 `destroyOnClose` + reset effect |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-22-blueprint-outline-suggest.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间做代码审查，迭代快

**2. Inline Execution** — 在本会话用 executing-plans 按 Task 批量执行，检查点暂停供你审阅

你想用哪种方式？
