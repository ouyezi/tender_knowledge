# 分类 UX 修复与 Schema 漂移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复知识库创建时间缺失、分类归档语义不清、分类树子节点入口不可见、来源导入页 500 四个用户反馈问题。

**Architecture:** 后端在现有 `init_db` 启动钩子中补 PostgreSQL 列同步（`llm_progress`），扩展 KB API 序列化时间戳；前端在两个 TreePanel 增加可见子节点入口，在生命周期组件澄清归档/停用文案。不引入 Alembic，不重构共享组件。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL, pytest, httpx | TypeScript, React 18, Ant Design 5, Vite

**Design doc:** `docs/superpowers/specs/2026-06-12-classification-ux-fixes-design.md`

---

## File Map

| 路径 | 职责 | 操作 |
|------|------|------|
| `backend/src/db/init_db.py` | 启动时 PostgreSQL 列同步 | Modify |
| `backend/src/api/routes/knowledge_bases.py` | KB API 响应序列化 | Modify |
| `backend/tests/unit/test_init_db_schema_sync.py` | 列同步单元测试 | Create |
| `backend/tests/contract/test_knowledge_bases_api.py` | KB API 契约测试 | Modify |
| `frontend/src/components/ClassificationLifecycleActions.tsx` | 停用/归档文案 | Modify |
| `frontend/src/components/CategoryTreePanel.tsx` | 产品分类树子节点入口 | Modify |
| `frontend/src/components/TaxonomyTreePanel.tsx` | 章节类型树子节点入口 | Modify |
| `frontend/src/pages/ProductCategoryCenter/index.tsx` | 传递 selectedLabel / parentLabel | Modify |
| `frontend/src/pages/ChapterTaxonomyCenter/index.tsx` | 传递 selectedLabel / parentLabel | Modify |
| `frontend/src/components/CategoryDetailPanel.tsx` | 新建子分类标题 | Modify |
| `frontend/src/components/TaxonomyDetailPanel.tsx` | 新建子章节标题 | Modify |
| `specs/001-classification-base/contracts/knowledge-base-api.md` | API 契约文档 | Modify |

---

## Task 1: PostgreSQL 列同步 — `llm_progress`

**Files:**
- Modify: `backend/src/db/init_db.py`
- Create: `backend/tests/unit/test_init_db_schema_sync.py`

- [ ] **Step 1: 写失败测试 — `_sync_missing_columns` 执行 ALTER**

```python
# backend/tests/unit/test_init_db_schema_sync.py
from unittest.mock import MagicMock

from src.db.init_db import _sync_missing_columns


def test_sync_missing_columns_adds_llm_progress():
    conn = MagicMock()
    _sync_missing_columns(conn)
    conn.execute.assert_called_once()
    sql = str(conn.execute.call_args[0][0])
    assert "template_parse_tasks" in sql
    assert "llm_progress" in sql
    assert "IF NOT EXISTS" in sql
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_init_db_schema_sync.py::test_sync_missing_columns_adds_llm_progress -v`

Expected: FAIL — `ImportError: cannot import name '_sync_missing_columns'`

- [ ] **Step 3: 实现 `_sync_missing_columns` 并在 `init_db` 中调用**

```python
# backend/src/db/init_db.py — 在 _sync_postgres_enum 之后添加

def _sync_missing_columns(conn) -> None:
    conn.execute(
        text(
            "ALTER TABLE template_parse_tasks "
            "ADD COLUMN IF NOT EXISTS llm_progress JSONB"
        )
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        _sync_postgres_enum(
            conn,
            "referenceobjecttype",
            [member.value for member in ReferenceObjectType],
        )
        _sync_missing_columns(conn)
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_init_db_schema_sync.py -v`

Expected: PASS

- [ ] **Step 5: 手动验证 PostgreSQL 500 修复**

Run（需本地 PostgreSQL 与 backend 运行中）:

