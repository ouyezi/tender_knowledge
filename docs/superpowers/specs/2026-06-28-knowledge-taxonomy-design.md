# Design: 知识块管理数据结构优化（Taxonomy + 动态知识）

**Date**: 2026-06-28  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md` · `docs/superpowers/specs/2026-06-26-writing-technique-design.md`  
**Problem**: 现有 `knowledge_chunks` 使用通用枚举（`category` / `quote_mode` / `products`），与投标业务语义脱节；缺少动态知识（品牌授权、门店、供应商）的独立建模；应用类型与业务线无标准配置。

---

## 1. 背景与目标

### 1.1 现状

| 维度 | 现有字段 | 问题 |
|------|----------|------|
| 业务分类 | `category` | 8 个粗粒度值（qualification / technical / …），无法表达两级业务类型 |
| 引用/应用方式 | `quote_mode` | 仅 full / partial，无法指导生成流水线策略 |
| 产品线 | `products` | 自由文本数组，无标准枚举 |
| 动态事实 | 无 | 品牌授权、门店、供应商等信息无法独立管理与后续 API 同步 |
| 有效期 | `issue_date` / `expire_date` | 字段已有，但缺少过期展示与筛选 |

### 1.2 产品目标

1. **配置表驱动分类**：taxonomy 单表维护四维度枚举，知识块通过 code 引用，支持后台扩展。
2. **两级知识块类型**：资质文件、财务资质、知识产权等 8 大类及子类。
3. **六种应用类型**：固定引用、优先引用、综合生成、模版填充、参考改写、事实提取。
4. **标准业务线**：通用、餐补、保险、礼包等 11 条，支持多选。
5. **动态知识独立表**：品牌授权、门店、供应商；V1 从历史标书/模版提取，预留 API 同步字段。
6. **块级有效期**：到期整块标记提醒，不做内容内事实级台账。

### 1.3 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 分类体系 | **配置表驱动**，code 引用 |
| 动态知识 | **独立实体表** `dynamic_knowledge_records` |
| 有效期 | **块级** `issue_date` / `expire_date` |
| Taxonomy 组织 | **单表多维度** `knowledge_taxonomy` + `parent_code` 两级树 |
| 迁移策略 | **一次性替换**；历史 `knowledge_chunks` 可 TRUNCATE，不做旧值映射 |

### 1.4 不在范围（V1）

- 内容内多条事实有效期台账（`validity_records`）
- 动态知识与外部 API 的实际对接（仅预留 `sync_status` / `last_synced_at`）
- 从历史标书自动批量提取动态知识的 pipeline（后续 Epic）
- KB 级 taxonomy 覆盖（`kb_id` 字段预留，V1 仅全局 seed）

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| ① 增量扩展 | 新旧字段并存，逐步迁移 | 风险低 | 双轨维护成本高 |
| **② 一次性替换（采用）** | DROP 旧字段，TRUNCATE 数据，全链路同步改 | 模型干净，无历史包袱 | 需同步改 API / 前端 / 测试 / LLM 预填 |
| ③ 关联表模式 | `chunk_taxonomy_assignments` 存多对多 | 最灵活 | 查询复杂，当前需求过度设计 |

**决议：方案 ②** — 用户确认历史数据可清空。

---

## 3. 架构总览

```text
knowledge_taxonomy (全局配置，4 dimensions)
        │
        ├──► knowledge_chunks
        │      block_type_code
        │      application_type_code
        │      business_line_codes[]
        │      issue_date / expire_date
        │      knowledge_type (内容形态，保留)
        │
        └──► dynamic_knowledge_records
               dynamic_type_code
               structured_data (JSONB)
               business_line_codes[]
               source: extracted → api (future)
```

**与现有模块关系**

- `knowledge_type`（fact / template / solution / case / table / image）与 `block_type_code` **正交**：前者描述内容形态，后者描述投标业务分类。
- `writing_techniques`、`chunk_embeddings` 不受影响；chunk 检索 filter 增加新维度。
- `chunk_assets` 在 TRUNCATE chunks 后需同步清理或 `chunk_id` 置空。

---

## 4. 数据模型

### 4.1 配置表 `knowledge_taxonomy`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | bigint PK | |
| `kb_id` | UUID NULL | NULL = 全局默认；V1 仅 NULL |
| `dimension` | varchar(32) NOT NULL | `block_type` / `application_type` / `business_line` / `dynamic_type` |
| `code` | varchar(64) NOT NULL | 稳定标识 |
| `parent_code` | varchar(64) NULL | 父级 code；一级为 NULL |
| `label` | varchar(128) NOT NULL | 中文展示名 |
| `label_en` | varchar(128) NULL | 可选英文 |
| `level` | smallint NOT NULL | 1 或 2 |
| `sort_order` | int NOT NULL DEFAULT 0 | |
| `is_active` | boolean NOT NULL DEFAULT true | |
| `metadata` | JSONB NOT NULL DEFAULT `{}` | 扩展描述 |
| `created_at` | timestamptz NOT NULL | |
| `updated_at` | timestamptz NOT NULL | |

**约束**

```sql
CREATE UNIQUE INDEX uq_knowledge_taxonomy_scope
  ON knowledge_taxonomy (
    COALESCE(kb_id, '00000000-0000-0000-0000-000000000000'::uuid),
    dimension,
    code
  );

