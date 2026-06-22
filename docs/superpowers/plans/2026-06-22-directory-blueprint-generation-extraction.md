# Directory Blueprint Generation Extraction (V1.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在目录蓝图 V1 上增量交付「目录生成能力提取」：从章节目录 + `content_preview` 聚合摘要生成 `content_description`、`tender_response_hint`、`suggested_structure_md`，全栈持久化与编辑。

**Architecture:** 扩展 `blueprint_generate_service` 输入与 Prompt；新增 3 个 DB 列；`blueprint_service` 保存时截断；前端 `BlueprintEditor` 增加「建议目录结构」卡片与节点「生成指导」分组。单次 `POST /blueprints/generate` 产出全部新字段。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, pytest; React 18, TypeScript, Ant Design 5.

**Design spec:** `docs/superpowers/specs/2026-06-22-directory-blueprint-generation-extraction-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/services/knowledge/blueprint_field_utils.py` | 字段长度常量 + 截断工具（新建） |
| `backend/alembic/versions/20260622_1000_blueprint_generation_extraction.py` | 三列 DDL |
| `backend/src/models/knowledge_blueprint.py` | +`suggested_structure_md` |
| `backend/src/models/knowledge_blueprint_node.py` | +`content_description`, `tender_response_hint` |
| `backend/src/services/knowledge/blueprint_generate_service.py` | 摘要聚合、Prompt、解析 |
| `backend/src/services/knowledge/blueprint_service.py` | CRUD 透传 + 保存截断 |
| `backend/src/api/schemas/blueprints.py` | Pydantic 扩展 |
| `backend/tests/unit/test_blueprint_field_utils.py` | 截断工具测试（新建） |
| `backend/tests/unit/test_blueprint_content_summary.py` | 摘要聚合测试（新建） |
| `backend/tests/unit/test_blueprint_generate_service.py` | 扩展 generate 测试 |
| `backend/tests/unit/test_blueprint_service.py` | 新字段 round-trip |
| `backend/tests/integration/test_blueprint_api.py` | API 端到端 |
| `frontend/src/services/blueprints.ts` | TS 类型 |
| `frontend/src/components/Blueprint/BlueprintSuggestedStructure.tsx` | 建议目录结构卡片（新建） |
| `frontend/src/components/Blueprint/BlueprintNodeDetailPanel.tsx` | 生成指导分组 |
| `frontend/src/components/Blueprint/BlueprintEditor.tsx` | 集成新卡片 |
| `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx` | 只读展示 |

---

## Task 1: 字段截断工具

**Files:**
- Create: `backend/src/services/knowledge/blueprint_field_utils.py`
- Create: `backend/tests/unit/test_blueprint_field_utils.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_blueprint_field_utils.py
from src.services.knowledge.blueprint_field_utils import (
    CONTENT_DESCRIPTION_MAX,
    SUGGESTED_STRUCTURE_MD_MAX,
    TENDER_RESPONSE_HINT_MAX,
    truncate_blueprint_field,
)


def test_truncate_blueprint_field_returns_none_for_blank():
    assert truncate_blueprint_field("   ", max_len=200) is None


def test_truncate_blueprint_field_truncates_long_text():
    text = "章" * 250
    result = truncate_blueprint_field(text, max_len=CONTENT_DESCRIPTION_MAX)
    assert result is not None
    assert len(result) == CONTENT_DESCRIPTION_MAX


def test_constants_match_design_spec():
    assert CONTENT_DESCRIPTION_MAX == 200
    assert TENDER_RESPONSE_HINT_MAX == 300
    assert SUGGESTED_STRUCTURE_MD_MAX == 1500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_field_utils.py -v`

Expected: FAIL with `ModuleNotFoundError: blueprint_field_utils`

- [ ] **Step 3: Implement utility**

```python
# backend/src/services/knowledge/blueprint_field_utils.py
from __future__ import annotations

CONTENT_SUMMARY_MAX = 800
CONTENT_DESCRIPTION_MAX = 200
TENDER_RESPONSE_HINT_MAX = 300
SUGGESTED_STRUCTURE_MD_MAX = 1500


def truncate_blueprint_field(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_field_utils.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_field_utils.py backend/tests/unit/test_blueprint_field_utils.py
git commit -m "feat: add blueprint field truncation utilities"
```

---

## Task 2: 数据库 Migration + ORM

