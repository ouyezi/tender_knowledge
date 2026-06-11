# Design: Epic 0 分类底座（classification-base）

**Date**: 2026-06-11  
**Status**: Draft — pending user review  
**Feature spec**: `specs/001-classification-base/spec.md`  
**Implementation plan**: `specs/001-classification-base/plan.md`

## 1. 背景与目标

Epic 0 建立 V3.0 前置「分类底座」：在知识库内治理 **Product Category**（产品分类）
与 **Chapter Taxonomy**（章节分类），支撑后续导入、检索与推荐的统一口径。

本设计在 Spec Kit 制品（spec / plan / research / data-model / contracts）基础上，
补充 brainstorming 阶段决议的**交付切片、多 KB 平台壳层、KB 复制与生命周期、合并规则**。

## 2. 设计决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 交付策略 | **纵向切片**：P0 → P1 → P2 → P3，每片 API + UI + 测试 |
| D2 | 实现路径 | **薄 P0 平台壳层 + 纵向切片**（共享布局/审计/KB 上下文） |
| D3 | 多 KB | **完整多 KB 管理**（创建/列表/切换） |
| D4 | KB 在切片中的位置 | **P0 独立交付**，P1–P3 依赖「已选中 KB」 |
| D5 | 新建 KB 初始化 | **默认空库**；可选 **从现有 KB 深拷贝** 分类树与绑定（新 UUID，非共享） |
| D6 | KB 生命周期 | 支持 **inactive**；切换器默认隐藏；inactive KB 下分类 **只读** |
| D7 | 分类合并（有子节点） | **禁止合并**；须先处理子节点（移动/合并/停用） |
| D8 | 分类合并（父子关系） | 源与目标存在祖先-后代关系时 **拒绝**（沿用 spec edge case） |
| D9 | 技术栈 | FastAPI + PostgreSQL + React/Ant Design（沿用 plan/research） |

## 3. 架构与交付切片

### 3.1 交付顺序

```text
P0  KB 平台壳层（多 KB 管理 + 共享基础设施）
  → P1  产品分类中心（Product Category）
  → P2  章节目录中心（Chapter Taxonomy + 产品绑定）
  → P3  分类生命周期（停用/归档/合并 + 影响分析）
```

每条切片交付：**migration（如需）+ REST API + 管理页面 + contract/integration 测试 +
quickstart 场景更新**。

### 3.2 P0 — Knowledge Base 平台壳层

| 能力 | 说明 |
|------|------|
| KB CRUD | 创建（默认空）、列表、详情、改名 |
| KB 切换器 | 顶栏全局组件；`kb_id` 持久化至 localStorage |
| 创建时复制 | `clone_from_kb_id` 可选：深拷贝 Product Category 树、Chapter Taxonomy 树、M:N 绑定；全部新 UUID |
| KB 停用 | `status=inactive`；列表/切换器默认仅 active；进入 inactive KB 后全局只读 |
| 共享基础设施 | PostgreSQL、Alembic、`audit` middleware（`trace_id` + `X-Operator-Id`）、统一 API envelope |

**P0 验收**：创建两个 KB（一空一复制）；切换上下文；停用后分类只读且写 API 返回 403。

### 3.3 P1 — 产品分类中心

- 多级树 CRUD、别名维护、按标准名/别名搜索
- Epic 1 消费：`GET /tree?status=active`、`GET /search?q=`
- UI：左树 + 右详情/编辑（Ant Design Tree + Form）

### 3.4 P2 — 章节目录中心

- Chapter Taxonomy 树、同义名、与 Product Category M:N 绑定
- 按 `product_category_id` 筛选章节类型
- UI 与 P1 对称，增加产品分类多选绑定区

### 3.5 P3 — 分类生命周期

- 影响分析：`classification_reference` 按 `object_type` 聚合（Epic 0 可用 seed 验证）
- 停用 / 归档 / 合并（含 D7、D8 校验）
- UI：影响分析弹窗 + 合并向导