```bash
# 重启 backend 触发 init_db
cd backend && ../.venv/bin/python startup.py
# 另开终端
curl -s -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8000/api/v1/kbs/<kb_id>/file-imports?page=1&page_size=20" \
  -H "X-Operator-Id: admin"
curl -s -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8000/api/v1/kbs/<kb_id>/template-parse/tasks?page_size=200" \
  -H "X-Operator-Id: admin"
```

Expected: 两个请求均返回 `200`

- [ ] **Step 6: Commit**

```bash
git add backend/src/db/init_db.py backend/tests/unit/test_init_db_schema_sync.py
git commit -m "fix: sync llm_progress column on postgres startup"
```

---

## Task 2: 知识库 API 返回 `created_at` / `updated_at`

**Files:**
- Modify: `backend/src/api/routes/knowledge_bases.py:27-32`
- Modify: `backend/tests/contract/test_knowledge_bases_api.py`
- Modify: `specs/001-classification-base/contracts/knowledge-base-api.md`

- [ ] **Step 1: 写失败测试 — 创建 KB 响应含时间戳**

在 `backend/tests/contract/test_knowledge_bases_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_create_kb_includes_timestamps(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-Timestamp"},
            headers={"X-Operator-Id": "admin"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert "T" in data["created_at"]

        list_response = await client.get("/api/v1/kbs?status=active")
        item = list_response.json()["data"]["items"][0]
        assert item["created_at"] is not None
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_knowledge_bases_api.py::test_create_kb_includes_timestamps -v`

Expected: FAIL — `KeyError: 'created_at'`

- [ ] **Step 3: 扩展 `_kb_dict`**

```python
# backend/src/api/routes/knowledge_bases.py

def _kb_dict(kb: KnowledgeBase) -> dict:
    return {
        "kb_id": str(kb.kb_id),
        "name": kb.name,
        "status": kb.status.value,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_knowledge_bases_api.py -v`

Expected: 全部 PASS

- [ ] **Step 5: 更新 API 契约文档**

`specs/001-classification-base/contracts/knowledge-base-api.md` — GET `/` 响应示例改为：

```json
{
  "items": [
    {
      "kb_id": "uuid",
      "name": "标书知识库-demo",
      "status": "active",
      "created_at": "2026-06-12T10:00:00+00:00",
      "updated_at": "2026-06-12T10:00:00+00:00"
    }
  ]
}
```

POST `/` 与 GET `/{kb_id}` 的 Response `data` 说明同步加入 `created_at`、`updated_at`。

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/routes/knowledge_bases.py \
  backend/tests/contract/test_knowledge_bases_api.py \
  specs/001-classification-base/contracts/knowledge-base-api.md
git commit -m "feat: expose knowledge base created_at in API"
```

---

## Task 3: 生命周期文案 — 归档 ≠ 删除

**Files:**
- Modify: `frontend/src/components/ClassificationLifecycleActions.tsx`

- [ ] **Step 1: 更新 Popconfirm 文案与 Tooltip**

```tsx
// frontend/src/components/ClassificationLifecycleActions.tsx
import { Button, Popconfirm, Space, Tooltip } from "antd";

// ... existing props ...

      <Popconfirm
        title="停用后该分类不可被新对象选用，已有引用保留。确认停用？"
        onConfirm={onDeactivate}
        disabled={disabled || status !== "active"}
      >
        <Button danger disabled={disabled || status !== "active"}>
          停用
        </Button>
      </Popconfirm>
      <Popconfirm
        title="归档不会删除数据，仅标记为历史分类，默认列表中隐藏。确认归档？"
        onConfirm={onArchive}
        disabled={disabled || status === "archived"}
      >
        <Tooltip title="归档 ≠ 删除，数据仍保留">
          <Button disabled={disabled || status === "archived"}>
            归档
          </Button>
        </Tooltip>
      </Popconfirm>
```

- [ ] **Step 2: 手动验证**

1. 打开产品分类中心，选中任一 active 分类
2. 点击「归档」→ 确认弹窗文案含「不会删除数据」
3. 鼠标悬停归档按钮 → tooltip 显示「归档 ≠ 删除，数据仍保留」
4. 章节类型中心重复上述步骤

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ClassificationLifecycleActions.tsx
git commit -m "fix: clarify archive is not delete in lifecycle actions"
```