**Files:**
- Create: `backend/alembic/versions/20260622_1000_blueprint_generation_extraction.py`
- Modify: `backend/src/models/knowledge_blueprint.py`
- Modify: `backend/src/models/knowledge_blueprint_node.py`

- [ ] **Step 1: Create migration**

```python
# backend/alembic/versions/20260622_1000_blueprint_generation_extraction.py
"""blueprint generation extraction fields

Revision ID: 20260622_1000
Revises: 20260621_1200_widen_blueprint_text_fields
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_1000"
down_revision: str | None = "20260621_1200_widen_blueprint_text_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_blueprints",
        sa.Column("suggested_structure_md", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("content_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("tender_response_hint", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_blueprint_nodes", "tender_response_hint")
    op.drop_column("knowledge_blueprint_nodes", "content_description")
    op.drop_column("knowledge_blueprints", "suggested_structure_md")
```

- [ ] **Step 2: Update ORM models**

In `backend/src/models/knowledge_blueprint.py`, after `usual_page_range`:

```python
    suggested_structure_md: Mapped[str | None] = mapped_column(Text, nullable=True)
```

In `backend/src/models/knowledge_blueprint_node.py`, after `writing_hint`:

```python
    content_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tender_response_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Run migration (dev DB)**

Run: `cd backend && ../.venv/bin/alembic upgrade head`

Expected: migration applies without error

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/20260622_1000_blueprint_generation_extraction.py \
  backend/src/models/knowledge_blueprint.py \
  backend/src/models/knowledge_blueprint_node.py
git commit -m "feat: add blueprint generation extraction columns"
```

---

## Task 3: 子树 content_preview 聚合

**Files:**
- Modify: `backend/src/services/knowledge/blueprint_generate_service.py`
- Create: `backend/tests/unit/test_blueprint_content_summary.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_blueprint_content_summary.py
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.knowledge.blueprint_generate_service import (
    aggregate_content_summary,
    collect_subtree_outline,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_tree_with_body(db_session, kb_id):
    file_import = FileImport(
        kb_id=kb_id,
        file_name="summary.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/summary.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="summary.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    root_id = uuid4()
    child_heading_id = uuid4()
    root = DocumentTreeNode(
        node_id=root_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="第一章",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    child_heading = DocumentTreeNode(
        node_id=child_heading_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=root_id,
        node_type=DocumentTreeNodeType.heading,
        title="1.1 技术方案",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    paragraph = DocumentTreeNode(
        node_id=uuid4(),
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=child_heading_id,
        node_type=DocumentTreeNodeType.paragraph,
        title=None,
        level=None,
        sort_order=2,
        content_preview="总体架构采用微服务部署。",
        tree_version=1,
    )
    db_session.add_all([root, child_heading, paragraph])
    db_session.commit()
    return document, root, child_heading


def test_aggregate_content_summary_joins_non_heading_previews():
    nodes = [
        type("N", (), {
            "node_id": uuid4(),
            "parent_id": None,
            "node_type": DocumentTreeNodeType.heading,
            "sort_order": 0,
            "content_preview": None,
        })(),
        type("N", (), {
            "node_id": uuid4(),
            "parent_id": None,
            "node_type": DocumentTreeNodeType.paragraph,
            "sort_order": 1,
            "content_preview": "第一段。",
        })(),
        type("N", (), {
            "node_id": uuid4(),
            "parent_id": None,
            "node_type": DocumentTreeNodeType.paragraph,
            "sort_order": 2,
            "content_preview": "第二段。",
        })(),
    ]
    root_id = nodes[0].node_id
    nodes[1].parent_id = root_id
    nodes[2].parent_id = root_id

    summary = aggregate_content_summary(nodes, root_id=root_id)
    assert "第一段" in summary
    assert "第二段" in summary


def test_collect_subtree_outline_includes_content_summary(db_session, seeded_kb):
    document, root, child_heading = _seed_tree_with_body(db_session, seeded_kb.kb_id)

    outline = collect_subtree_outline(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=root.node_id,
    )

    child = outline["children"][0]
    assert child["node_title"] == "1.1 技术方案"
    assert "微服务" in child.get("content_summary", "")
    assert outline.get("content_summary", "") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_content_summary.py -v`

Expected: FAIL with `ImportError: cannot import name 'aggregate_content_summary'`

- [ ] **Step 3: Implement aggregation in blueprint_generate_service.py**

Add imports at top:

```python
from src.services.knowledge.blueprint_field_utils import CONTENT_SUMMARY_MAX, truncate_blueprint_field
```

Add function before `collect_subtree_outline`:

```python
def aggregate_content_summary(
    nodes: list[DocumentTreeNode],
    *,
    root_id: UUID,
) -> str:
    """Collect non-heading content_preview under root heading subtree."""
    children_by_parent: dict[UUID | None, list[DocumentTreeNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    parts: list[str] = []

    def walk(node_id: UUID) -> None:
        for child in sorted(children_by_parent.get(node_id, []), key=lambda n: n.sort_order):
            if child.node_type != DocumentTreeNodeType.heading:
                preview = (child.content_preview or "").strip()
                if preview:
                    parts.append(preview)
            else:
                walk(child.node_id)

    walk(root_id)
    joined = "\n".join(parts).strip()
    return truncate_blueprint_field(joined, max_len=CONTENT_SUMMARY_MAX) or ""
```

Update `collect_subtree_outline` to load **all** node types (remove heading-only filter), build `children_by_parent`, and in `build(node)`:

```python
    def build(node: DocumentTreeNode) -> dict[str, Any]:
        child_headings = [
            child
            for child in children_by_parent.get(node.node_id, [])
            if child.node_type == DocumentTreeNodeType.heading
        ]
        return {
            "node_title": node.title or "",
            "node_level": int(node.level or 1),
            "content_summary": aggregate_content_summary(nodes, root_id=node.node_id),
            "children": [build(child) for child in child_headings],
        }
```

Replace the existing heading-only query with:

```python
    nodes = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == doc_id,
        )
        .order_by(
            DocumentTreeNode.sort_order.asc(),
            DocumentTreeNode.level.asc().nulls_last(),
            DocumentTreeNode.created_at.asc(),
        )
        .all()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_content_summary.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_generate_service.py \
  backend/tests/unit/test_blueprint_content_summary.py
git commit -m "feat: aggregate content_preview summaries for blueprint generate input"
```

---

## Task 4: LLM Prompt 与解析扩展

**Files:**
- Modify: `backend/src/services/knowledge/blueprint_generate_service.py`
- Modify: `backend/tests/unit/test_blueprint_generate_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_blueprint_generate_service.py`:

```python
MOCK_LLM_JSON_V11 = {
    **MOCK_LLM_JSON,
    "suggested_structure_md": "## 技术方案模块\n- 映射：1.1 技术方案",
    "nodes": [
        {
            **MOCK_LLM_JSON["nodes"][0],
            "content_description": "描述总体架构与部署方式。",
            "tender_response_hint": "需响应技术规格书中的架构要求。",
        }
    ],
}


def test_generate_returns_generation_extraction_fields(db_session, seeded_kb, monkeypatch):
    document, root, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **kw: json.dumps(MOCK_LLM_JSON_V11, ensure_ascii=False),
    )

    result = generate_blueprint_draft(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=root.node_id,
    )

    assert result["suggested_structure_md"].startswith("## 技术方案")
    root_node = result["nodes"][0]
    child = root_node["children"][0]
    assert child["content_description"] == "描述总体架构与部署方式。"
    assert child["tender_response_hint"] == "需响应技术规格书中的架构要求。"


def test_estimate_max_tokens_uses_higher_per_node_budget():
    assert _estimate_max_tokens(subtree_node_count=6) == 2792
```

Update existing test `test_estimate_max_tokens_scales_with_subtree_size` expected values:

```python
def test_estimate_max_tokens_scales_with_subtree_size():
    assert _estimate_max_tokens(subtree_node_count=6) == 2792
    assert _estimate_max_tokens(subtree_node_count=100) == 20480
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_generate_service.py::test_generate_returns_generation_extraction_fields -v`

Expected: FAIL (`KeyError: 'suggested_structure_md'` or assertion on missing fields)

- [ ] **Step 3: Extend generate service**

Update `_SYSTEM_PROMPT` string to append:

```python
    "suggested_structure_md, nodes。"
    # change nodes line to include:
    "nodes 为树结构，每个节点包含：node_title, node_level, purpose, writing_goal, "
    "writing_hint, content_description, tender_response_hint, required_flag, recommended_flag, "
    "content_type, keyword_hint, children。"
    "顶层另含 suggested_structure_md：按逻辑模块用 Markdown 分段描述建议目录组织。"
    "content_description 与 tender_response_hint 各 1-2 句；tender_response_hint 无线索可省略。"
```