### 3.6 明确不在范围

- RBAC、文件导入、检索/生成、Bid Outline 自动发现章节类型
- KB 物理删除（有分类数据的 KB 不可删）
- industry / project_type / customer_type 维度

## 4. 组件与模块边界

### 4.1 后端（`backend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `routes/knowledge_bases.py` | KB CRUD、停用、clone 触发 | P0 |
| `services/kb_service.py` | KB 业务编排 | P0 |
| `services/kb_clone_service.py` | 深拷贝分类与绑定（单事务） | P0 |
| `routes/product_categories.py` | 产品分类 API | P1, P3 |
| `routes/chapter_taxonomies.py` | 章节分类 API | P2, P3 |
| `services/category_tree.py` | path/depth、循环检测 | P1, P2 |
| `services/alias_registry.py` | normalized 唯一校验 | P1, P2 |
| `services/impact_analysis.py` | 引用聚合 | P3 |
| `services/merge.py` | 合并事务与校验 | P3 |
| `api/deps.py` | `kb_write_guard`：inactive KB 写拦截 | P0+ |
| `api/middleware/audit.py` | trace + 审计日志 | P0+ |

### 4.2 前端（`frontend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `layout/AppShell.tsx` | 顶栏、导航、KB 切换器 | P0 |
| `layout/KBContext.tsx` | 当前 kb_id、只读态 | P0 |
| `pages/KnowledgeBaseList/` | KB 列表与创建（含复制选项） | P0 |
| `pages/ProductCategoryCenter/` | 产品分类树维护 | P1 |
| `pages/ChapterTaxonomyCenter/` | 章节分类维护 | P2 |
| `components/ImpactAnalysisModal.tsx` | 影响分析 | P3 |
| `components/MergeWizard.tsx` | 合并确认 | P3 |
| `components/CategoryTreePanel.tsx` | 共享左树 | P1, P2 |
| `components/CategoryDetailPanel.tsx` | 共享右详情 | P1, P2 |

### 4.3 依赖原则

- Routes 仅做 HTTP 适配；业务逻辑在 services。
- Epic 1 只依赖 P1/P2 **读 API**，不依赖前端。
- 写操作统一经 `kb_write_guard` + audit middleware。

## 5. 数据流

### 5.1 创建 KB（可选复制）

```text
POST /api/v1/kbs { name, clone_from_kb_id? }
  → kb_service.create
  → [optional] kb_clone_service:
       1. 读取源 KB 全部 Product Category（按 depth 排序）
       2. 建立 old_id → new_id 映射
       3. 插入副本（更新 parent_id、path）
       4. 同样处理 Chapter Taxonomy + synonyms
       5. 复制 binding 表（映射新 taxonomy_id / category_id）
  → classification_audit_log
  → 返回 { kb_id, trace_id }
```

### 5.2 创建产品分类

```text
POST /api/v1/kbs/{kb_id}/product-categories
  → kb_write_guard
  → alias_registry.check(category_name, aliases)
  → category_tree.assign_path(parent_id)
  → INSERT product_category + aliases
  → audit
```

### 5.3 合并分类

```text
POST .../product-categories/{id}/merge { target_category_id }
  → assert source.status ∉ { merged }
  → assert source has no active children        # D7
  → assert target not ancestor/descendant of source  # D8
  → BEGIN
       UPDATE classification_reference SET classification_id = target WHERE ...
       dedupe conflicts
       UPDATE source SET status=merged, merged_into_id=target
     COMMIT
  → audit (migrated_reference_count)
```

### 5.4 前端 KB 上下文

```text
KBSwitcher 变更 → KBContext.kb_id 更新 → 各中心 reload 树
inactive KB → 只读 banner + 禁用 POST/PATCH/PUT/merge 按钮
```

## 6. 数据模型补充（相对 data-model.md）

### 6.1 Knowledge Base 字段