---

## Task 4: 产品分类树 — 可见子节点入口

**Files:**
- Modify: `frontend/src/components/CategoryTreePanel.tsx`
- Modify: `frontend/src/pages/ProductCategoryCenter/index.tsx`
- Modify: `frontend/src/components/CategoryDetailPanel.tsx`

- [ ] **Step 1: 扩展 `CategoryTreePanel` props 与 UI**

```tsx
// frontend/src/components/CategoryTreePanel.tsx
import { Button, Card, Space, Tree, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";

interface CategoryTreePanelProps {
  nodes: ProductCategoryNode[];
  selectedId?: string;
  selectedLabel?: string;
  readOnly?: boolean;
  loading?: boolean;
  onSelect: (categoryId: string) => void;
  onCreateRoot: () => void;
  onCreateChild: (parentId: string) => void;
}

// titleRender 改为：
        titleRender={(node) => (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span
              onDoubleClick={(event) => {
                event.stopPropagation();
                if (!readOnly && typeof node.key === "string") {
                  onCreateChild(node.key);
                }
              }}
            >
              {node.title as string}
            </span>
            {!readOnly && typeof node.key === "string" ? (
              <Button
                type="text"
                size="small"
                icon={<PlusOutlined />}
                aria-label="添加子分类"
                onClick={(event) => {
                  event.stopPropagation();
                  onCreateChild(node.key as string);
                }}
              />
            ) : null}
          </div>
        )}

// Card extra 改为 Space：
      extra={
        <Space>
          {selectedId && !readOnly ? (
            <Button onClick={() => onCreateChild(selectedId)}>添加子分类</Button>
          ) : null}
          <Button type="primary" disabled={readOnly} onClick={onCreateRoot}>
            新建分类
          </Button>
        </Space>
      }

// Tree 下方追加：
      <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
        选中节点后点击 + 或双击节点，可添加子分类
      </Typography.Text>
```

- [ ] **Step 2: 父组件传入 `selectedLabel`**

```tsx
// frontend/src/pages/ProductCategoryCenter/index.tsx

// 在 treeOptions useMemo 之后添加：
  const selectedCategoryLabel = useMemo(() => {
    if (editor.kind === "existing") {
      return detail?.category_name;
    }
    if (editor.kind === "new" && editor.parentId) {
      return treeOptions.find((opt) => opt.value === editor.parentId)?.label;
    }
    return undefined;
  }, [detail, editor, treeOptions]);

// CategoryTreePanel 增加 prop：
        <CategoryTreePanel
          nodes={nodes}
          selectedId={editor.kind === "existing" ? editor.categoryId : undefined}
          selectedLabel={selectedCategoryLabel}
          ...
        />

// CategoryDetailPanel 增加 prop：
        <CategoryDetailPanel
          ...
          isNew={editor.kind === "new"}
          parentLabel={
            editor.kind === "new" && editor.parentId ? selectedCategoryLabel : undefined
          }
        />
```

- [ ] **Step 3: 详情面板标题显示父节点名**

```tsx
// frontend/src/components/CategoryDetailPanel.tsx
interface CategoryDetailPanelProps {
  ...
  parentLabel?: string;
}

// Card title:
      title={
        isNew
          ? parentLabel
            ? `新建子分类（父：${parentLabel}）`
            : "新建分类"
          : "分类详情"
      }
```

- [ ] **Step 4: 手动验证**

1. 产品分类中心 → 选中已有分类 → 点击「添加子分类」或节点 `+`
2. 右侧标题显示「新建子分类（父：xxx）」
3. 保存后子节点出现在树中

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CategoryTreePanel.tsx \
  frontend/src/pages/ProductCategoryCenter/index.tsx \
  frontend/src/components/CategoryDetailPanel.tsx
