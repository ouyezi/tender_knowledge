# Epic 2 澄清增量（知识块分类 + 分批 LLM）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已实现的 Epic 2 模板解析链路上，对齐 2026-06-12 三项澄清：知识块级分类（非文件级）、环境变量 LLM 可切换且失败降级、大文件禁止整文件 LLM（按块分批 + `llm_progress`）。

**Architecture:** Phase A 沿用现有 `docx_outline_parser` + `docx_content_extractor`（无 LLM）；新增 `KnowledgeChunk` 与 `chunk_classification_service` 执行 Phase B 逐块分类；`template_parse_runner` 编排两阶段并写回 `template_parse_suggestions` JSON；前端确认向导 Step2/3 展示/编辑块级分类。同步 Phase B（同一 `_run_entry` 完成后再 `parse_ready`）。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pydantic-settings, 已有 `llm_client.py` | React 18, Ant Design 5 | pytest

**Design doc:** `docs/superpowers/specs/2026-06-12-epic2-clarification-delta-design.md`  
**Spec Kit:** `specs/003-template-parse-publish/spec.md` (FR-004a, FR-021–FR-023, SC-008)  
**Base plan (P0–P4 已完成部分):** `docs/superpowers/plans/2026-06-12-epic2-template-parse-publish.md`

---

## File Map（本增量）

| 路径 | 职责 |
|------|------|
| `backend/src/models/template_parse_task.py` | +`llm_progress` JSON |
| `backend/src/models/candidate_knowledge_stub.py` | +`suggestion_source`, `classification_confidence`, `chunk_ref`, `suggested_knowledge_type` |
| `backend/src/services/knowledge_chunk.py` | `KnowledgeChunk` dataclass + `build_knowledge_chunks` + `merge_classifications_into_suggestion` |
| `backend/src/services/chunk_classification_service.py` | 规则匹配 Epic 0 分类 + 可选 LLM + 降级 |
| `backend/src/services/classification_rule_index.py` | 从 DB 加载 KB 分类别名索引（供规则匹配） |
| `backend/src/services/template_parse_runner.py` | Phase A/B 编排；移除 file 级 product_category 默认 |
| `backend/src/services/template_confirm_service.py` | stub 块级字段；禁止 template 级 fallback 继承 |
| `backend/src/api/routes/template_parse.py` | 序列化 `llm_progress`、块级 suggestion 字段 |
| `backend/tests/unit/test_knowledge_chunk.py` | 块构建单测 |
| `backend/tests/unit/test_chunk_classification_service.py` | 规则/降级/LLM mock 单测 |
| `backend/tests/integration/test_template_parse_runner.py` | 扩展 llm_progress + 块级字段断言 |
| `backend/tests/integration/test_template_chunk_classification_flow.py` | 确认后 stub 块级持久化 |
| `frontend/src/services/templates.ts` | TS 类型 + `llm_progress` |
| `frontend/src/pages/TemplateLibraryCenter/ParseConfirmWizard.tsx` | Step1/2/3 块级分类 UI |
| `frontend/src/pages/TemplateLibraryCenter/index.tsx` | 待办区 llm_progress 文案（running 时） |

---

## Task 1: ORM 字段扩展

**Files:**
- Modify: `backend/src/models/template_parse_task.py`
- Modify: `backend/src/models/candidate_knowledge_stub.py`
- Test: `backend/tests/integration/test_template_model.py`（或新建 smoke）

- [ ] **Step 1: 写失败测试 — parse task 可存 llm_progress**

```python
# backend/tests/integration/test_template_model.py 末尾追加
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus


def test_template_parse_task_persists_llm_progress(db_session, seeded_kb):
    import uuid
    from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType

    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="t.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/t.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.template_file,
        created_by="admin",
    )
    db_session.add(imp)
    db_session.flush()
    task = TemplateParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        status=TemplateParseTaskStatus.running,
        llm_progress={
            "total_chunks": 3,
            "completed_chunks": 1,
            "failed_chunks": 0,
            "degraded_to_rule": 0,
            "batch_size": 1,
        },
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    assert task.llm_progress["total_chunks"] == 3
```

