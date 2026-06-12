# Design Delta: Epic 2 澄清增量修订

**Date**: 2026-06-12  
**Status**: Implemented (2026-06-12)  
**Base design**: `docs/superpowers/specs/2026-06-12-epic2-template-parse-publish-design.md` (D1–D12 approved)  
**Spec Kit**: `specs/003-template-parse-publish/` (spec clarifications + plan R13–R15)

## 0. 修订范围

在已批准 Epic 2 设计（双入口、全屏向导 P0–P4）上 **增量对齐** 三项澄清：

| # | 澄清 | 设计影响 |
|---|------|----------|
| C1 | 分类落在知识块，非文件 | 移除文件级细分类默认值；块级字段 + 向导 Step2/3 |
| C2 | LLM 环境变量可切换 | 复用 `llm_client` + `config.py` 预设；集中降级 |
| C3 | 大文件禁止整文件 LLM | Phase A/B 流水线 + `llm_progress` |

**不变**：D1–D5 UX（双入口、向导三步、待办优先、拖拽树）、D7 diff、D10 BackgroundTasks。

** supersede**：原 D6「snippet = heading_titles + first paragraphs」→ 见本文 §2 `chunk_classification_service`。

---

## 1. 解析流水线与模块边界

### 1.1 两阶段流水线

```text
Phase A — 结构解析（无 LLM）
  docx_outline_parser        → OutlineNode[]
  docx_content_extractor     → MaterialDraft[]
  build_knowledge_chunks()   → KnowledgeChunk[]

Phase B — 块级分类（可选 LLM，逐块）
  FOR chunk IN chunks:
    chunk_classification_service.classify(chunk, kb_id)
    UPDATE template_parse_task.llm_progress
  merge_classifications() → suggestion JSON
  status = parse_ready
```

**硬约束**：禁止将整份 docx 拼成单个 LLM prompt（FR-022）。

### 1.2 KnowledgeChunk

```python
@dataclass
class KnowledgeChunk:
    chunk_ref: str
    chunk_type: Literal["chapter", "material", "candidate"]
    title: str
    content_preview: str
    parent_chunk_ref: str | None
    suggested_product_category_ids: list[UUID]
    suggested_chapter_taxonomy_id: UUID | None
    suggested_knowledge_type: str | None
    classification_confidence: float
    suggestion_source: Literal["rule", "llm", "hybrid"]
    classification_rationale: str | None
```

| chunk_type | 来源 | 分类维度 |
|------------|------|----------|
| chapter | OutlineNode | product_category, chapter_taxonomy |
| material | MaterialDraft | product_category |
| candidate | 可提取长段落 | product_category, chapter_taxonomy, knowledge_type |

### 1.3 模块职责

| 模块 | 职责 | 切片 |
|------|------|------|
| `services/knowledge_chunk.py` | dataclass + `build_knowledge_chunks()` | P1.1 |
| `services/chunk_classification_service.py` | 规则 → 可选 LLM → 降级 | P1.1 |
| `services/llm_client.py` | OpenAI 兼容客户端（已有） | — |
| `template_parse_runner._run_entry` | Phase A/B 编排 | P1.1 改 |
| `models/template_parse_task` | +`llm_progress` JSON | P1.1 |

### 1.4 移除行为

- `_run_entry` 中 **`suggestion.suggested_product_category_ids = file_import.product_category_ids`** 删除。
- 文件级 `product_category_ids` 不得作为块分类默认值。

### 1.5 chunk_classification_service

```text
classify(chunk, kb_id):
  1. rule_result ← title/别名匹配 (Epic 0 Product Category + Chapter Taxonomy)
  2. IF NOT settings.llm_enabled: RETURN rule_result
  3. llm_result ← chat_completion(truncate(title + content_preview))
  4. IF llm_result IS NULL: increment degraded_to_rule; RETURN rule_result
  5. MERGE by confidence → suggestion_source hybrid|llm
```

单块失败不 fail 整个 parse task（FR-023）。

### 1.6 llm_progress

```json
{
  "total_chunks": 12,
  "completed_chunks": 12,
  "failed_chunks": 0,
  "degraded_to_rule": 2,
  "batch_size": 1
}
```

### 1.7 交付切片调整

```text
P1   结构解析（已有）
P1.1 知识块管道 + 块级分类 + llm_progress + API 字段
P2   向导 Step2/3 块级分类 UI（依赖 P1.1）
P3/P4 无架构变更
```

MVP 采用 **同步 Phase B**（同一 `_run_entry` 内完成）；若大文件等待过长再评估 `classifying` 中间状态。

---

## 2. 确认向导 UX 变更（D2 增量）

### 2.1 Step1「模板归类」— 降级文件级分类

| 项 | 原行为 | 修订后 |
|----|--------|--------|
| 产品分类表单项 | 必填感、预填 import 分类 | **可选**「批量快捷填充」 |
| 预填来源 | `file_import.product_category_ids` | **空**；不读 import 细分类 |
| confirm payload `product_category_ids` | 模板级默认 | 保留为 **Template 级可选标签**；块级以 chapters/materials/candidates 为准 |