ALTER TABLE knowledge_taxonomy
  ADD CONSTRAINT ck_knowledge_taxonomy_level CHECK (level IN (1, 2));
```

**校验规则（服务层）**

- `level = 2` 时 `parent_code` 非空，且 parent 同 dimension、`level = 1`
- `level = 1` 时 `parent_code` 必须为 NULL
- `application_type` / `business_line` / `dynamic_type` 仅 level = 1

### 4.2 种子数据

#### dimension = `block_type`

| code | parent_code | label | level |
|------|-------------|-------|-------|
| `qualification_document` | — | 资质文件 | 1 |
| `qualification_sub_brand` | qualification_document | 子品牌 | 2 |
| `qualification_headquarters` | qualification_document | 总公司 | 2 |
| `qualification_branch` | qualification_document | 分公司 | 2 |
| `financial_qualification` | — | 财务资质 | 1 |
| `awards_honors` | — | 获奖及荣誉材料 | 1 |
| `intellectual_property` | — | 知识产权 | 1 |
| `ip_software_copyright` | intellectual_property | 软著 | 2 |
| `ip_patent` | intellectual_property | 专利证书 | 2 |
| `ip_trademark` | intellectual_property | 商标证书 | 2 |
| `company_intro` | — | 企业介绍 | 1 |
| `company_product_intro` | company_intro | 企业产品介绍 | 2 |
| `company_history` | company_intro | 发展历程 | 2 |
| `company_org_structure` | company_intro | 组织架构 | 2 |
| `member_info` | — | 成员信息 | 1 |
| `member_tech_team` | member_info | 技术团队 | 2 |
| `member_product_team` | member_info | 产品团队 | 2 |
| `member_service_team` | member_info | 服务团队 | 2 |
| `official_template` | — | 官方模版 | 1 |
| `product_solution` | — | 产品方案知识 | 1 |

#### dimension = `application_type`

| code | label |
|------|-------|
| `fixed_reference` | 固定引用 |
| `preferred_reference` | 优先引用 |
| `composite_generation` | 综合生成 |
| `template_fill` | 模版填充 |
| `reference_rewrite` | 参考改写 |
| `fact_extraction` | 事实提取 |

#### dimension = `business_line`

| code | label |
|------|-------|
| `general` | 通用 |
| `meal_subsidy` | 餐补 |
| `insurance` | 保险 |
| `gift_package` | 超级礼包/礼包 |
| `health_check` | 体检 |
| `birthday` | 生日 |
| `movie` | 电影 |
| `procurement` | 物资采购 |
| `baifude` | 百福得 |
| `lefu_card` | 乐福卡 |

> 原需求列表中「保险」重复，种子数据仅保留一条。

#### dimension = `dynamic_type`

| code | label |
|------|-------|
| `brand_authorization` | 品牌授权信息 |
| `store_info` | 门店信息 |
| `supplier_info` | 供应商信息 |

### 4.3 主表 `knowledge_chunks` 变更

**删除字段**

| 字段 | 替代 |
|------|------|
| `category` | `block_type_code` |
| `quote_mode` | `application_type_code` |
| `products` | `business_line_codes` |

**新增字段**

| 字段 | 类型 | 约束 |
|------|------|------|
| `block_type_code` | varchar(64) NOT NULL | 引用 taxonomy，`dimension=block_type` |
| `application_type_code` | varchar(64) NOT NULL | 引用 taxonomy，`dimension=application_type` |
| `business_line_codes` | JSONB NOT NULL DEFAULT `["general"]` | 多选；空数组写入时规范化为 `["general"]` |

**保留字段（不变）**

- `knowledge_type`, `content_type`, `source_type`, `template_type`, `is_template`
- `issue_date`, `expire_date`, `status`, `tags`, `industries`, `customer_types`, `regions`
- 版本链、资产关联、embedding 相关字段

**DDL 策略**

```sql
TRUNCATE knowledge_chunks CASCADE;
-- chunk_assets.chunk_id 随 CASCADE 或单独 UPDATE SET chunk_id = NULL

