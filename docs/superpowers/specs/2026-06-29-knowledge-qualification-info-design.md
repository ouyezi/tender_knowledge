# Design: 知识块资质信息字段合并与索引增强

**Date**: 2026-06-29  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-28-knowledge-chunk-field-trim-design.md`  
**Problem**: 证书编号/日期分列维护成本高、与业务语义（资质/授权/证书）不匹配；旧版 `embedding_task` 与当前索引流水线重复；预填与索引的 LLM 契约需统一，并在索引时结合图片理解更新资质信息。

---

## 1. 背景与目标

### 1.1 目标

1. **删除旧版代码**：移除 `embedding_task.embed_knowledge_chunk` 及其测试（当前生产路径为 `chunk_index_task.index_knowledge_chunk`）。
2. **字段合并**：用单一文本字段 `qualification_info`（展示名「资质信息」）替代 `certificate_number` + `certificate_date`。
3. **LLM 契约统一**：预填与索引摘要共用输出格式；索引阶段结合 Vision 图片理解与正文，更新 `summary` 与 `qualification_info`。

### 1.2 已锁定决策

| 议题 | 决议 |
|------|------|
| 块级 `expire_date` | **保留**；从各资质有效期解析后取 **最早（min）**，供列表筛选 `expire_date_from/to`、`is_expired` |
| 资质文本格式 | 单条 `简称\|编号\|发证日期\|有效期`；多条用英文分号 `;` 分隔 |
| 数据迁移 | **不考虑**；清库后按新 schema 重建（`TRUNCATE knowledge_chunks CASCADE`） |
| 预填 | **与索引共用** LLM 输出字段（`summary`、`qualification_info`、`date_confidence`） |
| 置信度门槛 | `qualification_info` 与 `expire_date` 仅在 `date_confidence == "high"` 时更新；`summary` 在非空时即可更新 |
| 旧版 embedding | 删除 `embedding_task.py` 与 `test_knowledge_embedding.py` |

### 1.3 不在范围

- `dynamic_knowledge_records` 证书相关字段
- `chunk_assets` 表结构与 Vision 缓存机制
- 语义检索打分逻辑（`chunk_search_service`）
- `chunk_embeddings` 三路向量策略

---

## 2. 方案对比与决议

| 方案 | 描述 | 决议 |
|------|------|------|
| ① 单一文本 + 解析工具 | `qualification_info` 存结构化文本；服务层解析并推导 `expire_date` | **采用** |
| ② JSONB 数组 | 资质存 JSON，另生成展示文本 | 与 field-trim 已否决的 JSONB 方案重复 |
| ③ 保留旧列 + 展示字段 | 双写 `certificate_*` 与 `qualification_info` | 冗余、易不一致 |

---

## 3. 数据模型

### 3.1 `knowledge_chunks` DDL 变更

**删除列**

| 列名 | 原因 |
|------|------|
| `certificate_number` | 并入 `qualification_info` |
| `certificate_date` | 并入 `qualification_info` |

**新增列**

| 列名 | 类型 | 说明 |
|------|------|------|
| `qualification_info` | `varchar(2048)` NULL | 资质信息；人可读、机器可解析 |

**保留列**

| 列名 | 说明 |
|------|------|
| `expire_date` | `date` NULL；块级最早失效日，由 `qualification_info` 自动推导 |
| `summary` | LLM 可更新 |

### 3.2 `qualification_info` 格式规范

**单条记录（4 段，`|` 分隔）**

```
{简称}|{编号}|{发证日期}|{有效期}
```

| 段 | 含义 | 示例 |
|----|------|------|
| 简称 | 证书/授权/资质名称 | `ISO9001`、`营业执照`、`软件著作权` |
| 编号 | 证书号、登记号、授权书编号等 | `A001`、`2020SR1234567` |
| 发证日期 | 发证/登记/授权日期 | `2024-01-01` |
| 有效期 | 失效日或描述性文本 | `2026-12-31` 或 `长期有效` |

**多条记录**：英文分号 `;` 分隔。

**示例**

```
ISO9001|A001|2024-01-01|2026-12-31;软件著作权|2020SR1234567|2020-06-01|2030-06-01
```

**规则**

| 规则 | 说明 |
|------|------|
| 日期格式 | 第 3、4 段若含日期，必须为 `YYYY-MM-DD` |
| 空段 | 未知子字段留空但保留 `|`（如 `ISO9001\|\|2024-01-01\|`） |
| 写入前 | 经 `normalize_qualification_info` trim、去重、校验 |
| 总长度 | ≤ 2048 字符 |
| 非资质类 | 允许 `NULL` 或空字符串 |

### 3.3 `expire_date` 推导

1. `parse_qualification_records(qualification_info)` 得到记录列表。
2. 从每条记录第 4 段（有效期）尝试解析 `YYYY-MM-DD`。
3. 取所有成功解析日期的 **min** 写入 `expire_date`。
4. 无法解析任何日期（如仅「长期有效」）→ `expire_date = NULL`。
5. 列表筛选 `expire_date_from/to`、`is_expired` 逻辑**不变**。

### 3.4 迁移

```sql
TRUNCATE knowledge_chunks CASCADE;