- [ ] **Step 2: 运行测试确认 FAIL**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_template_model.py::test_template_parse_task_persists_llm_progress -v
```

Expected: FAIL — `TemplateParseTask` has no attribute `llm_progress`

- [ ] **Step 3: 实现 ORM 变更**

`backend/src/models/template_parse_task.py` — imports 增加 `JSON`，类内增加：

```python
llm_progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
```

`backend/src/models/candidate_knowledge_stub.py` — 增加：

```python
from src.models.template_parse_suggestion import TemplateSuggestionSource  # 或本地 Enum 复用

suggested_knowledge_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
suggestion_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
classification_confidence: Mapped[float | None] = mapped_column(nullable=True)
chunk_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
```

（若 SQLite 不支持 float nullable 无类型，用 `Mapped[float | None] = mapped_column(nullable=True)` 或 `Numeric`。）

- [ ] **Step 4: 运行测试确认 PASS**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_template_model.py::test_template_parse_task_persists_llm_progress -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/template_parse_task.py backend/src/models/candidate_knowledge_stub.py backend/tests/integration/test_template_model.py
git commit -m "feat(epic2): add llm_progress and stub classification columns"
```

---

## Task 2: KnowledgeChunk 构建与合并

**Files:**
- Create: `backend/src/services/knowledge_chunk.py`
- Test: `backend/tests/unit/test_knowledge_chunk.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_knowledge_chunk.py
from src.services.docx_outline_parser import OutlineNode
from src.services.knowledge_chunk import build_knowledge_chunks, merge_classifications_into_suggestion


def test_build_knowledge_chunks_from_outline_and_materials():
    nodes = [
        OutlineNode(temp_id="n1", parent_temp_id=None, title="1. 售后服务方案", level=1, sort_order=0, needs_manual_review=False),
    ]
    materials = [
        {"temp_id": "m1", "chapter_temp_id": "n1", "title": "固定说明", "content": "我们提供7x24支持", "material_type": "fixed_paragraph"},
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
    from src.services.knowledge_chunk import KnowledgeChunk, ChunkClassificationResult

    chunks = build_knowledge_chunks(
        outline_nodes=[OutlineNode(temp_id="n1", parent_temp_id=None, title="售后服务", level=1, sort_order=0, needs_manual_review=False)],
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
```

- [ ] **Step 2: 运行确认 FAIL**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: 实现 knowledge_chunk.py**

```python
# backend/src/services/knowledge_chunk.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from src.services.docx_outline_parser import OutlineNode

ChunkType = Literal["chapter", "material", "candidate"]


@dataclass
class KnowledgeChunk:
    chunk_ref: str
    chunk_type: ChunkType
    title: str
    content_preview: str
    parent_chunk_ref: str | None = None


@dataclass
class ChunkClassificationResult:
    suggested_product_category_ids: list[UUID] = field(default_factory=list)
    suggested_chapter_taxonomy_id: UUID | None = None
    suggested_knowledge_type: str | None = None
    classification_confidence: float = 0.5
    suggestion_source: Literal["rule", "llm", "hybrid"] = "rule"
    classification_rationale: str | None = None


def build_knowledge_chunks(
    *,
    outline_nodes: list[OutlineNode],
    materials: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for node in outline_nodes:
        chunks.append(
            KnowledgeChunk(
                chunk_ref=node.temp_id,
                chunk_type="chapter",
                title=node.title,
                content_preview=node.title,
                parent_chunk_ref=node.parent_temp_id,
            )
        )
    for material in materials:
        content = str(material.get("content") or material.get("title") or "")
        chunks.append(
            KnowledgeChunk(
                chunk_ref=str(material["temp_id"]),
                chunk_type="material",
                title=str(material.get("title") or ""),
                content_preview=content[:8000],
                parent_chunk_ref=material.get("chapter_temp_id"),
            )
        )
    for candidate in candidates or []:
        chunks.append(
            KnowledgeChunk(
                chunk_ref=str(candidate["temp_id"]),
                chunk_type="candidate",
                title=str(candidate.get("title") or ""),
                content_preview=str(candidate.get("content_preview") or candidate.get("content") or "")[:8000],
                parent_chunk_ref=candidate.get("chapter_temp_id"),
            )
        )
    return chunks


def _apply_result_to_dict(item: dict[str, Any], result: ChunkClassificationResult) -> None:
    item["suggested_product_category_ids"] = [str(x) for x in result.suggested_product_category_ids]
    item["suggested_chapter_taxonomy_id"] = (
        str(result.suggested_chapter_taxonomy_id) if result.suggested_chapter_taxonomy_id else None
    )
    item["suggested_knowledge_type"] = result.suggested_knowledge_type
    item["classification_confidence"] = result.classification_confidence
    item["suggestion_source"] = result.suggestion_source
    item["classification_rationale"] = result.classification_rationale
    # 用户编辑初始值
    if item.get("chapter_taxonomy_id") is None and result.suggested_chapter_taxonomy_id:
        item["chapter_taxonomy_id"] = str(result.suggested_chapter_taxonomy_id)
    if not item.get("product_category_ids"):
        item["product_category_ids"] = [str(x) for x in result.suggested_product_category_ids]


def merge_classifications_into_suggestion(
    *,
    suggested_chapter_tree: list[dict[str, Any]],
    suggested_materials: list[dict[str, Any]],
    suggested_candidates: list[dict[str, Any]],
    chunks: list[KnowledgeChunk],
    results: dict[str, ChunkClassificationResult],
) -> dict[str, Any]:
    tree = [dict(x) for x in suggested_chapter_tree]
    materials = [dict(x) for x in suggested_materials]
    candidates = [dict(x) for x in suggested_candidates]
    index = {c.chunk_ref: c.chunk_type for c in chunks}
    for item in tree:
        r = results.get(str(item.get("temp_id")))
        if r:
            _apply_result_to_dict(item, r)
    for item in materials:
        r = results.get(str(item.get("temp_id")))
        if r:
            _apply_result_to_dict(item, r)
    for item in candidates:
        r = results.get(str(item.get("temp_id")))
        if r:
            _apply_result_to_dict(item, r)
    sources = {r.suggestion_source for r in results.values()}
    task_source = "hybrid" if len(sources) > 1 else (next(iter(sources)) if sources else "rule")
    return {
        "suggested_chapter_tree": tree,
        "suggested_materials": materials,
        "suggested_candidates": candidates,
        "suggestion_source": task_source,
    }
```