ALTER TABLE knowledge_chunks
  DROP COLUMN category,
  DROP COLUMN quote_mode,
  DROP COLUMN products,
  ADD COLUMN block_type_code VARCHAR(64) NOT NULL,
  ADD COLUMN application_type_code VARCHAR(64) NOT NULL,
  ADD COLUMN business_line_codes JSONB NOT NULL DEFAULT '["general"]'::jsonb;

CREATE INDEX ix_knowledge_chunks_block_type ON knowledge_chunks (kb_id, block_type_code);
CREATE INDEX ix_knowledge_chunks_application_type ON knowledge_chunks (kb_id, application_type_code);
CREATE INDEX ix_knowledge_chunks_business_lines ON knowledge_chunks USING GIN (business_line_codes);
CREATE INDEX ix_knowledge_chunks_expire_date ON knowledge_chunks (kb_id, expire_date);
```

**写入校验**

- `block_type_code` 必须存在于 taxonomy 且 `is_active = true`
- 允许存 level-1 或 level-2 code；UI 默认引导选 level-2（有子类时）
- `application_type_code` 单值校验
- `business_line_codes` 每项校验；含 `general` 表示全业务线可用

### 4.4 动态知识表 `dynamic_knowledge_records`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | bigint PK | |
| `kb_id` | UUID NOT NULL | 租户隔离 |
| `dynamic_type_code` | varchar(64) NOT NULL | 引用 taxonomy，`dimension=dynamic_type` |
| `title` | varchar(255) NOT NULL | |
| `content` | text NOT NULL DEFAULT '' | 原始文本 |
| `structured_data` | JSONB NOT NULL DEFAULT `{}` | 结构化字段（品牌名、地址、资质号等） |
| `business_line_codes` | JSONB NOT NULL DEFAULT `["general"]` | 与静态块口径一致 |
| `source_type` | varchar(32) NOT NULL DEFAULT `extracted` | `extracted` / `api` |
| `source_doc_id` | UUID NULL | 来源文档 |
| `source_chunk_id` | bigint NULL | 来源知识块（可选，无 FK 强约束以免 purge 阻塞） |
| `issue_date` | date NULL | |
| `expire_date` | date NULL | |
| `status` | varchar(32) NOT NULL DEFAULT `draft` | draft / active / deprecated / disabled |
| `sync_status` | varchar(32) NOT NULL DEFAULT `pending` | pending / synced / failed（API 预留） |
| `last_synced_at` | timestamptz NULL | |
| `content_hash` | varchar(64) NOT NULL | |
| `create_time` | timestamptz NOT NULL | |
| `update_time` | timestamptz NOT NULL | |

**索引**

```sql
CREATE INDEX ix_dynamic_knowledge_kb_type ON dynamic_knowledge_records (kb_id, dynamic_type_code);
CREATE INDEX ix_dynamic_knowledge_kb_status ON dynamic_knowledge_records (kb_id, status);
CREATE INDEX ix_dynamic_knowledge_expire ON dynamic_knowledge_records (kb_id, expire_date);
CREATE INDEX ix_dynamic_knowledge_business_lines ON dynamic_knowledge_records USING GIN (business_line_codes);
```

---

## 5. 有效期处理

| 机制 | 说明 |
|------|------|
| 存储 | 仅 `issue_date` + `expire_date` |
| 计算 | API 响应附加 `is_expired: bool`（`expire_date IS NOT NULL AND expire_date < CURRENT_DATE`） |
| 筛选 | 列表支持 `expired_only=true`；保留现有 `expire_date_from/to` |
| 展示 | 浏览列表 / 详情对 `is_expired=true` 显示「已过期，需更新」标签 |
| 状态 | **不**自动修改 `status`；避免误禁用仍有效的块 |
| 录入 | 资质类 `block_type_code` 前缀为 `qualification_` / `financial_` / `ip_` 时，UI 强提示填写 `expire_date`（非硬拦截） |

---

## 6. API 契约

### 6.1 Taxonomy（全局）

**前缀**：`/api/v1/knowledge-taxonomy`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 查询参数：`dimension?`, `parent_code?`, `active_only=true` |
| GET | `/{code}` | 单条详情 |

响应示例：

```json
{
  "code": "qualification_sub_brand",
  "dimension": "block_type",
  "parent_code": "qualification_document",
  "label": "子品牌",
  "level": 2,
  "sort_order": 10,
  "is_active": true
}
```

V1 只读；管理端 CRUD 后续迭代。

### 6.2 知识块（变更）

**前缀**：`/api/v1/kbs/{kb_id}/knowledge-chunks`

**CreateKnowledgeChunkRequest 变更**

- 删除：`category`, `quote_mode`, `products`
- 新增：`block_type_code`, `application_type_code`, `business_line_codes`

**KnowledgeChunkListFilters 变更**

- 删除：`category`, `products`
- 新增：`block_type_code`, `application_type_code`, `business_line_codes`（overlap 匹配）, `expired_only`

**Detail 响应增补**：`is_expired`, taxonomy label 展开（`block_type_label`, `application_type_label`, `business_line_labels[]`）— 服务端 join 或二次查询 taxonomy 缓存。

### 6.3 动态知识（新）

**前缀**：`/api/v1/kbs/{kb_id}/dynamic-knowledge`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表 + 筛选（dynamic_type_code, status, business_line_codes, expired_only） |
| POST | `/` | 创建 |
| GET | `/{id}` | 详情 |
| PUT | `/{id}` | 更新 |
| DELETE | `/{id}` | 软删或 hard delete（V1 hard delete） |

---

## 7. 前端变更

| 区域 | 变更 |
|------|------|
| `knowledgeChunkMeta.ts` | 删除 `category` / `quote_mode` / `products` ENUM；新增 taxonomy 字段 label |
| Taxonomy Hook | `useKnowledgeTaxonomy(dimension)` 从 API 加载，缓存 session |
| 录入页 | 知识块类型 → 级联 Select（parent → child）；应用类型单选；业务线多选 Tag |
| 浏览页 | 筛选器换 taxonomy；过期块 Badge |
| 详情 Drawer | 展示新字段 + 过期警告 |
| 动态知识 | 新页面或 Tab（V1 可最小：列表 + 表单 CRUD） |

**Prefill**：LLM 输出改为 taxonomy code；前端表单直接绑定 code。

---

## 8. 后端模块结构

```text
backend/src/
├── models/
│   ├── knowledge_taxonomy.py          # 新
│   ├── dynamic_knowledge_record.py    # 新
│   └── knowledge_chunk.py             # 改字段
├── services/knowledge/
│   ├── taxonomy_service.py            # 新：校验 + 缓存 + seed
│   ├── dynamic_knowledge_service.py   # 新
│   ├── chunk_service.py               # 改写入/校验
│   └── prefill_service.py             # 改 prompt 枚举
├── api/
│   ├── routes/knowledge_taxonomy.py   # 新
│   ├── routes/dynamic_knowledge.py    # 新
│   └── schemas/knowledge_chunks.py    # 改
└── alembic/versions/
    └── 20260628_*_knowledge_taxonomy.py