Step1 职责收窄：**库归类 + 模板名称/类型**，不再承担细粒度分类。

### 2.2 Step2「章节树」— 块级分类列

章节表新增列：

| 列 | 控件 | 数据字段 |
|----|------|----------|
| 章节类型 | Select（Chapter Taxonomy 树） | `chapter_taxonomy_id` |
| 产品分类 | Select multiple | `product_category_ids` |
| 建议来源 | Tag（只读） | `suggestion_source` |
| 置信度 | Tag/Progress（只读，可选） | `classification_confidence` |

**批量填充**：Toolbar 按钮「将 Step1 快捷分类应用到全部章节」— 显式用户操作，非自动继承。

加载 suggestion 时映射：

- `suggested_chapter_taxonomy_id` → `chapter_taxonomy_id`
- `suggested_product_category_ids` → `product_category_ids`

### 2.3 Step3「素材与候选」— 块级分类

**素材表**新增：

- 产品分类（Select multiple）
- 建议来源 Tag（只读）

**候选表**新增：

- 知识类型（Select：scheme/product/qualification/…）
- 章节类型、产品分类
- 建议来源 Tag

confirm payload 扩展：materials/candidates 携带块级分类字段；后端 `template_confirm_service` 写入 chapter/material/stub + `classification_reference`。

### 2.4 待办区与解析中状态

- 解析中任务：可选展示 `llm_progress` 文案「块级分类 8/12」。
- `parse_ready` 后 suggestion 已含完整块级分类（同步 Phase B 模式）。

### 2.5 TypeScript 类型扩展（`templates.ts`）

`ParseSuggestionChapterNode` / `Material` / `Candidate` 增加：

```typescript
suggested_product_category_ids?: string[];
suggested_chapter_taxonomy_id?: string | null;
suggested_knowledge_type?: string | null;
classification_confidence?: number;
suggestion_source?: "rule" | "llm" | "hybrid";
classification_rationale?: string | null;
chapter_taxonomy_id?: string | null;  // 用户编辑值
```

`ParseTask` 增加 `llm_progress?: LLMProgress`。

---

## 3. 测试、迁移与 API

### 3.1 数据库迁移（P1.1）

| 表 | 变更 |
|----|------|
| `template_parse_tasks` | ADD `llm_progress` JSONB nullable |
| `candidate_knowledge_stubs` | ADD `suggestion_source`, `classification_confidence`, `chunk_ref`, `suggested_knowledge_type` |

suggestion JSON  schema 扩展无需列迁移（JSONB 内嵌字段）。

### 3.2 后端测试

| 用例 | 断言 |
|------|------|
| 无 `LLM_API_KEY` | 全 rule；`parse_ready`；`degraded_to_rule == total_chunks` 或等效 |
| `LLM_API_KEY=force_fail` | 块级降级；task 不 failed |
| mock LLM 返回 taxonomy | 对应 chunk `suggestion_source=llm` |
| sample-template.docx | 每 chapter 有独立 classification 字段 |
| 大 fixture / mock 500 chunks | 无整文件 prompt；`llm_progress.completed == total` |
| 确认后 | stub/chapter 持久化块级分类；非 file_import 继承 |

新增：

- `tests/unit/test_knowledge_chunk.py`
- `tests/unit/test_chunk_classification_service.py`
- 扩展 `tests/integration/test_template_parse_flow.py`

### 3.3 前端测试（可选 P2）

- Step2 渲染 taxonomy/product 列
- Step1 批量填充按钮更新全部章节

### 3.4 API 契约

沿用 `contracts/template-parse-api.md` 澄清修订版：

- GET task/suggestion 含 `llm_progress`、块级分类字段
- confirm body materials/candidates 含块级分类

### 3.5 confirm_service 变更

- 写 `TemplateChapter.chapter_taxonomy_id` / `product_category_ids` 来自 **payload 块值**
- 写 `CandidateKnowledgeStub` 含 `knowledge_type`, `suggestion_source`, `chunk_ref`
- `classification_reference` 按块 object_type 写入

---

## 4. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 块数过多 LLM 慢 | 同步 Phase B + progress 日志；后续可限流或 async |
| 向导 Step2 列过多 | 章节类型/产品分类可折叠到「展开分类」抽屉 |
| 与旧 suggestion 兼容 | API 对缺失块级字段默认 null + source=rule |
| Epic 0 taxonomy 未加载 | 分类 service 缓存 KB 分类树；规则降级 |

---

## 5. 与 Spec Kit 同步

| 制品 | 动作 |
|------|------|
| `plan.md` Clarification Delta | 已对齐 |
| `research.md` R13–R15 | 已对齐 |
| `data-model.md` | 已对齐 |
| `tasks.md` | `/speckit-tasks` 生成 P1.1 任务 |
| 原 design D6 | 由本文 §1.5 取代 |

---

## 6. 审批记录

| 阶段 | 状态 | 日期 |
|------|------|------|
| §1 流水线与模块 | 用户确认（「继续」） | 2026-06-12 |
| §2 向导 UX | 待确认 | — |
| §3 测试与迁移 | 待确认 | — |
| 书面审阅 | 待用户批准 | — |