- [ ] **Step 4: 运行 PASS**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge_chunk.py backend/tests/unit/test_knowledge_chunk.py
git commit -m "feat(epic2): add KnowledgeChunk build and merge helpers"
```

---

## Task 3: 分类规则索引（Epic 0 DB）

**Files:**
- Create: `backend/src/services/classification_rule_index.py`
- Test: `backend/tests/unit/test_classification_rule_index.py`

- [ ] **Step 1: 写失败测试（使用 db_session + seeded_kb fixture）**

```python
# backend/tests/unit/test_classification_rule_index.py
from src.models.chapter_taxonomy import ChapterTaxonomy, CategoryStatus
from src.models.product_category import ProductCategory
from src.services.classification_rule_index import load_classification_index, match_product_category, match_chapter_taxonomy


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
```

- [ ] **Step 2: FAIL 后实现 classification_rule_index.py**

核心逻辑：
- `load_classification_index(db, kb_id)` 查询 active `ProductCategory`(+aliases) 与 `ChapterTaxonomy`(+synonyms)
- `match_product_category(text, index)` — 子串匹配 category_name / alias_normalized
- `match_chapter_taxonomy(text, index)` — 子串匹配 standard_name / synonym

返回 dataclass `MatchedCategory` / `MatchedTaxonomy` 含 id 与 confidence（名称完全包含 0.85，部分 0.7）。

- [ ] **Step 3: PASS + Commit**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_classification_rule_index.py -v
git add backend/src/services/classification_rule_index.py backend/tests/unit/test_classification_rule_index.py
git commit -m "feat(epic2): classification rule index from Epic 0 tables"
```

---

## Task 4: chunk_classification_service

**Files:**
- Create: `backend/src/services/chunk_classification_service.py`
- Test: `backend/tests/unit/test_chunk_classification_service.py`

- [ ] **Step 1: 写失败测试 — 无 LLM 时 rule 降级**

```python
# backend/tests/unit/test_chunk_classification_service.py
import os
from uuid import uuid4

import pytest

from src.services.chunk_classification_service import classify_chunk
from src.services.knowledge_chunk import KnowledgeChunk


def test_classify_chunk_without_llm_uses_rule(db_session, seeded_kb, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", None)

    chunk = KnowledgeChunk(chunk_ref="n1", chunk_type="chapter", title="售后服务方案", content_preview="...")
    result, degraded = classify_chunk(db_session, kb_id=seeded_kb.kb_id, chunk=chunk)
    assert result.suggestion_source == "rule"
    assert degraded is True
```

