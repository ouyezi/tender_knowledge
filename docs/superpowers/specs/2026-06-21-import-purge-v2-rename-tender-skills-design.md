# Design: 来源导入硬删除 + V2 全量重命名 + tender_skills 表格侧车

**Date**: 2026-06-21  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-20-core-four-modules-cleanup-design.md`

---

## 1. 背景与目标

四核心模块精简后，仍存在三类收尾问题：

1. **来源导入删除不完整**：`file_import_purge_service` 未清理 `knowledge_chunks` / `chunk_assets` / `chunk_embeddings`、`actual_bid_parse_tasks`、document 级存储与 doc_chunk 工作区；无法「删干净再测新文件」。
2. **V2 命名过时**：旧知识管理已移除，V2 是唯一路径，用户可见与代码目录仍带 V2 后缀。
3. **tender_skills 已更新**：表格侧车 `tables/`、docx 内联图片去重等；本项目 `asset_seed_service` 未消费侧车，表格资产字段不完整。

### 1.1 已锁定决策

| 议题 | 决议 |
|------|------|
| 删除语义 | **硬删除**：物理 `DELETE file_imports` 行，便于同 hash 重新上传 |
| V2 去品牌化 | **全量重命名**：路由、文案、前后端目录、测试文件名 |
| tender_skills | **升级 + 适配表格侧车** |
| 旧 `/knowledge-v2/*` 路由 | **不保留 redirect**，直接切换 |
| 实施顺序 | **分层 3 PR**：purge → sidecar → rename |

---

## 2. 方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 分层 3 PR（采用）** | purge → sidecar → rename | 每步可测、rename 不干扰 purge | 3 轮 review |
| ② 后端合一 | purge + sidecar 一 PR，rename 一 PR | 2 PR | 首 PR 仍偏大 |
| ③ 单次 PR | 全部一起 | 最快 | diff 巨大 |

---

## 3. 来源导入硬删除

### 3.1 目标

删除一条来源导入后，清除：

- 上传文件与解析工作区存储
- 文档树、媒体、解析任务等中间态
- 知识录入产生的 chunks、assets、embeddings
- `file_imports` 行本身

删除后可立即重新上传同名或同 hash 文件（依赖 `uq_file_imports_kb_hash` 在硬删后释放）。

### 3.2 删除顺序（FK 安全）

```text
1. 收集本 import（及递归子 import）下所有 document_id
2. chunk_embeddings      ← object_id IN (chunk ids for those doc_ids)
3. chunk_assets          ← doc_id IN (...)
4. knowledge_chunks      ← doc_id IN (...)（含版本链，按 doc 整批删除）
5. document_parse_suggestions
6. actual_bid_parse_tasks
7. document_tree_nodes
8. document_media_assets
9. documents
10. import_tasks / downstream_task_entries / file_purpose_suggestions
11. 递归处理 parent_import_id 指向本 import 的子 import（先子后父）
12. 存储目录：
    - {storage_root}/{kb_id}/{import_id}/
    - {storage_root}/doc_chunk_workspaces/{kb_id}/{import_id}/
    - {storage_root}/documents/{doc_id}/（每个 document）
13. DELETE FROM file_imports WHERE import_id = ...
```

`import_audit_logs.import_id` 使用 `ondelete=SET NULL`，审计保留、不阻塞删除。

### 3.3 API / 服务变更

| 项 | 变更 |
|----|------|
| `DELETE .../file-imports/{id}` | 移除 `deprecate_published` 参数 |
| `check_purge_impact` | 返回 `knowledge_chunks`、`chunk_assets`、`chunk_embeddings`、`documents`、`import_tasks` 等计数；移除 `has_published_assets` |
| `FileImportStatus.deleted` | enum 保留兼容历史 DB；新逻辑不再写墓碑 |
| `list_file_imports` | 可移除 `status != deleted` 过滤（行已不存在） |
| 错误处理 | 保留 `IntegrityError` → 409，便于发现遗漏 FK |

### 3.4 前端 UX

- 单次 `Modal.confirm`：「将删除导入文件、解析数据及已录入知识，不可恢复。」
- 移除 `deprecate_published` 分支与已发布资产 `ImpactAnalysisModal` 废弃流程
- `getFileImportPurgeImpact` 仍可用于展示影响计数（可选展示在 confirm content）

### 3.5 测试

- `backend/tests/unit/test_file_import_purge_service.py`：删除顺序、存储清理、子 import 递归、硬删后可 re-upload
- `backend/tests/contract/test_file_import_delete.py`：DELETE 200 + 响应 `deleted_counts`
- 集成场景：上传 → 解析 → 录入 chunk → DELETE → 知识浏览列表为空

---

## 4. V2 全量重命名

### 4.1 路由与文案

| 旧 | 新 |
|----|-----|
| `/knowledge-v2/entry` | `/knowledge/entry` |
| `/knowledge-v2/browse` | `/knowledge/browse` |
| 「知识录入 V2」 | 「知识录入」 |
| 「知识浏览 V2」 | 「知识浏览」 |

**不保留** `/knowledge-v2/*` redirect。

### 4.2 目录与包名

| 旧 | 新 |
|----|-----|
| `frontend/src/pages/KnowledgeV2/` | `frontend/src/pages/Knowledge/` |
| `frontend/src/components/KnowledgeV2/` | `frontend/src/components/Knowledge/` |
| `backend/src/services/knowledge_v2/` | `backend/src/services/knowledge/` |
| `backend/tests/unit/test_knowledge_v2_*` | `test_knowledge_*` |
| `backend/tests/integration/test_knowledge_v2_*` | `test_knowledge_*` |

### 4.3 不变项

- REST API：`/api/v1/kbs/{kb_id}/knowledge-chunks/*`（无 v2 后缀）
- DB 表名：`knowledge_chunks`、`chunk_assets`、`chunk_embeddings`
- `FileImportCenter` 解析完成链接改为 `/knowledge/entry?docId=...`

### 4.4 杂项

- `localStorage`：`knowledge-v2-filters:{kbId}` → `knowledge-filters:{kbId}`
- 全库 grep `knowledge_v2|KnowledgeV2|knowledge-v2` 清零（文档历史 spec 可保留）

---

## 5. tender_skills 升级 + 表格侧car

### 5.1 依赖对齐

- `backend/pyproject.toml`：`doc-chunk @ file:../../tender_skills` 对齐最新 HEAD（含 table sidecar、inline image dedup）
- 本地/CI：`pip install -e` 重装；跑 `pytest tests/` 全量回归
- 若 workspace schema 变化，更新 `tests/fixtures/doc_chunk_workspace_minimal/`

### 5.2 asset_seed_service 适配

处理 chunk / workspace 中 `type == "table"` 的块时：

```text
IF table_ref 可解析（content.blocks.json 或 chunk block）:
  sidecar = load tables/{path}  # 对齐 doc_chunk.table.access.load_table_model
  raw_markdown   ← sidecar.markdown
  table_summary  ← sidecar.llm_text
  table_schema   ← { layout_type, grid_width, record_groups, schema_version }
  table_headers  ← logical_rows[0] if present
  table_rows     ← logical_rows[1:] or derived from records
ELSE:
  沿用 block.text / block.markdown（旧工作区向后兼容）
```

char 锚点仍来自 block / manifest entry，与现逻辑一致。

### 5.3 消费方

- `knowledge_chunks` API 已暴露 `table_schema` / `table_headers` / `table_rows`；seed 填充后录入与浏览页自动受益
- `entry_content_service` 暂不改为 llm_text 切片（content.md 仍为录入正文源）；表格详情由 linked `chunk_assets` 提供

### 5.4 测试

- 单元：`test_knowledge_asset_seed.py` 增加含 `tables/t0000.json` + `content.blocks.json` table_ref 的 fixture
- 断言：`ChunkAsset.table_schema` 非空、`raw_markdown` 与 sidecar.markdown 一致
- 契约/集成：docx 样例 parse 后 seed 行数 ≥ 表格块数

---

## 6. 实施顺序（3 PR）

| PR | 范围 | 验收 |
|----|------|------|
| **PR1** | `file_import_purge_service` 重写 + API/前端删除 UX + purge 测试 | 删除后 chunks/存储清空；可 re-upload |
| **PR2** | tender_skills 升级 + `asset_seed_service` + fixture/测试 | 表格 asset 含 sidecar 字段 |
| **PR3** | V2 全量 rename（前后端 + 测试） | grep 无 V2 痕迹；路由/导航正确 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| purge 遗漏 FK → DELETE 409 | 先写 contract test；删除顺序按 §3.2 |
| 硬删误操作不可恢复 | 前端明确文案；purge-impact 展示计数 |
| rename 漏改 import | PR3 全库 grep + vitest/pytest |
| 旧 workspace 无 tables/ | table_ref 缺失时 fallback 现有 markdown 逻辑 |
| sidecar schema 与 tk 字段映射 | 单元测试锁定映射；不存 grid 全量 JSON 入 table_rows |

---

## 8. 非目标

- 已删除 import 的「恢复」功能
- `FileImportStatus.deleted` enum 的数据库 migration 移除
- tender_skills 包内新功能开发
- 录入正文改用 `substitute_tables_for_llm` 替换 content.md（后续迭代）