ALTER TABLE knowledge_chunks
  DROP COLUMN IF EXISTS certificate_number,
  DROP COLUMN IF EXISTS certificate_date;

ALTER TABLE knowledge_chunks
  ADD COLUMN IF NOT EXISTS qualification_info varchar(2048) NULL;
```

与 2026-06-28 field-trim 策略一致：开发/测试环境清库重建，不做旧数据转换。

---

## 4. 服务层

### 4.1 `qualification_field_utils.py`

新建（自 `certificate_field_utils.py` 演进；删除或合并旧模块）：

| 函数 | 职责 |
|------|------|
| `normalize_qualification_info(value)` | 规范化分隔符、trim、去重整条记录、校验 ISO 日期 |
| `parse_qualification_records(value)` | 解析为 `list[QualificationRecord]`（name, number, issue_date, expire_text） |
| `earliest_expire_date_from_qualification_info(value)` | 推导块级 `expire_date` |
| `format_qualification_record(...)` | 单条组装（测试与 LLM 后处理） |

保留通用日期工具（如 `parse_expire_date_value`）供 API 入参校验。

### 4.2 写入路径

以下路径在持久化前调用规范化，并在有 `qualification_info` 时推导 `expire_date`：

| 模块 | 场景 |
|------|------|
| `chunk_service.create_knowledge_chunk` | 手工/批量入库 |
| `prefill_service._normalize_prefill` | 录入预填 |
| `chunk_summary_service.apply_summary_update` | 索引摘要重写 |

### 4.3 删除旧版 `embedding_task`

| 删除文件 | 说明 |
|----------|------|
| `backend/src/services/knowledge/embedding_task.py` | 旧版纯向量化；含 `embed_knowledge_chunk`、`get_embedding_status` |
| `backend/tests/unit/test_knowledge_embedding.py` | 仅测试旧模块 |

**保留**：`chunk_index_task.index_knowledge_chunk` 为唯一知识块索引入口。状态以 `KnowledgeChunk.embedding_status` 为准。

---

## 5. LLM 契约（预填 + 索引）

### 5.1 输出 JSON

```json
{
  "summary": "1~3 句摘要",
  "qualification_info": "简称|编号|发证日|有效期;...",
  "date_confidence": "high|medium|low"
}
```

### 5.2 更新规则（`apply_summary_update` / 预填 normalize）

| 字段 | 条件 |
|------|------|
| `summary` | LLM 返回非空 → 更新；空 → 保留原值，`warnings` 含 `summary_rewrite_empty` |
| `qualification_info` | 仅 `date_confidence == "high"` → 规范化后写入 |
| `expire_date` | 仅 high → 由新 `qualification_info` 推导 min |

低/中置信度：保留用户已填或原 `qualification_info`、`expire_date`。

### 5.3 Prompt 变更

**预填**（`knowledge_prefill_prompt.py`）

- 移除 `certificate_number` / `certificate_date` 说明。
- 新增 `qualification_info` 格式、示例与资质类 `block_type` 提取指引。

**索引摘要**（`chunk_summary_service._SUMMARY_SYSTEM_PROMPT`）

- 输出字段改为 `summary`、`qualification_info`、`date_confidence`。
- 强调结合 `image_context`（Vision caption/OCR/extracted_facts）与正文提取或修正资质。
- `information_role=core` 的证书/资质图应写入 `qualification_info`；`auxiliary` 图忽略。

**用户 Prompt（索引）**

- 保持传入：标题、原摘要、正文（截断）、图片信息（截断）。

### 5.4 索引流水线（不变，仅字段替换）

```
ensure_image_assets_for_chunk
  → Vision（缓存）→ image_context（core 图）
  → rewrite_chunk_summary(...)
  → apply_summary_update(qualification_info, expire_date, ...)
  → _upsert_chunk_embeddings(title, summary, content)
  → embedding_status = ready | skipped | failed