| Field | Type | Notes |
|-------|------|-------|
| kb_id | UUID PK | |
| name | string(128) | NOT NULL |
| status | enum | `active`, `inactive` |
| created_at | timestamp | |
| updated_at | timestamp | |

Epic 0 不支持 KB 物理删除。

### 6.2 KB Clone 记录（可选）

`kb_clone_log`：`target_kb_id`, `source_kb_id`, `operator_id`, `trace_id`, `created_at`  
用于审计「从哪复制」，不保留运行时共享引用。

### 6.3 其余实体

Product Category、Chapter Taxonomy、Alias/Synonym、Binding、Classification Reference、
Audit Log 沿用 `specs/001-classification-base/data-model.md`，无结构变更。

## 7. API 契约补充

新增 **`contracts/knowledge-base-api.md`**（实现阶段创建）：

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/kbs` | 列表；`?status=active` 默认 |
| POST | `/api/v1/kbs` | 创建；body 含可选 `clone_from_kb_id` |
| GET | `/api/v1/kbs/{kb_id}` | 详情 |
| PATCH | `/api/v1/kbs/{kb_id}` | 改名 |
| POST | `/api/v1/kbs/{kb_id}/deactivate` | 停用 |

现有 `product-category-api.md`、`chapter-taxonomy-api.md` 路径不变；错误码补充：

| code | 场景 |
|------|------|
| `KB_READ_ONLY` | inactive KB 写操作 |
| `HAS_CHILDREN` | 合并时源节点仍有子节点 |
| `HAS_ACTIVE_CHILDREN` | 停用父节点时存在 active 子节点 |
| `ANCESTOR_RELATION` | 合并双方存在父子关系 |

## 8. 错误处理

- 统一 envelope：`{ data, trace_id }` / `{ error: { code, message, details }, trace_id }`
- 409 冲突类：返回 `details` 指明冲突别名归属或冲突节点 ID
- 前端：Toast 展示 message；表单字段级展示 details

## 9. 测试策略

| 切片 | 关键测试 |
|------|----------|
| P0 | KB CRUD；clone 后树/绑定结构同构且 ID 不同；inactive 403 |
| P1 | 三级树；别名全局唯一；search；sibling code 唯一 |
| P2 | 同义名唯一；M:N 绑定；按产品筛选 |
| P3 | impact 分组；merge 迁移；HAS_CHILDREN/ANCESTOR 拒绝；audit trace |

- 后端：pytest + httpx（`tests/contract/`, `tests/integration/`）
- 前端：Playwright 冒烟（KB 切换、P1 建树）
- 工具脚本：`seed_classification_references.py` 支撑 P3

## 10. 与 Spec Kit 制品同步项

实现前建议更新（`/speckit-tasks` 或手工）：

1. `plan.md` — 增加 P0 切片、KB API、`kb_clone_service`
2. `data-model.md` — KB status、kb_clone_log
3. `contracts/knowledge-base-api.md` — 新建
4. `quickstart.md` — 增加 P0 VS 场景（创建/复制/切换/停用）

`spec.md` 用户故事 P1–P3 不变；**P0 作为实现切片补充**，不修改产品需求优先级表述。

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| clone 大树超时 | 单事务 + 节点数上限提示（>2000 拒绝并建议分批） |
| inactive KB 误操作 | 停用前确认弹窗；UI 只读 banner |
| P3 无真实引用难验收 | seed 脚本注入 reference 行 |
| 前后端 kb_id 不一致 | KBContext 单源；API client 拦截器注入路径 |

## 12. 审批记录

| 阶段 | 状态 | 日期 |
|------|------|------|
| §1 架构与交付切片 | 已确认 | 2026-06-11 |
| §2 组件划分 | 已确认 | 2026-06-11 |
| §3 数据流/错误/测试 | 已确认 | 2026-06-11 |
| 设计文档书面审阅 | 待用户确认 | — |