Update `_estimate_max_tokens`:

```python
    per_node = 380
```

Update `_build_user_prompt`:

```python
    return truncate_for_llm(f"目录子树（含 content_summary）：\n{outline_json}")
```

In `generate_blueprint_draft` return dict, add:

```python
        "suggested_structure_md": truncate_blueprint_field(
            _as_optional_text(parsed.get("suggested_structure_md")),
            max_len=SUGGESTED_STRUCTURE_MD_MAX,
        ),
```

Add imports:

```python
from src.services.knowledge.blueprint_field_utils import (
    CONTENT_DESCRIPTION_MAX,
    SUGGESTED_STRUCTURE_MD_MAX,
    TENDER_RESPONSE_HINT_MAX,
    truncate_blueprint_field,
)
```

In `_normalize_nodes`, inside normalized.append dict:

```python
                "content_description": truncate_blueprint_field(
                    _as_optional_text(node.get("content_description")),
                    max_len=CONTENT_DESCRIPTION_MAX,
                ),
                "tender_response_hint": truncate_blueprint_field(
                    _as_optional_text(node.get("tender_response_hint")),
                    max_len=TENDER_RESPONSE_HINT_MAX,
                ),
```

In `_wrap_nodes_with_source_root`, extend `root_fields` defaults and matched branch:

```python
        "content_description": None,
        "tender_response_hint": None,
```

And when copying from matched root:

```python
            "content_description": matched.get("content_description"),
            "tender_response_hint": matched.get("tender_response_hint"),
```

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_generate_service.py -v`

Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_generate_service.py \
  backend/tests/unit/test_blueprint_generate_service.py
git commit -m "feat: extend blueprint generate prompt and parsing for V1.1 fields"
```

---

## Task 5: blueprint_service 持久化

**Files:**
- Modify: `backend/src/services/knowledge/blueprint_service.py`
- Modify: `backend/tests/unit/test_blueprint_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_blueprint_service.py`:

```python
from src.services.knowledge.blueprint_service import get_blueprint_detail


def test_create_persists_generation_extraction_fields(db_session, seeded_kb):
    payload = _payload()
    payload["suggested_structure_md"] = "## 模块\n- 技术方案"
    payload["nodes"] = [
        {
            "node_title": "章节一",
            "node_level": 1,
            "node_order": 1,
            "importance_level": "required",
            "content_description": "写架构设计。",
            "tender_response_hint": "响应星号条款。",
            "children": [],
        }
    ]
    blueprint = create_blueprint(db_session, kb_id=seeded_kb.kb_id, payload=payload)
    db_session.commit()

    detail = get_blueprint_detail(
        db_session,
        kb_id=seeded_kb.kb_id,
        blueprint_id=blueprint.blueprint_id,
    )
    assert detail["suggested_structure_md"] == "## 模块\n- 技术方案"
    assert detail["nodes"][0]["content_description"] == "写架构设计。"
    assert detail["nodes"][0]["tender_response_hint"] == "响应星号条款。"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_service.py::test_create_persists_generation_extraction_fields -v`

Expected: FAIL (`KeyError` or `assert None == ...`)

- [ ] **Step 3: Update blueprint_service.py**

Add import:

```python
from src.services.knowledge.blueprint_field_utils import (
    CONTENT_DESCRIPTION_MAX,
    SUGGESTED_STRUCTURE_MD_MAX,
    TENDER_RESPONSE_HINT_MAX,
    truncate_blueprint_field,
)
```

In `create_blueprint`, after `usual_page_range`:

```python
        suggested_structure_md=truncate_blueprint_field(
            payload.get("suggested_structure_md"),
            max_len=SUGGESTED_STRUCTURE_MD_MAX,
        ),
```

In `update_blueprint`, after `usual_page_range` assignment:

```python
    if "suggested_structure_md" in payload:
        blueprint.suggested_structure_md = truncate_blueprint_field(
            payload.get("suggested_structure_md"),
            max_len=SUGGESTED_STRUCTURE_MD_MAX,
        )
```

In `replace_nodes`, inside `KnowledgeBlueprintNode(...)`:

```python
                content_description=truncate_blueprint_field(
                    node.get("content_description"),
                    max_len=CONTENT_DESCRIPTION_MAX,
                ),
                tender_response_hint=truncate_blueprint_field(
                    node.get("tender_response_hint"),
                    max_len=TENDER_RESPONSE_HINT_MAX,
                ),
```