```

---

## 6. API 与前端

### 6.1 后端

| 文件 | 变更 |
|------|------|
| `models/knowledge_chunk.py` | ORM 列替换 |
| `api/schemas/knowledge_chunks.py` | Create/Detail/Filters：`qualification_info` 替代 `certificate_*` |
| `api/routes/knowledge_chunks.py` | 序列化；`expire_date` 筛选与 `is_expired` 不变 |

### 6.2 前端

| 文件 | 变更 |
|------|------|
| `services/knowledgeChunks.ts` | 类型 |
| `constants/knowledgeChunkMeta.ts` | `qualification_info: "资质信息"` |
| `KnowledgeEntryPage.tsx` | 单字段录入 + 格式 placeholder |
| `KnowledgeChunkDetailDrawer.tsx` | 展示；可将 `;` 拆为多行 |
| `KnowledgeBrowsePage.tsx` | 列表列（若展示） |
| `batchIngestUtils.ts` | 批量 payload |

---

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| `llm_enabled=false` 或 LLM 失败 | 跳过 LLM 步骤；保留已有字段 |
| `date_confidence != high` | 不覆盖 `qualification_info`、`expire_date` |
| `qualification_info` 部分段非法 | 规范化丢弃非法整条或非法日期段；记 `warnings` |
| 向量服务未配置 | `embedding_status=skipped`；Vision/摘要/资质仍可能已提交 |
| 索引异常 | `embedding_status=failed` |

---

## 8. 测试

| 类型 | 文件/场景 |
|------|-----------|
| 单元 | `test_qualification_field_utils.py`：解析、规范化、min 日期 |
| 单元 | `test_chunk_summary_service.py`：置信度门槛、字段写入 |
| 单元 | `test_chunk_index_task.py`：索引后 `qualification_info` |
| 单元 | `test_knowledge_prefill.py`：预填输出格式 |
| 单元 | 确认无 `embedding_task` 引用 |
| 集成 | `test_knowledge_api.py`：CRUD 含 `qualification_info` |
| 集成 | migration 测试（清库 + 新列） |
| 前端 | `knowledgeChunkMeta.test.ts`、`batchIngestUtils.test.ts` |

---

## 9. 实现文件清单（预估）

| 文件 | 操作 |
|------|------|
| `backend/alembic/versions/20260629_*_qualification_info.py` | 新增 migration |
| `backend/src/services/knowledge/qualification_field_utils.py` | 新增 |
| `backend/src/services/knowledge/certificate_field_utils.py` | 删除或合并 |
| `backend/src/models/knowledge_chunk.py` | 修改 |
| `backend/src/services/knowledge/chunk_service.py` | 修改 |
| `backend/src/services/knowledge/chunk_summary_service.py` | 修改 |
| `backend/src/services/knowledge/chunk_index_task.py` | 修改 |
| `backend/src/services/knowledge/knowledge_prefill_prompt.py` | 修改 |
| `backend/src/services/knowledge/prefill_service.py` | 修改 |
| `backend/src/api/schemas/knowledge_chunks.py` | 修改 |
| `backend/src/api/routes/knowledge_chunks.py` | 修改 |
| `backend/src/services/knowledge/embedding_task.py` | **删除** |
| `backend/tests/unit/test_knowledge_embedding.py` | **删除** |
| `frontend/src/**` | 见 §6.2 |
| `backend/tests/**` | 同步更新 payload 与断言 |

---

## 10. 验收标准

1. 知识块表仅有 `qualification_info` + `expire_date`，无 `certificate_number`/`certificate_date`。
2. 预填 API 返回符合格式的 `qualification_info`（资质类章节）。
3. 构建索引后，结合正文与 core 图片，`qualification_info` 与 `summary` 可更新；high 置信度时 `expire_date` 与筛选一致。
4. `embedding_task` 及引用已移除，索引仅走 `chunk_index_task`。
5. 前端录入/详情/批量导入展示「资质信息」字段。
