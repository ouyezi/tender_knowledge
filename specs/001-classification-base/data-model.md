# Data Model: Epic 0 分类底座

**Date**: 2026-06-11（Epic 0 实现同步：2026-06-11）  
**Feature**: `specs/001-classification-base`

## Overview

```text
Knowledge Base (kb)
  ├── KB Clone Log (深拷贝审计)
  ├── Product Category (tree)
  │     └── aliases[]
  ├── Chapter Taxonomy (tree)
  │     ├── synonyms[]
  │     └── ↔ Product Category (M:N binding)
  ├── Classification Reference (Epic 0 建表；Epic 1+ 写入)
  └── Classification Audit Log
```

所有实体按 `kb_id` 隔离。

## Implementation notes (Epic 0 现状)

| 项 | 说明 |
|----|------|
| Schema  bootstrap | 应用启动时 `init_db.create_all` 建表；Alembic baseline 迁移待补 |
| 唯一性约束 | `(kb_id, alias_normalized)` 等 UNIQUE 规则由 **应用层** `alias_registry` 校验；DB 级唯一索引随迁移补齐 |
| `kb_id` 列 | ORM 中为 UUID 列 + 业务校验；部分表未声明 FK 至 `knowledge_bases`（Epic 0 可接受） |
| 别名/同义名去重 | 创建或替换时，与标准名（`category_name` / `standard_name`）normalized 相同的 alias/synonym **自动过滤**，不持久化、不报错 |

---

## Entity: Knowledge Base


| Field      | Type      | Notes            |
| ---------- | --------- | ---------------- |
| kb_id      | UUID PK   |                  |
| name       | string    |                  |
| status     | enum      | active, inactive |
| created_at | timestamp |                  |
| updated_at | timestamp |                  |


Epic 0 至少支持单标书知识库实例；多 KB  schema 就绪。

---

## Entity: KB Clone Log

记录一次 KB 深拷贝操作（P0）。


| Field        | Type      | Notes     |
| ------------ | --------- | --------- |
| clone_id     | UUID PK   |           |
| target_kb_id | UUID FK   | 新 KB      |
| source_kb_id | UUID FK   | 源 KB      |
| operator_id  | string    |           |
| trace_id     | string    | 关联 API 请求 |
| created_at   | timestamp |           |


克隆范围：产品分类树 + 章节分类树（含别名/同义名/绑定）；节点数上限 2000。

---

## Entity: Product Category


| Field          | Type        | Constraints                     | Notes                                        |
| -------------- | ----------- | ------------------------------- | -------------------------------------------- |
| category_id    | UUID PK     |                                 |                                              |
| kb_id          | UUID FK     | NOT NULL                        |                                              |
| parent_id      | UUID FK     | NULL = root                     |                                              |
| category_name  | string(128) | NOT NULL                        | 标准显示名                                        |
| category_code  | string(64)  | NOT NULL                        | sibling 唯一                                   |
| description    | text        | nullable                        |                                              |
| status         | enum        | active/inactive/archived/merged |                                              |
| merged_into_id | UUID FK     | nullable                        | merged 时指向目标                                 |
| path           | string(512) | NOT NULL                        | materialized path, e.g. `/root-id/child-id/` |
| depth          | int         | NOT NULL                        | 0-based                                      |
| created_at     | timestamp   |                                 |                                              |
| updated_at     | timestamp   |                                 |                                              |


### Validation rules

- `parent_id` MUST 同 kb；禁止循环（path 不得包含 self）。
- 创建/更新时 `depth` ≤ 10（软上限，防误操作）。
- `category_code` UNIQUE `(kb_id, parent_id, category_code)` where parent_id IS NULL use sentinel or partial index.
- 物理 DELETE 禁止；仅状态变更或 merge。
- **停用**（`inactive`）：若存在 **active** 子节点 → API `409 INVALID_STATE`，code `HAS_ACTIVE_CHILDREN`。
- **合并**：若源节点有 active 子节点 → `409 HAS_CHILDREN`；源/目标存在祖先关系 → `409 ANCESTOR_RELATION`。

### State transitions

```text
active ──→ inactive ──→ archived
   │           │
   └─ merge ───┴─→ merged (terminal)
```

- inactive/archived 可恢复为 active（若未 merged）。
- merged 不可逆。

---

## Entity: Product Category Alias


| Field            | Type        | Constraints                   |
| ---------------- | ----------- | ----------------------------- |
| alias_id         | UUID PK     |                               |
| category_id      | UUID FK     | ON DELETE RESTRICT            |
| kb_id            | UUID FK     | denormalized for unique scope |
| alias            | string(128) | NOT NULL                      |
| alias_normalized | string(128) | NOT NULL                      |
| created_at       | timestamp   |                               |


**UNIQUE** `(kb_id, alias_normalized)` — 应用层校验；不与 `category_name` 重复存储（见 Implementation notes）。

---

## Entity: Chapter Taxonomy


| Field          | Type        | Constraints        | Notes      |
| -------------- | ----------- | ------------------ | ---------- |
| taxonomy_id    | UUID PK     |                    |            |
| kb_id          | UUID FK     | NOT NULL           |            |
| parent_id      | UUID FK     | nullable           |            |
| standard_name  | string(128) | NOT NULL           | 章节类型标准名    |
| taxonomy_code  | string(64)  | NOT NULL           | sibling 唯一 |
| description    | text        | nullable           |            |
| status         | enum        | 同 Product Category |            |
| merged_into_id | UUID FK     | nullable           |            |
| path           | string(512) | NOT NULL           |            |
| depth          | int         | NOT NULL           |            |
| created_at     | timestamp   |                    |            |
| updated_at     | timestamp   |                    |            |