In `get_blueprint_detail` flat_nodes dict:

```python
            "content_description": node.content_description,
            "tender_response_hint": node.tender_response_hint,
```

In return dict:

```python
        "suggested_structure_md": blueprint.suggested_structure_md,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_service.py \
  backend/tests/unit/test_blueprint_service.py
git commit -m "feat: persist blueprint generation extraction fields in service layer"
```

---

## Task 6: API Schema + 集成测试

**Files:**
- Modify: `backend/src/api/schemas/blueprints.py`
- Modify: `backend/tests/integration/test_blueprint_api.py`

- [ ] **Step 1: Write the failing integration test**

Append to `backend/tests/integration/test_blueprint_api.py`:

```python
MOCK_LLM_JSON_V11 = """
{
  "outline_title": "供应链方案通用大纲",
  "overall_strategy": "强调仓配能力",
  "suggested_structure_md": "## 技术模块\\n- 总体设计",
  "nodes": [{
    "node_title": "总体设计", "node_level": 1, "children": [],
    "purpose": "p", "writing_goal": "g", "writing_hint": "h",
    "content_description": "写总体设计思路。",
    "tender_response_hint": "响应评分点。",
    "required_flag": true, "recommended_flag": false,
    "content_type": "text", "keyword_hint": ["供应链"]
  }]
}
""".strip()


def test_generate_create_get_includes_v11_fields(client, db_session, seeded_kb, monkeypatch):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **_: MOCK_LLM_JSON_V11,
    )

    generate_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/generate",
        json={"doc_id": str(document.document_id), "node_id": str(parent.node_id)},
    )
    assert generate_resp.status_code == 200
    draft = generate_resp.json()["data"]
    assert draft["suggested_structure_md"].startswith("## 技术模块")
    assert draft["nodes"][0]["content_description"] == "写总体设计思路。"

    create_resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=draft)
    assert create_resp.status_code == 201
    blueprint_id = create_resp.json()["data"]["blueprint_id"]

    detail_resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/{blueprint_id}")
    detail = detail_resp.json()["data"]
    assert detail["suggested_structure_md"].startswith("## 技术模块")
    assert detail["nodes"][0]["tender_response_hint"] == "响应评分点。"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_blueprint_api.py::test_generate_create_get_includes_v11_fields -v`

Expected: FAIL (field missing in response)

- [ ] **Step 3: Update Pydantic schemas**

In `backend/src/api/schemas/blueprints.py`, add to `BlueprintNodeInput`:

```python
    content_description: str | None = None
    tender_response_hint: str | None = None
```

Add to `SaveBlueprintRequest`:

```python
    suggested_structure_md: str | None = None
```

No route changes needed — schemas flow through existing handlers.

- [ ] **Step 4: Run integration tests**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_blueprint_api.py -v`

Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/schemas/blueprints.py backend/tests/integration/test_blueprint_api.py
git commit -m "feat: expose blueprint V1.1 fields in API schemas and integration tests"
```

---

## Task 7: 前端类型与建议目录结构组件

**Files:**
- Modify: `frontend/src/services/blueprints.ts`
- Create: `frontend/src/components/Blueprint/BlueprintSuggestedStructure.tsx`

- [ ] **Step 1: Extend TypeScript types**

In `frontend/src/services/blueprints.ts`:

```typescript
export interface BlueprintNode {
  // ...existing fields
  content_description?: string | null;
  tender_response_hint?: string | null;
}

export interface BlueprintDraft {
  // ...existing fields
  suggested_structure_md?: string | null;
}
```

- [ ] **Step 2: Create BlueprintSuggestedStructure.tsx**

```tsx
import { Card, Input, Typography } from "antd";
import type { BlueprintDraft } from "../../services/blueprints";

const { Text } = Typography;

interface BlueprintSuggestedStructureProps {
  value: BlueprintDraft;
  readOnly?: boolean;
  onChange: (next: BlueprintDraft) => void;
}

export default function BlueprintSuggestedStructure({
  value,
  readOnly,
  onChange,
}: BlueprintSuggestedStructureProps) {
  return (
    <Card title="建议目录结构" size="small">
      <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
        按逻辑模块描述建议的目录组织方式，可引用源章节标题。
      </Text>
      <Input.TextArea
        rows={6}
        value={value.suggested_structure_md ?? ""}
        readOnly={readOnly}
        placeholder={"例如：\n## 技术方案模块\n- 总体架构（对应 1.1）\n- 实施方案（对应 1.2）"}
        onChange={(event) =>
          onChange({ ...value, suggested_structure_md: event.target.value || null })
        }
      />
    </Card>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run build`