git commit -m "fix: add visible child category entry points in product tree"
```

---

## Task 5: 章节类型树 — 同步子节点入口

**Files:**
- Modify: `frontend/src/components/TaxonomyTreePanel.tsx`
- Modify: `frontend/src/pages/ChapterTaxonomyCenter/index.tsx`
- Modify: `frontend/src/components/TaxonomyDetailPanel.tsx`

- [ ] **Step 1: 扩展 `TaxonomyTreePanel`（与 Task 4 同模式）**

复制 Task 4 的 TreePanel 改动到 `TaxonomyTreePanel.tsx`，文案替换为：

- 按钮：`添加子章节类型`
- 提示：`选中节点后点击 + 或双击节点，可添加子章节类型`
- `aria-label="添加子章节类型"`

- [ ] **Step 2: 更新 `ChapterTaxonomyCenter/index.tsx`**

与 Task 4 相同模式，添加 `selectedTaxonomyLabel` computed value，传给 `TaxonomyTreePanel` 与 `TaxonomyDetailPanel` 的 `parentLabel`。

- [ ] **Step 3: 更新 `TaxonomyDetailPanel.tsx` 标题**

```tsx
      title={
        isNew
          ? parentLabel
            ? `新建子章节类型（父：${parentLabel}）`
            : "新建章节类型"
          : "章节类型详情"
      }
```

- [ ] **Step 4: 手动验证**

章节类型中心重复 Task 4 验证步骤。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TaxonomyTreePanel.tsx \
  frontend/src/pages/ChapterTaxonomyCenter/index.tsx \
  frontend/src/components/TaxonomyDetailPanel.tsx
git commit -m "fix: add visible child taxonomy entry points in chapter tree"
```

---

## Task 6: 回归测试与端到端验证

**Files:** （无新文件）

- [ ] **Step 1: 运行后端全量契约测试**

Run: `cd backend && ../.venv/bin/pytest tests/contract/ -v`

Expected: 全部 PASS

- [ ] **Step 2: 运行相关集成测试**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_template_model.py tests/integration/test_template_parse_runner.py -v`

Expected: PASS（确认 `llm_progress` 列读写正常）

- [ ] **Step 3: 前端 TypeScript 编译检查**

Run: `cd frontend && npm run build`

Expected: 编译成功，无 TS 错误

- [ ] **Step 4: 四条用户路径手动验收**

| # | 路径 | 预期 |
|---|------|------|
| 1 | 知识库列表 | 「创建时间」列显示本地化时间，非 `-` |
| 2 | 产品分类 → 归档 | 弹窗说明不删除；tooltip 正确 |
| 3 | 产品分类 / 章节类型 → 添加子节点 | `+` 按钮、extra 按钮、双击均可用 |
| 4 | 来源导入页 | 打开无 500；列表正常渲染 |

- [ ] **Step 5: Commit（如有测试修复）**

```bash
git add -A
git commit -m "test: regression for classification ux fixes"
```

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| `init_db` 列同步 `llm_progress` | Task 1 |
| KB API 返回 `created_at` / `updated_at` | Task 2 |
| API 契约文档更新 | Task 2 |
| 归档/停用 Popconfirm 文案 | Task 3 |
| `CategoryTreePanel` 子节点入口 | Task 4 |
| `TaxonomyTreePanel` 子节点入口 | Task 5 |
| 来源导入页 500 修复（列同步后自动） | Task 1 + Task 6 |
| 知识库列表前端（已有列，API 补字段即可） | Task 2 |

## Risks & Notes

- Task 1 Step 5 需重启 backend 才会执行 `init_db`；开发环境若用 `--reload`，改 `init_db.py` 后自动重载即可。
- `@ant-design/icons` 已在项目中使用；若 `PlusOutlined` import 报错，检查 `frontend/package.json` 是否含 `@ant-design/icons`（Epic 0 前端已依赖 Ant Design，通常已安装）。
- `Tooltip` 包裹 `Button` 时需确保 disabled 状态下 tooltip 仍可见 — 若 Ant Design 5 行为异常，改用 `<span><Button .../></span>` 包裹。
