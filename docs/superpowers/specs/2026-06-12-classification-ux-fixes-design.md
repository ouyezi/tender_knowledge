# Design: 分类底座 UX 修复与 Schema 漂移

**Date**: 2026-06-12  
**Status**: Approved (design review)  
**Scope**: Epic 0 分类 UX + Epic 1/2 来源导入 500 修复

## Background

用户反馈四个问题：

1. 知识库列表「创建时间」列始终显示 `-`
2. 分类「归档」是否等于删除 — 语义不清
3. 无法发现「添加子分类」入口 — 分类树名不副实
4. 来源导入页一打开即 500 — `file-imports` 与 `template-parse/tasks` 均失败

## Root Cause Analysis

| 问题 | 根因 |
|------|------|
| 创建时间 | DB 有 `created_at`，API `_kb_dict` 未序列化该字段 |
| 归档语义 | 功能正确（软状态 `archived`），UI 未解释与删除的区别 |
| 子分类 | 后端与页面逻辑支持 `parent_id`；前端仅双击树节点触发，无可见入口 |
| 导入 500 | ORM 新增 `template_parse_tasks.llm_progress`，现有 PostgreSQL 表未迁移；`create_all` 不 ALTER 已有表 |

500 错误栈：

```
psycopg.errors.UndefinedColumn: column template_parse_tasks.llm_progress does not exist
```

`list_file_imports` 联查 `TemplateParseTask` 取 `parse_status` 时触发；`list_parse_tasks` 直接查询同表。

## Goals

- 知识库列表正确展示创建时间
- 分类生命周期操作语义对用户清晰（归档 ≠ 删除）
- 产品分类树与章节类型树均可直观添加子节点
- 来源导入页与模板解析任务列表 API 在已有 DB 上返回 200

## Non-Goals

- Alembic 完整迁移体系（后续独立任务）
- 分类从 inactive/archived 恢复为 active 的管理 UI
- 分类树组件抽象重构（共享 `ClassificationTreePanel`）
- 来源导入页请求失败时的细粒度降级（列修复后不应再 500）

## Approach

**选定方案：最小修复包（方案 A）**

- `init_db` 列同步补 `llm_progress`（与现有 `_sync_postgres_enum` 模式一致）
- API 补 `created_at` / `updated_at`
- 两个 TreePanel 增加可见子节点入口与操作提示
- 生命周期按钮 Popconfirm 文案澄清

## Backend Changes

### 1. Schema 漂移修复 — `init_db.py`

新增 `_sync_missing_columns(conn)`，在 PostgreSQL 启动时执行：

```sql
ALTER TABLE template_parse_tasks
  ADD COLUMN IF NOT EXISTS llm_progress JSONB;
```

- 仅在 `engine.dialect.name == "postgresql"` 时运行
- SQLite 测试环境由 `create_all` 建完整表，无需 ALTER
- 幂等：`IF NOT EXISTS` 可重复执行

### 2. 知识库 API — `knowledge_bases.py`

扩展 `_kb_dict`：

```python
{
    "kb_id": str(kb.kb_id),
    "name": kb.name,
    "status": kb.status.value,
    "created_at": kb.created_at.isoformat() if kb.created_at else None,
    "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
}
```

影响端点：`POST /`、`GET /`、`GET /{kb_id}`、`PATCH /{kb_id}`、`POST /{kb_id}/deactivate`。

### 3. API Contract 更新

更新 `specs/001-classification-base/contracts/knowledge-base-api.md` 响应示例，加入 `created_at`、`updated_at`。

## Frontend Changes

### 1. 分类树 — 子分类入口

**文件**: `CategoryTreePanel.tsx`、`TaxonomyTreePanel.tsx`

| 改动 | 说明 |
|------|------|
| 节点 `titleRender` | 节点名右侧增加小号 `+` 按钮；`readOnly` 时隐藏 |
| 卡片 `extra` | 已选中节点时显示「添加子分类」按钮 |
| 卡片底部 | 灰色提示：「选中节点后点击 + 或双击节点，可添加子分类」 |
| 保留双击 | 不破坏已有交互 |

**可选增强**（父组件传入 `parentLabel`）：新建时详情面板标题显示「新建子分类（父：xxx）」。

产品分类中心与章节类型中心同步应用。

### 2. 生命周期语义 — `ClassificationLifecycleActions.tsx`

| 操作 | Popconfirm 标题 |
|------|-----------------|
| 停用 | 「停用后该分类不可被新对象选用，已有引用保留。确认停用？」 |
| 归档 | 「归档不会删除数据，仅标记为历史分类，默认列表中隐藏。确认归档？」 |

归档按钮增加 `Tooltip`：「归档 ≠ 删除，数据仍保留」。

### 3. 知识库列表

`KnowledgeBaseList/index.tsx` 已有 `created_at` 列与 `toLocaleString` 渲染，API 补字段后自动生效，无需改前端。

### 4. 来源导入页

后端列同步完成后，`FileImportCenter` 现有 `Promise.all([listFileImports, listParseTasks])` 应恢复正常，无需改请求逻辑。

## Data Flow (After Fix)

```text
打开来源导入页
  ├─ GET file-imports → file_imports 表
  └─ GET template-parse/tasks → template_parse_tasks（含 llm_progress）
       └─ 渲染 parse_status / 重试链接
```

## Classification Lifecycle Reference

规格定义（`specs/001-classification-base/data-model.md`）：

```text
active ──→ inactive ──→ archived
   │           │
   └─ merge ───┴─→ merged (terminal)
```

- 物理 DELETE 禁止
- `archived` 为软状态，数据保留，默认列表排除
- `inactive` 与 `archived` 可恢复为 `active`（未 merged 时；恢复 UI 不在本次范围）

## Testing

| 类型 | 内容 |
|------|------|
| 契约 | KB list/detail 响应含 ISO8601 `created_at` |
| 集成 | 模拟旧 schema（无 `llm_progress`）执行 `init_db` 后，`file-imports` 与 `template-parse/tasks` 返回 200 |
| 手动 | KB 列表显示创建时间；分类/章节树可点 + 建子节点；归档弹窗文案正确；来源导入页加载无 500 |

## Implementation Order

1. `init_db` 列同步（解除 500 阻塞）
2. KB API 补时间戳字段
3. `ClassificationLifecycleActions` 文案
4. `CategoryTreePanel` + `TaxonomyTreePanel` 子节点入口
5. 契约文档与测试
6. 手动验证四条用户路径

## Risks

| 风险 | 缓解 |
|------|------|
| 未来还有更多列漂移 | 后续补 Alembic baseline；`init_db` 列同步仅作过渡 |
| 树节点 + 按钮点击冒泡 | `stopPropagation` 于 + 按钮 click |
| 仅 PostgreSQL 列同步 | 与项目默认 DATABASE_URL 一致；SQLite 测试不受影响 |
