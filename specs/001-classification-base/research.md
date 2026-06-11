# Research: Epic 0 分类底座

**Date**: 2026-06-11  
**Feature**: `specs/001-classification-base`

## R1 — 技术栈选型（绿field 项目）

### Decision

采用 **Python 3.11 + FastAPI** 后端、**PostgreSQL 15** 持久化、**React 18 + TypeScript + Ant Design**
管理后台的单体仓库（monorepo）结构。

### Rationale

- 仓库尚无应用代码；Epic 0 以 CRUD + 树形治理 + 审计为主，关系型数据库与 REST API 足够。
- 用户环境规则引用 `.venv/bin/python`，与 Python 后端一致。
- PostgreSQL 支持事务（合并/引用迁移）、唯一约束（别名）、递归 CTE（树查询）。
- Ant Design Tree/Table 组件适合产品分类树与章节分类维护场景。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| MongoDB 文档树 | 合并迁移、别名唯一、审计事务性较弱 |
| 纯 API 无前端 | Epic 0 明确要求管理后台（产品分类中心、章节目录中心） |
| Django Admin | 定制树编辑、影响分析、合并流程交互成本高 |
| GraphQL | Epic 1+ 以 REST 清单为主（总需求 §16），首 Epic 保持简单 |

---

## R2 — 层级分类存储模型

### Decision

Product Category 与 Chapter Taxonomy 均使用 **邻接表（parent_id）+ materialized path（path 字符串）**
双字段模型；查询树用 recursive CTE 或 path prefix。

### Rationale

- 深度通常 ≤ 5 层，邻接表足够简单。
- materialized path 加速子树查询与「禁止循环引用」校验。
- 合并操作可在单事务内更新 path 与引用表。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 闭包表（closure table） | Epic 0 规模下过度设计 |
| 仅 nested set | 移动节点成本高，不利于频繁编辑 |

---

## R3 — 别名与同义名唯一性

### Decision

- Product Category 别名：知识库内 `(kb_id, alias_normalized)` 全局唯一（标准名也参与唯一校验）。
- Chapter Taxonomy 同义名：同上，与 product category 别名分表/分 scope 隔离。
- `alias_normalized` = 去空格、统一大小写（中文保持原样）后的比较键。

### Rationale

- 满足 spec FR-003 与 edge case「别名占用」。
- Epic 1 按别名搜索定位分类时不会歧义。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅 sibling 级唯一 | 无法满足「按别名搜索全局定位」 |
| 不做规范化 | 「餐补 」与「餐补」重复 |

---

## R4 — 分类编码（category_code）唯一范围

### Decision

**同级 sibling 唯一**：`(kb_id, parent_id, category_code)` 唯一；跨分支允许相同 code。

### Rationale

- 与 spec Assumptions 一致。
- 不同产品线分支可使用相同业务编码惯例。

---

## R5 — 影响分析与引用追踪

### Decision

引入 **`classification_reference`** 通用引用表，字段：
`(kb_id, classification_type, classification_id, object_type, object_id)`。

Epic 0 实现统计 API；Epic 1–3 写入引用。Epic 0 上线初期计数为 0，结构与 API 就绪。

`object_type` 枚举：`ku | wiki | template | template_chapter | bid_outline | manual_asset | candidate_knowledge`。

### Rationale

- 满足 FR-006 按类型分组计数。
- 避免 Epic 0 为尚未存在的表建硬外键。
- 合并时单事务批量 UPDATE reference 行。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 各业务表反查 COUNT | Epic 0 业务表不存在，且合并迁移分散 |
| 仅返回 0 占位 | 无法满足 SC-003 端到端验证与合并迁移测试 |

---

## R6 — 合并与生命周期语义

### Decision

| 状态 | 含义 | 可选列表 | 可合并 |
|------|------|----------|--------|
| active | 启用 | 是 | 是 |
| inactive | 停用 | 否（默认） | 是 |
| archived | 归档 | 否 | 否（需先激活或走合并） |
| merged | 已合并 | 否 | 否 |

合并：源 → 目标，源状态 `merged`，记录 `merged_into_id`；引用迁移；写 audit。

停用父节点：若存在 `active` 子节点则 **拒绝**（spec edge case）。

### Rationale

- 与总需求 status 字段一致。
- `merged` 终态满足「源分类不可再被选用」。

---

## R7 — 审计与 trace

### Decision

`classification_audit_log` 表：`trace_id`（UUID）、`operator_id`、`action`、`entity_type`、
`entity_id`、`payload_summary`、`created_at`。

所有写操作 MUST 产生 audit 行；API 响应含 `trace_id`。

### Rationale

- 满足 constitution G4 与 FR-010。
- 与 V3.0 操作日志要求（§20.1 #9）一致。

---

## R8 — 人工覆盖优先级（Epic 0 范围）

### Decision

Epic 0 在数据模型预留 **`source` 字段**（`manual | suggested | imported`）于分类绑定关系
（chapter ↔ product category）及未来 `object_classification` 关联表；Epic 1 导入确认写入
`manual` 覆盖 `suggested`。

Epic 0 不实现导入建议 UI，仅文档化规则与 schema 预留。

### Rationale

- 满足 FR-011 与 constitution G3 在不引入 Candidate 流程下的最小合规。

---

## R9 — API 风格

### Decision

REST JSON API，前缀 `/api/v1/kbs/{kb_id}/`；OpenAPI 3.1 由 FastAPI 自动生成；
`contracts/` 目录存放人类可读契约摘要。

### Rationale

- 与总需求 §16 API 清单风格一致。
- Epic 1 消费读接口路径稳定。

---

## Resolved Clarifications

| 原标记 | 决议 |
|--------|------|
| 技术栈 | Python/FastAPI/PostgreSQL/React（R1） |
| category_code 唯一范围 | sibling 级（R4） |
| 影响分析无业务表 | classification_reference 通用表（R5） |
