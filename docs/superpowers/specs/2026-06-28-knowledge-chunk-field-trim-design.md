# Design: 知识块字段精简与证书信息

**Date**: 2026-06-28  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-28-knowledge-taxonomy-design.md`  
**Problem**: 知识块录入/浏览字段过多，部分仅历史兼容、部分与资产预览重复；资质类需要证书编号/日期与块级失效日，但不需要生效日期与页面定位字段对用户可见。

---

## 1. 背景与目标

### 1.1 删除字段（用户不可见、API 不暴露）

| 字段 | 原因 |
|------|------|
| `page_start` / `page_end` | 预览可从切片与资产临时计算，无需持久化在知识块 |
| `edit_distance_avg` | 无产品使用场景 |
| `variables` / `exclusion_rules` | 模版变量体系未落地，录入负担大 |
| `need_parent_context` | 无生成链路消费 |
| `winning_flag` | 筛选/标记无实际工作流 |
| `is_immutable` | 无强制只读消费 |
| `issue_date` | 由证书日期字段替代语义 |

### 1.2 起止字符（内部保留）

| 字段 | 决策 |
|------|------|
| `char_start` / `char_end` | **保留在 DB**，入库时由章节切片自动计算，用于 `link_assets_to_chunk` 与 `ensure_image_assets_for_chunk`；**不在页面展示**，Create/Detail/List API **不暴露给前端** |

### 1.3 证书与有效期

| 字段 | 决策 |
|------|------|
| `certificate_number` | 新增；多个证书编号英文逗号分隔 |
| `certificate_date` | 新增；多个证书日期 `YYYY-MM-DD` 逗号分隔，与编号按位置一一对应 |
| `expire_date` | 保留；从正文/图片提取多个失效日时取 **最早（min）** 作为块级失效日 |
| `issue_date` | 删除 |

### 1.4 已锁定决策

| 议题 | 决议 |
|------|------|
| 多失效日期聚合 | **min（最早到期）** |
| 迁移策略 | **一次性替换**；`TRUNCATE knowledge_chunks` |
| 起止页 | 从知识块表删除 |
| 起止字符 | DB 内部保留，UI/API 不展示 |
| 动态知识表 | 本次不改 `dynamic_knowledge_records` |

### 1.5 不在范围

- `chunk_assets` 的 `char_start/char_end/page_start/page_end`（资产定位）
- `NodePreview` 运行时 `char_start`（内容预览组件用）
- `dynamic_knowledge_records.issue_date`

---

## 2. 方案对比与决议

| 方案 | 描述 | 决议 |
|------|------|------|
| ① 精简主表 | DROP 冗余列 + 证书 varchar 字段；char 内部自动写 | **采用** |
| ② 证书侧车表 | 一对多证书行 | 过度设计 |
| ③ 证书 JSONB | 灵活但筛选/展示复杂 | 不采用 |

---

## 3. 数据模型

### 3.1 `knowledge_chunks` DDL

**删除列**

```
page_start, page_end
edit_distance_avg
variables, exclusion_rules
need_parent_context, winning_flag, is_immutable
issue_date
```

**保留（内部）**

```
char_start, char_end  -- 服务端自动写入，API 不返回
```

**新增列**

| 字段 | 类型 | 说明 |
|------|------|------|
| `certificate_date` | `varchar(512)` NULL | 证书日期，逗号分隔 |
| `certificate_number` | `varchar(1024)` NULL | 证书编号，逗号分隔 |

**保留列**

| 字段 | 说明 |
|------|------|
| `expire_date` | `date` NULL；块级失效日 |

### 3.2 证书字段规则

| 规则 | 说明 |
|------|------|
| 分隔符 | 英文逗号 `,`；写入前 trim 每项 |
| 对应关系 | 第 i 个编号 ↔ 第 i 个证书日期 |
| `expire_date` | 多个失效日取 `min`；无则 NULL |
| 校验 | 服务层校验日期格式；编号长度 ≤1024 总宽；非资质类允许全空 |
| 展示 | 资质/财务/知识产权类 block_type 录入时 UI 强提示（非硬拦截） |

### 3.3 迁移

```sql
TRUNCATE knowledge_chunks CASCADE;

