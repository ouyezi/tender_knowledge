# Design: 四核心模块精简（退役旧知识管理）

**Date**: 2026-06-20  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md`

---

## 1. 目标

将 tender_knowledge 代码库精简为四个核心模块，删除旧知识管理（KU/候选/正式知识/检索/模板/目录等）的全部应用代码、测试与数据库表，并将来源导入改为 V2-only 解析路径，清空历史测试数据以便重新验收。

### 1.1 保留的四个核心模块

| 模块 | 前端路由 | 后端 API |
|------|---------|----------|
| 知识库管理 | `/` | `/api/v1/knowledge-bases` |
| 来源导入 | `/file-imports` | `/api/v1/kbs/{kb_id}/file-imports` |
| 知识录入 V2 | `/knowledge-v2/entry` | `/api/v1/kbs/{kb_id}/knowledge-chunks/*` |
| 知识浏览 V2 | `/knowledge-v2/browse` | 同上 |

### 1.2 已锁定决策

| 议题 | 决议 |
|------|------|
| 范围 | **严格四模块**：除上述四项外，所有 UI/API/服务/测试删除 |
| 数据库 | **代码 + Schema 同步清理**：Alembic migration 删除废弃表与列 |
| 实施策略 | **分层删除**（前端 → API/服务 → 模型/migration → 测试/数据） |
| 解析路径 | 来源导入统一走 `import_workspace_for_knowledge_entry()`，不写 bid outline / candidate |
| `actual_bid_parse_tasks` 表名 | 暂保留，避免额外 rename churn |

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 分层删除（采用）** | 分阶段删除，每步可验证 | CI 逐步恢复，风险低 | 短期存在 dead code |
| ② 大爆炸单次 PR | 一次性删除全部 | 最快 | diff 巨大，review 困难 |
| ③ 新建 slim 包 | 新 backend 包只含四模块 | 边界极清晰 | 对本项目过度 |

---

## 3. 架构（精简后）

```text
┌─────────────────────────────────────────────────────────┐
│  Frontend                                                │
│  知识库 │ 来源导入 │ 知识录入 V2 │ 知识浏览 V2            │
└────────┬──────────┬─────────────┬───────────────────────┘
         │          │             │
         ▼          ▼             ▼
┌─────────────────────────────────────────────────────────┐
│  API                                                     │
│  knowledge-bases │ file-imports │ knowledge-chunks │ media│
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Services                                                │
│  knowledge_v2/* │ doc_chunk/* (V2-only) │ document_parse_runner │
│  file_import_service │ file_import_purge_service         │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Database (retained tables)                              │
│  knowledge_bases, file_imports, documents,               │
│  document_tree_nodes, document_media_assets,             │
│  actual_bid_parse_tasks, knowledge_chunks,               │
│  chunk_assets, chunk_embeddings + import audit tables    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 保留清单

### 4.1 前端

- `pages/KnowledgeBaseList/`
- `pages/FileImportCenter/`（精简 ConfirmDrawer、列表页）
- `pages/KnowledgeV2/` + `components/KnowledgeV2/`
- `layout/AppShell.tsx`、`layout/KBContext.tsx`
- Services: `knowledgeChunks.ts`, `fileImports.ts`, `knowledgeBases` 相关

### 4.2 后端 API 路由

- `knowledge_bases`
- `file_imports`（精简）
- `knowledge_chunks`
- `media`

### 4.3 后端服务

- `services/knowledge_v2/*`
- `services/doc_chunk/*`（删除 bid_outline/candidates mapper 调用链）
- `services/file_import_service.py`
- `services/file_import_purge_service.py`（重写）
- `services/document_parse_runner.py`（新建，合并 doc_chunk 解析路径）
- `services/confirm_service.py`（精简，去掉旧下游路由）

### 4.4 数据表（保留）

```
knowledge_bases
kb_clone_logs
file_imports
import_tasks
import_audit_logs
file_purpose_suggestions
downstream_task_entries
documents
document_tree_nodes
document_media_assets
document_parse_suggestions
actual_bid_parse_tasks
knowledge_chunks
chunk_assets
chunk_embeddings
```

### 4.5 保留表上的列清理

| 表 | 删除列 |
|----|--------|
| `file_imports` | `product_category_ids`, `chapter_taxonomy_id`, `target_object_type` |
| `documents` | `product_category_ids` |
| `document_tree_nodes` | `chapter_taxonomy_id`, `product_category_ids` |
| `file_purpose_suggestions` | `suggested_product_category_ids`, `suggested_chapter_taxonomy_id` |

### 4.6 FilePurpose 枚举

只保留：

- `actual_bid`
- `template_file`

删除：`qualification`, `ppt_material`, `cover_guide`, `writing_guide`, `wiki_source`, `other`

---

## 5. 删除清单

### 5.1 前端页面（整目录删除）

- `CandidateCenter/`
- `KnowledgeCenter/`
- `OutlineCenter/`
- `TemplateLibraryCenter/`
- `ProductCategoryCenter/`
- `ChapterTaxonomyCenter/`
- `RetrievalOptimizationCenter/`

### 5.2 前端路由（从 App.tsx 移除）

`/product-categories`, `/chapter-taxonomies`, `/template-libraries`, `/outlines`, `/retrieval-optimization`, `/candidates`, `/knowledge`, `/candidates/audit`, `/candidates/confirm/:id`, 及所有 template/outline 子路由

### 5.3 后端 API 路由（删除）

`knowledge_units`, `candidates`, `candidate_batch`, `candidate_audit_logs`, `wikis`, `manual_assets`, `templates`, `template_libraries`, `template_parse`, `template_chapters`, `template_assets`, `bid_outlines`, `actual_bid_parse`（独立路由，逻辑并入 document_parse_runner）, `retrieval`, `retrieval_eval`, `retrieval_feedback`, `generation`, `module_suggestions`, `tender_requirements`, `chapter_patterns`, `product_categories`, `chapter_taxonomies`

### 5.4 后端服务/模型（删除）

**候选/KU 链**：`candidate_*_service`, `ku_publisher`, `publishers/*`, models: `knowledge_unit`, `candidate_knowledge*`, `candidate_confirm_audit_log`, `wiki`, `manual_asset`

**模板/目录**：`template_*`, `bid_outline_*`, `actual_bid_parse_runner`（legacy 部分）, models: `template*`, `bid_outline*`, `actual_bid_audit_log`

**检索/生成**：`services/retrieval/*`, `services/generation/*`, `module_suggestion*`, models: `retrieval_*`, `generation_*`, `chapter_draft`, `module_assembly_suggestion`, `tender_requirement_context`, `chapter_pattern*`

**分类管理**：`product_category*`, `chapter_taxonomy*`, `classification_*`, `document_tree_classification_service`

**doc_chunk mappers（删除或停用）**：`mappers/bid_outline.py`, `mappers/candidates.py`；`import_service.import_workspace()` 全量路径

### 5.5 Alembic migration 删表

分组删除约 40 张表：

- 旧知识：`knowledge_units`, `candidate_knowledges`, `candidate_knowledge_stubs`, `candidate_confirm_audit_logs`, `wikis`, `manual_assets`
- 结构（旧）：`bid_outlines`, `bid_outline_nodes`, `bid_outline_structure_diffs`, `actual_bid_audit_logs`
- 模板：`template_libraries`, `templates`, `template_chapters`, `template_materials`, `template_variables`, `template_rules`, `template_parse_tasks`, `template_parse_suggestions`, `template_structure_diffs`, `template_publish_snapshots`, `template_audit_logs`
- 检索：`retrieval_index_entries`, `retrieval_traces`, `retrieval_feedbacks`, `retrieval_eval_sets`, `retrieval_eval_cases`, `retrieval_eval_runs`, `retrieval_strategy_versions`
- 生成：`generation_tasks`, `generation_snapshots`, `chapter_drafts`, `module_assembly_suggestions`, `tender_requirement_contexts`
- 分类：`product_categories`, `chapter_taxonomies`, `classification_audit_logs`, `classification_references`
- 模式：`chapter_patterns`, `chapter_pattern_mining_tasks`

Migration 同时执行 §4.5 列删除与 `FilePurpose` 枚举收窄。

---

## 6. 来源导入重构（V2-only）

### 6.1 目标流程

```text
上传 → 确认用途(actual_bid | template_file)
     → doc_chunk 解析 (document_parse_runner)
     → import_workspace_for_knowledge_entry()
         (document + tree + content.md + chunk_assets)
     → parse_status = ready
     → 用户点击「前往知识录入」→ /knowledge-v2/entry?docId=...
```

### 6.2 具体改动

1. **新建 `document_parse_runner.py`**  
   合并 `actual_bid_parse_runner` doc_chunk 路径与 `template_parse_runner` 的 knowledge entry 部分；删除 legacy walk_document、bid outline persist、candidate import、template 解析。

2. **精简 `import_service.py`**  
   只暴露 `import_workspace_for_knowledge_entry()`；删除 `import_workspace()` 及 `persist_outline` / `persist_candidates` 分支；移除 `classify_heading_nodes_for_document` 调用。

3. **精简 `ConfirmDrawer`**  
   去掉产品分类、章节类型字段；只选文件用途（actual_bid / template_file）。

4. **精简 `FileImportCenter`**  
   - 删除跳转到 `/outlines/parse-confirm/` 和 `/template-libraries` 的链接  
   - 解析完成后显示「前往知识录入」链接  
   - 删除 `retryTemplateParse` 等旧 retry 入口（统一为 document parse retry）

5. **重写 `file_import_purge_service`**  
   Purge 链：`file_import → documents → tree_nodes → media → knowledge_chunks → storage`；不再引用 KU/template/bid outline/retrieval index。

6. **精简 `confirm_service`**  
   确认后只创建 document parse 下游任务，不路由到 template/bid outline 流程。

---

## 7. 测试策略

### 7.1 删除

所有 candidate/KU/template/outline/retrieval/generation/classification 相关测试（contract + integration + unit，约 80+ 文件），包括但不限于：

- `test_candidate_*`, `test_knowledge_unit*`, `test_epic4_*`, `test_epic5_*`, `test_epic6_*`
- `test_template_*`, `test_bid_outline_*`, `test_retrieval_*`, `test_generation_*`
- `test_module_suggestion_*`, `test_product_category_*`, `test_chapter_taxonomy_*`

### 7.2 保留并更新

- `test_knowledge_bases_api.py`
- `test_knowledge_v2_*`（全部）
- `test_file_import_*`（upload/delete/purge，按新 purge 逻辑改）
- `test_doc_chunk_*`（import/tree/section_slice 相关，删除 bid_outline/candidates 用例）
- `test_reset_business_data.py`（更新 `BUSINESS_TABLES`）
- `test_media_api.py`

### 7.3 验收门槛

- 精简后 `pytest` 全绿
- 前端 `vitest` 全绿
- 手动通路：上传 → 确认 → 解析 → 知识录入 V2 → 入库 → 知识浏览 V2 可见

---

## 8. 测试数据清理

1. 更新 `scripts/lib/e2e/reset_business_data.py` 的 `BUSINESS_TABLES` 为 §4.4 保留表清单（加 import 相关表）
2. 本地 dev 执行 reset（TRUNCATE + 清 `STORAGE_ROOT`）
3. Migration 升级后再次 reset，确保 schema 与代码一致
4. 删除或归档旧 E2E 脚本（`run_zhongtie_acceptance.py`、Epic4–6 workbench steps 等）

---

## 9. 实施顺序

| 阶段 | 内容 | 验证 |
|------|------|------|
| P0 | 跑 reset + 记录当前基线 | — |
| P1 | 来源导入 V2-only 重构（runner + ConfirmDrawer + 列表页） | 上传→解析→录入 V2 手动通路 |
| P2 | 删前端旧页面 + 路由/导航 | 前端 build 通过 |
| P3 | 删后端 routes/services | 无 dead import |
| P4 | 删 models + Alembic migration | `alembic upgrade head` 成功 |
| P5 | 删测试 + 更新 reset 脚本 | pytest + vitest 全绿 |
| P6 | 清本地测试数据 | 空库可重新导入测试 |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 漏删引用导致 import 错误 | 分层删除 + 每阶段编译/测试 |
| migration 删表顺序 FK 冲突 | migration 按依赖逆序 DROP；先删子表 |
| purge 逻辑遗漏导致 DELETE 500 | 重写 purge 前先写/更新 contract test |
| FilePurpose 枚举收窄影响存量数据 | reset 清数据后再 migration；无存量兼容负担 |

---

## 11. 不在范围

- 旧 specs/docs 目录归档（可后续单独 PR）
- `retrieval_index_entries` 重建或新检索 API
- KU/候选数据迁移到 knowledge_chunks
- `actual_bid_parse_tasks` 表 rename