- [ ] **Step 2: 写失败测试 — mock LLM 返回 JSON**

```python
def test_classify_chunk_with_mock_llm(db_session, seeded_kb, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    def fake_chat(**kwargs):
        from src.services.llm_client import LLMResponse
        return LLMResponse(
            content='{"chapter_taxonomy_hint":"售后服务方案","knowledge_type":"scheme","confidence":0.9}',
            model="test",
            provider="qwen",
        )

    monkeypatch.setattr("src.services.chunk_classification_service.chat_completion", fake_chat)
    chunk = KnowledgeChunk(chunk_ref="n1", chunk_type="candidate", title="方案段", content_preview="详细方案...")
    result, degraded = classify_chunk(db_session, kb_id=seeded_kb.kb_id, chunk=chunk)
    assert result.suggestion_source in ("llm", "hybrid")
    assert degraded is False
```

- [ ] **Step 3: 实现 classify_chunk**

要点：
- 先 `load_classification_index` + rule match on `chunk.title + chunk.content_preview`
- `if not is_llm_available(): return rule_result, True`
- LLM prompt 要求返回 JSON（仅单块 title+preview，用 `truncate_for_llm`）
- parse JSON；失败 → `return rule_result, True`
- merge：LLM confidence > rule → `hybrid` or `llm`

- [ ] **Step 4: PASS + Commit**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_chunk_classification_service.py -v
git add backend/src/services/chunk_classification_service.py backend/tests/unit/test_chunk_classification_service.py
git commit -m "feat(epic2): chunk-level classification with LLM fallback to rules"
```

---

## Task 5: template_parse_runner Phase A/B 编排

**Files:**
- Modify: `backend/src/services/template_parse_runner.py`
- Modify: `backend/tests/integration/test_template_parse_runner.py`

- [ ] **Step 1: 写失败测试 — parse_ready 含 llm_progress 与块级字段**

在 `test_template_parse_runner.py` 追加：

```python
def test_template_parse_runner_populates_llm_progress_and_block_classification(
    db_session, seeded_kb, sample_docx_path, monkeypatch
):
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", None)

    import_id = _seed_confirmed_import_with_downstream(db_session, seeded_kb, sample_docx_path)
    run_template_parse_pending(db_session)

    task = db_session.query(TemplateParseTask).filter(TemplateParseTask.import_id == import_id).one()
    assert task.llm_progress is not None
    assert task.llm_progress["total_chunks"] >= 1
    assert task.llm_progress["completed_chunks"] == task.llm_progress["total_chunks"]

    suggestion = db_session.query(TemplateParseSuggestion).filter(
        TemplateParseSuggestion.parse_task_id == task.parse_task_id
    ).one()
    assert suggestion.suggested_product_category_ids == []  # 不再继承 file import
    first_chapter = suggestion.suggested_chapter_tree[0]
    assert "suggestion_source" in first_chapter
    assert "classification_confidence" in first_chapter
```

- [ ] **Step 2: FAIL 后修改 `_run_entry`**

在 `docx` 解析完成后：

```python
from src.services.knowledge_chunk import build_knowledge_chunks, merge_classifications_into_suggestion
from src.services.chunk_classification_service import classify_chunk

# ... existing outline + materials ...
suggested_tree = _to_suggested_tree(outline_nodes)
suggested_candidates = []  # 或从长 material 生成

chunks = build_knowledge_chunks(
    outline_nodes=outline_nodes,
    materials=materials,
    candidates=suggested_candidates,
)
llm_progress = {
    "total_chunks": len(chunks),
    "completed_chunks": 0,
    "failed_chunks": 0,
    "degraded_to_rule": 0,
    "batch_size": 1,
}
results = {}
for chunk in chunks:
    result, degraded = classify_chunk(db, kb_id=file_import.kb_id, chunk=chunk)
    results[chunk.chunk_ref] = result
    llm_progress["completed_chunks"] += 1
    if degraded:
        llm_progress["degraded_to_rule"] += 1
    task.llm_progress = dict(llm_progress)
    db.flush()