```

---

## 9. 测试策略

| 范围 | 要点 |
|------|------|
| Unit | taxonomy 校验（level/parent）、chunk 写入非法 code 拒绝、business_line 空数组规范化 |
| Integration | taxonomy seed 加载、chunk CRUD 新字段、dynamic knowledge CRUD |
| Frontend | meta label、taxonomy hook、表单级联 |
| Fixtures | 所有测试 payload 换 `block_type_code` / `application_type_code` / `business_line_codes` |

---

## 10. 实施顺序

1. Alembic：建 `knowledge_taxonomy` + seed；TRUNCATE chunks；ALTER 换字段；建 `dynamic_knowledge_records`
2. 后端：models → taxonomy service → chunk/dynamic services → routes → prefill
3. 前端：taxonomy hook → 录入/浏览/详情改字段 → 动态知识最小 CRUD
4. 测试：fixtures 全量更新；集成测试绿
5. 文档：更新 `knowledge-v2` 相关 plan 中的枚举说明

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| TRUNCATE 丢失全部 chunk | 用户已确认可清空 |
| LLM 预填输出非法 code | prompt 限定枚举 + 服务端 fallback 到默认值 |
| taxonomy 缓存 stale | 启动时 load + 短 TTL 内存缓存；seed 变更需重启或 explicit invalidate |
| 动态知识与 chunk 来源断裂 | `source_chunk_id` 软引用；purge 时不级联删除 dynamic record |

---

## 12. 后续 Epic（非 V1）

- KB 级 taxonomy 扩展（`kb_id` 非空行覆盖全局）
- 动态知识 API 同步 worker
- 从历史标书 batch 提取 dynamic records
- Taxonomy 管理后台 CRUD
- 生成流水线按 `application_type_code` 路由策略