### Validation rules

- 与 Product Category 相同的树约束（含 `HAS_ACTIVE_CHILDREN`、`HAS_CHILDREN`、`ANCESTOR_RELATION`）。
- `standard_name` 在 kb 内不得与同义名冲突（统一 normalized 命名空间）。

---

## Entity: Chapter Taxonomy Synonym


| Field              | Type        | Constraints |
| ------------------ | ----------- | ----------- |
| synonym_id         | UUID PK     |             |
| taxonomy_id        | UUID FK     |             |
| kb_id              | UUID FK     |             |
| synonym            | string(128) | NOT NULL    |
| synonym_normalized | string(128) | NOT NULL    |
| created_at         | timestamp   |             |


**UNIQUE** `(kb_id, synonym_normalized)` — 应用层校验；不与 `standard_name` 重复存储。

---

## Entity: Chapter Taxonomy ↔ Product Category Binding


| Field       | Type      | Constraints               | Notes     |
| ----------- | --------- | ------------------------- | --------- |
| binding_id  | UUID PK   |                           |           |
| kb_id       | UUID FK   |                           |           |
| taxonomy_id | UUID FK   |                           |           |
| category_id | UUID FK   |                           |           |
| source      | enum      | manual/suggested/imported | FR-011 预留 |
| created_at  | timestamp |                           |           |
| created_by  | string    | operator id               |           |


**UNIQUE** `(taxonomy_id, category_id)`

---

## Entity: Classification Reference

Epic 0 定义；Epic 1+ 写入。


| Field               | Type      | Notes                                                                                |
| ------------------- | --------- | ------------------------------------------------------------------------------------ |
| reference_id        | UUID PK   |                                                                                      |
| kb_id               | UUID FK   |                                                                                      |
| classification_type | enum      | product_category, chapter_taxonomy                                                   |
| classification_id   | UUID      |                                                                                      |
| object_type         | enum      | ku, wiki, template, template_chapter, bid_outline, manual_asset, candidate_knowledge |
| object_id           | UUID      |                                                                                      |
| created_at          | timestamp |                                                                                      |


**INDEX** `(kb_id, classification_type, classification_id, object_type)`

合并时：批量 UPDATE `classification_id` from source → target；若目标已有同 object 引用则 dedupe 删除源行。

---

## Entity: Classification Impact Report (view/DTO)

非持久化；由 aggregation 查询产生。

```json
{
  "classification_type": "product_category",
  "classification_id": "uuid",
  "total_count": 42,
  "by_object_type": {
    "ku": 10,
    "wiki": 5,
    "template": 3,
    "template_chapter": 8,
    "bid_outline": 4,
    "manual_asset": 2,
    "candidate_knowledge": 10
  }
}
```

---

## Entity: Classification Audit Log


| Field           | Type      | Notes                                                                             |
| --------------- | --------- | --------------------------------------------------------------------------------- |
| audit_id        | UUID PK   |                                                                                   |
| trace_id        | UUID      | 关联一次 API 操作                                                                       |
| kb_id           | UUID      |                                                                                   |
| operator_id     | string    | V3.0 无 RBAC，记录用户标识                                                                |
| entity_type     | enum      | product_category, chapter_taxonomy                                                |
| entity_id       | UUID      |                                                                                   |
| action          | enum      | 见下表 |
| payload_summary | jsonb     | 变更摘要（JSON；Epic 0 ORM 使用 JSON 列） |
| created_at      | timestamp |                                                                                   |

### action 枚举与 Epic 0 实际写入

| action | Epic 0 是否写入 | 说明 |
|--------|----------------|------|
| create | ✅ | 创建分类/章节类型 |
| update | ✅ | 更新名称/描述/状态；**别名/同义名全集替换**也记为 update |
| bind | ✅ | 章节类型 ↔ 产品分类绑定替换 |
| deactivate | ✅ | 停用 |
| archive | ✅ | 归档 |
| merge | ✅ | 合并 |
| alias_add | — | 预留；当前合并入 `update` |
| alias_remove | — | 预留；当前合并入 `update` |
| unbind | — | 预留；绑定清空时记为 `bind`（空列表） |

---

## Relationships diagram

```text
KnowledgeBase 1──* ProductCategory (self-ref parent)
KnowledgeBase 1──* ChapterTaxonomy (self-ref parent)
KnowledgeBase 1──* KBCloneLog (source / target)
ProductCategory 1──* ProductCategoryAlias
ChapterTaxonomy 1──* ChapterTaxonomySynonym
ChapterTaxonomy *──* ProductCategory (via Binding)
ProductCategory 1──* ClassificationReference
ChapterTaxonomy 1──* ClassificationReference
KnowledgeBase 1──* ClassificationAuditLog
```

---

## Epic 1+ 预留（不在 Epic 0 建表）

- `object_classification`：业务对象与分类的多对多关联（含 source=manual/suggested）。
- 自动发现候选章节类型队列（Epic 2/3）。