merged = merge_classifications_into_suggestion(
    suggested_chapter_tree=suggested_tree,
    suggested_materials=materials,
    suggested_candidates=suggested_candidates,
    chunks=chunks,
    results=results,
)
suggestion.suggested_chapter_tree = merged["suggested_chapter_tree"]
suggestion.suggested_materials = merged["suggested_materials"]
suggestion.suggested_candidates = merged["suggested_candidates"]
suggestion.suggestion_source = merged["suggestion_source"]
suggestion.suggested_product_category_ids = []  # 文件级细分类清空
suggestion.rationale = "docx structure parse + chunk classification"
task.llm_progress = llm_progress
_append_log(task, f"块级分类 {llm_progress['completed_chunks']}/{llm_progress['total_chunks']} 完成")
```

**删除**原行：`suggestion.suggested_product_category_ids = file_import.product_category_ids or []`

- [ ] **Step 3: PASS 全量 template 测试**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_template_parse_runner.py tests/unit/test_knowledge_chunk.py tests/unit/test_chunk_classification_service.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/services/template_parse_runner.py backend/tests/integration/test_template_parse_runner.py
git commit -m "feat(epic2): wire chunk classification pipeline in parse runner"
```

---

## Task 6: API 序列化 llm_progress

**Files:**
- Modify: `backend/src/api/routes/template_parse.py`
- Modify: `backend/tests/contract/test_template_parse_trigger.py`（或 task detail 契约测试）

- [ ] **Step 1: 在 `_serialize_task` / list items 增加 `llm_progress`**

```python
"llm_progress": task.llm_progress,
```