Expected: build succeeds (no TS errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/blueprints.ts \
  frontend/src/components/Blueprint/BlueprintSuggestedStructure.tsx
git commit -m "feat: add blueprint suggested structure component and types"
```

---

## Task 8: 节点详情与编辑器集成

**Files:**
- Modify: `frontend/src/components/Blueprint/BlueprintNodeDetailPanel.tsx`
- Modify: `frontend/src/components/Blueprint/BlueprintEditor.tsx`

- [ ] **Step 1: Update BlueprintNodeDetailPanel**

Add import: `Collapse` from `antd`.

Wrap existing purpose/writing fields in `Collapse` panel key `writing-strategy`, label `写作策略`.

Before Collapse, add open「生成指导」section:

```tsx
      <Typography.Text strong>生成指导</Typography.Text>
      <Form.Item label="内容描述" style={{ marginTop: 8 }}>
        <Input.TextArea
          rows={2}
          value={node.content_description ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ content_description: event.target.value || null })}
          placeholder="本章应写什么（1-2 句）"
        />
      </Form.Item>
      <Form.Item label="应标/得分/应答提示">
        <Input.TextArea
          rows={2}
          value={node.tender_response_hint ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ tender_response_hint: event.target.value || null })}
          placeholder="从历史章节推断，遇则填写，可留空"
        />
      </Form.Item>
```

- [ ] **Step 2: Wire BlueprintEditor**

In `BlueprintEditor.tsx`:

```tsx
import BlueprintSuggestedStructure from "./BlueprintSuggestedStructure";
```

After meta Card, before Row:

```tsx
      <BlueprintSuggestedStructure
        value={value}
        readOnly={readOnly}
        onChange={onChange}
      />
```

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Blueprint/BlueprintNodeDetailPanel.tsx \
  frontend/src/components/Blueprint/BlueprintEditor.tsx
git commit -m "feat: integrate generation guidance fields in blueprint editor UI"
```

---

## Task 9: 蓝图详情页只读展示

**Files:**
- Modify: `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx`

- [ ] **Step 1: Add read-only display for new fields**

In the non-editing `Descriptions` or detail section, add:

```tsx
<Descriptions.Item label="建议目录结构" span={2}>
  {draft?.suggested_structure_md?.trim() ? (
    <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
      {draft.suggested_structure_md}
    </Paragraph>
  ) : (
    "—"
  )}
</Descriptions.Item>
```

`BlueprintNodeDetailPanel` in read-only mode already shows new node fields once Task 8 is done.

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Knowledge/BlueprintDetailPage.tsx
git commit -m "feat: show suggested structure in blueprint detail page"
```

---

## Task 10: 全量验证

**Files:** (none — verification only)

- [ ] **Step 1: Run backend blueprint tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_field_utils.py tests/unit/test_blueprint_content_summary.py tests/unit/test_blueprint_generate_service.py tests/unit/test_blueprint_service.py tests/integration/test_blueprint_api.py -v`

Expected: all PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 3: Manual smoke (optional but recommended)**

1. 录入页选有正文章节 → 【提取目录蓝图】→ 检查建议目录结构 + 节点生成指导  
2. 编辑保存 → 蓝图详情页回显  
3. 重新生成 → 新字段被覆盖  

---

## Spec Coverage Self-Review

| Spec 要求 | 对应 Task |
|-----------|-----------|
| `content_summary` 聚合输入 | Task 3 |
| LLM Prompt 扩展三字段 | Task 4 |
| DB 三列迁移 | Task 2 |
| 保存截断 200/300/1500 | Task 1, 5 |
| API generate/save/detail 透传 | Task 5, 6 |
| 前端建议目录结构卡片 | Task 7, 8 |
| 节点生成指导 UI | Task 8 |
| 详情页只读展示 | Task 9 |
| 单元 + 集成测试 | Task 1–6, 10 |
| Epic 6 不对接 | 未纳入（符合 spec Out of Scope） |

**Placeholder scan:** 无 TBD / 相似省略步骤。  
**Type consistency:** `content_description` / `tender_response_hint` / `suggested_structure_md` 命名在 ORM、service、schema、TS 中一致。