ALTER TABLE knowledge_chunks
  DROP COLUMN IF EXISTS page_start,
  DROP COLUMN IF EXISTS page_end,
  DROP COLUMN IF EXISTS edit_distance_avg,
  DROP COLUMN IF EXISTS variables,
  DROP COLUMN IF EXISTS exclusion_rules,
  DROP COLUMN IF EXISTS need_parent_context,
  DROP COLUMN IF EXISTS winning_flag,
  DROP COLUMN IF EXISTS is_immutable,
  DROP COLUMN IF EXISTS issue_date,
  ADD COLUMN certificate_date VARCHAR(512),
  ADD COLUMN certificate_number VARCHAR(1024);
-- char_start, char_end 保留
```

---

## 4. 入库与资产关联

```text
create_knowledge_chunk():
  1. entry_content_service 按 primary_node_id 切片 → 得到 char_start/char_end（内存）
  2. 写入 KnowledgeChunk（含 char 字段，不含 page 字段）
  3. link_assets_to_chunk(char_start, char_end)
  4. ensure_image_assets_for_chunk(chunk, base_char=char_start)
```

`get_node_preview()` 继续返回运行时 `char_start/page_start` 供预览组件使用，不依赖 chunk 表上的 page 字段。

---

## 5. API 契约

### 5.1 CreateKnowledgeChunkRequest

**删除**: `page_start`, `page_end`, `char_start`, `char_end`, `variables`, `exclusion_rules`, `need_parent_context`, `winning_flag`, `is_immutable`, `edit_distance_avg`, `issue_date`

**新增**:

```python
certificate_date: str | None = None
certificate_number: str | None = None
expire_date: date | None = None  # 保留
```

### 5.2 Detail / List 响应

- 删除所有已 DROP 字段（含 `char_start/char_end`）
- 新增 `certificate_date`, `certificate_number`
- 保留 `expire_date`, `is_expired`（计算字段）

### 5.3 ListFilters

**删除**: `winning_flag`, `issue_date_from`, `issue_date_to`

**保留**: `expire_date_from/to`, `expired_only`

---

## 6. 前端变更

| 区域 | 变更 |
|------|------|
| KnowledgeEntryPage | 删除定位/变量/排除/中标等表单项；新增证书编号、证书日期；保留失效日期 |
| KnowledgeBrowsePage | 删除 winning、生效日期筛选 |
| KnowledgeChunkDetailDrawer | 展示证书字段 + 失效日期 + 过期 Badge |
| batchIngestUtils | payload 同步 |
| knowledgeChunkMeta.ts | 更新 label；删除废弃 ENUM/label |
| knowledgeChunks.ts | TS 类型同步 |

`NodePreview` / `KnowledgeContentViewer` 的 `sectionCharStart` 不变（预览层，非 chunk 持久字段）。

---

## 7. LLM 预填与索引摘要

### 7.1 prefill_service / knowledge_prefill_prompt

- 删除 `issue_date`, `winning_flag` 输出要求
- 新增 `certificate_date`, `certificate_number`
- `expire_date`：多值时规范为 `min`
- 资质类章节优先提取证书信息

### 7.2 chunk_summary_service

- 删除 `issue_date` 从 LLM JSON 与 `apply_summary_update`
- 新增证书编号/日期提取；`expire_date` 取 min
- 更新 system prompt

### 7.3 image_extraction_utils

- 证书 OCR 字段映射：`cert_no` → `certificate_number`，发证日期 → `certificate_date`，失效 → 参与 `expire_date` min

---

## 8. 测试策略

| 范围 | 要点 |
|------|------|
| Unit | 证书逗号解析；多失效日 min；create 自动写 char 但不序列化 |
| Integration | CRUD 不含已删字段；预填输出新字段 |
| Frontend | 表单/详情/批量入库；meta label |
| Fixtures | chunk_payload helper 更新 |

---

## 9. 实施顺序

1. Alembic migration（TRUNCATE + DROP/ADD）
2. ORM + schemas + chunk_service（切片写 char）
3. API routes 序列化/筛选
4. prefill + chunk_summary + image 映射
5. 前端录入/浏览/详情/批量
6. 全量测试 fixtures 更新

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| TRUNCATE 丢数据 | 用户已确认可清空 |
| 隐藏 char 字段后资产关联失败 | create 路径集成测试覆盖 link + image asset |
| 证书多值顺序错乱 | 预填 prompt 强调编号与日期位置对应 |