- [ ] **Step 2: 契约测试断言字段存在**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(epic2): expose llm_progress on template parse task API"
```

---

## Task 7: confirm_service 块级 stub 持久化

**Files:**
- Modify: `backend/src/services/template_confirm_service.py`
- Create: `backend/tests/integration/test_template_chunk_classification_flow.py`

- [ ] **Step 1: 写失败测试 — stub 不继承 template.product_category_ids**

```python
def test_confirm_uses_block_level_candidate_categories(db_session, seeded_kb, sample_docx_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", None)
    # seed parse → confirm with candidate_actions accepted
    # assert stub.product_category_ids 来自 payload/suggestion 块值，非 template 级
```

- [ ] **Step 2: 修改 confirm 循环**

将：

```python
product_category_ids = _as_uuid_list(
    candidate_payload.get("product_category_ids")
    or (chapter_row.product_category_ids if chapter_row else template.product_category_ids),
    ...
)
```

改为：

```python
product_category_ids = _as_uuid_list(
    action.get("product_category_ids")
    or candidate_payload.get("product_category_ids")
    or (chapter_row.product_category_ids if chapter_row else []),
    field_name="candidate.product_category_ids",
)
chapter_taxonomy_id = _as_uuid(
    action.get("chapter_taxonomy_id") or candidate_payload.get("chapter_taxonomy_id"),
    field_name="chapter_taxonomy_id",
)
# CandidateKnowledgeStub(..., chapter_taxonomy_id=chapter_taxonomy_id,
#   suggested_knowledge_type=..., suggestion_source=..., classification_confidence=..., chunk_ref=temp_id)
```

扩展 `ConfirmCandidateActionRequest` 可选字段：`product_category_ids`, `chapter_taxonomy_id`, `knowledge_type`。

- [ ] **Step 3: PASS + Commit**

---

## Task 8: 前端类型扩展

**Files:**
- Modify: `frontend/src/services/templates.ts`

- [ ] **Step 1: 增加接口字段**

```typescript
export interface LLMProgress {
  total_chunks: number;
  completed_chunks: number;
  failed_chunks: number;
  degraded_to_rule: number;
  batch_size?: number;
}

export interface BlockClassificationFields {
  suggested_product_category_ids?: string[];
  suggested_chapter_taxonomy_id?: string | null;
  suggested_knowledge_type?: string | null;
  classification_confidence?: number;
  suggestion_source?: "rule" | "llm" | "hybrid";
  classification_rationale?: string | null;
}
```

扩展 `ParseSuggestionChapterNode`, `ParseSuggestionMaterial`, `ParseSuggestionCandidate` 继承 `BlockClassificationFields`；`ParseTaskDetail` + `TemplateParseTaskListItem` 增加 `llm_progress?: LLMProgress | null`。

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/templates.ts
git commit -m "feat(epic2): extend frontend types for block classification"
```

---

## Task 9: ParseConfirmWizard 块级分类 UI

**Files:**
- Modify: `frontend/src/pages/TemplateLibraryCenter/ParseConfirmWizard.tsx`
- Optional: `frontend/src/services/chapterTaxonomyApi.ts`（若尚无 list API）

- [ ] **Step 1: Step1 — 产品分类改为可选 + 去掉 import 预填**

删除/修改 `loadData` 中：

```typescript
product_category_ids: suggestion.suggested_product_category_ids ?? [],
```

改为 `product_category_ids: []`，label 改为「快捷产品分类（可选，可批量应用到章节）」。

- [ ] **Step 2: Step2 — 章节表新增列**

- `chapter_taxonomy_id` — Select，options 来自 `getChapterTaxonomyTree(selectedKbId)`
- `product_category_ids` — Select mode=multiple
- `suggestion_source` — Tag 只读

Toolbar 按钮：

```typescript
const applyQuickCategoriesToChapters = () => {
  const quick = form.getFieldValue("product_category_ids") ?? [];
  setChapters((prev) => prev.map((c) => ({ ...c, product_category_ids: [...quick] })));
};
```

- [ ] **Step 3: loadData 映射 suggested_* → 编辑字段**

```typescript
setChapters((suggestion.suggested_chapter_tree ?? []).map((chapter) => ({
  ...chapter,
  chapter_taxonomy_id: chapter.chapter_taxonomy_id ?? chapter.suggested_chapter_taxonomy_id ?? null,
  product_category_ids: chapter.product_category_ids?.length
    ? chapter.product_category_ids
    : (chapter.suggested_product_category_ids ?? []),
})));
```

- [ ] **Step 4: Step3 — material/candidate 分类列**（产品分类 Select + suggestion_source Tag；candidate 加 knowledge_type Select）

- [ ] **Step 5: 本地 smoke — 打开向导可见新列**

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/TemplateLibraryCenter/ParseConfirmWizard.tsx
git commit -m "feat(epic2): block-level classification in parse confirm wizard"
```

---

## Task 10: 待办区 llm_progress 展示

**Files:**
- Modify: `frontend/src/pages/TemplateLibraryCenter/index.tsx`

- [ ] **Step 1: todoColumns status render 扩展**

```typescript
render: (value: string, record: TemplateParseTaskListItem) => {
  if (value === "running" && record.llm_progress) {
    const p = record.llm_progress;
    return <Tag color="processing">块级分类 {p.completed_chunks}/{p.total_chunks}</Tag>;
  }
  // ... existing tags
}
```

- [ ] **Step 2: listParseTasks 响应已含 llm_progress（Task 6 后端）**

- [ ] **Step 3: Commit**

---

## Task 11: 全量回归

- [ ] **Step 1: 后端全量**

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "template or chunk or classification"
```

Expected: 全部 PASS

- [ ] **Step 2: 前端 build**

```bash
cd frontend && npm run build
```

Expected: 无 TS 错误

- [ ] **Step 3: quickstart 场景 7/8 手工验证**

参考 `specs/003-template-parse-publish/quickstart.md` 场景 7（无 Key 降级）、场景 8（llm_progress）。

---

## Spec Coverage Self-Review

| 需求 | 任务 |
|------|------|
| FR-004a 块级分类 | Task 2, 4, 5, 9 |
| FR-021 LLM 环境变量 | Task 4（复用 llm_client） |
| FR-022 禁止整文件 LLM | Task 5（逐块 loop + truncate） |
| FR-023 降级不阻断 | Task 4, 5, 11 场景 7 |
| SC-008 大文件分批 | Task 5 llm_progress |
| 确认 UI 块粒度 | Task 9 |
| stub 块级持久化 | Task 7 |

**Placeholder scan:** 无 TBD/TODO。

**Type consistency:** `ChunkClassificationResult.suggestion_source` 与 API/前端 `"rule"|"llm"|"hybrid"` 一致。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-12-epic2-clarification-delta.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间 review，迭代快  
2. **Inline Execution** — 本会话用 executing-plans 按 Task 批量执行，检查点暂停 review  

你想用哪种方式？
