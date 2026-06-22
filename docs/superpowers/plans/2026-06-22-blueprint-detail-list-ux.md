# Blueprint Detail Tree & List Layout UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复目录蓝图详情页只读树「点击复制拦截选中」导致节点详情（含应标提示）不可达的问题，并优化蓝图列表页名称列固定宽度与标签/版本列紧凑展示。

**Architecture:** 纯前端改动两处：`BlueprintOutlineTreeReadonly` 将复制从标题点击拆到旁侧图标，恢复 Tree 默认选中；`BlueprintListPage` 调整列 `width`/`ellipsis`/`Tag size`。无后端变更。

**Tech Stack:** React 18, TypeScript, Ant Design 5, vitest, @testing-library/react

**Design spec:** `docs/superpowers/specs/2026-06-22-blueprint-detail-list-ux-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.tsx` | 只读目录树：选中 + 图标复制 |
| `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.test.tsx` | 树交互单元测试（新建） |
| `frontend/src/pages/Knowledge/BlueprintListPage.tsx` | 列表列宽与 Tag 尺寸 |

---

## Task 1: 修复只读目录树选中与复制

**Files:**
- Modify: `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.tsx`
- Create: `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import BlueprintOutlineTreeReadonly from "./BlueprintOutlineTreeReadonly";
import type { BlueprintNode } from "../../services/blueprints";

const nodes: BlueprintNode[] = [
  {
    node_title: "技术方案",
    node_level: 1,
    importance_level: "required",
    content_description: "写架构设计",
    tender_response_hint: "响应评分点",
    children: [],
  },
];

describe("BlueprintOutlineTreeReadonly", () => {
  it("selects node when clicking tree title", async () => {
    const user = userEvent.setup();
    const onSelectNode = vi.fn();
    render(
      <BlueprintOutlineTreeReadonly nodes={nodes} onSelectNode={onSelectNode} />,
    );
    await user.click(screen.getByText(/技术方案/));
    expect(onSelectNode).toHaveBeenCalledWith("0");
  });

  it("copies title via copy icon without changing selection callback order", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const onSelectNode = vi.fn();
    render(
      <BlueprintOutlineTreeReadonly nodes={nodes} onSelectNode={onSelectNode} />,
    );
    await user.click(screen.getByRole("button", { name: "复制章节标题" }));
    expect(writeText).toHaveBeenCalledWith("技术方案");
    expect(onSelectNode).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/components/Blueprint/BlueprintOutlineTreeReadonly.test.tsx`

Expected: FAIL — 第一个用例 `onSelectNode` 未被调用（标题点击仍 stopPropagation）；第二个用例找不到 `复制章节标题` 按钮。

- [ ] **Step 3: Implement tree interaction fix**

Replace `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.tsx` title block:

```tsx
import { CopyOutlined } from "@ant-design/icons";
import { Tree, Tooltip, message } from "antd";
import type { DataNode } from "antd/es/tree";
import type { BlueprintNode } from "../../services/blueprints";
import { getImportanceLevelLabel } from "../../constants/blueprintMeta";

// ... interface unchanged ...

function copyTitle(title: string) {
  void navigator.clipboard
    .writeText(title)
    .then(() => message.success("章节标题已复制"))
    .catch(() => message.error("复制失败，请手动复制"));
}

function toTreeData(nodes: BlueprintNode[], parentPath = ""): DataNode[] {
  return nodes.map((node, index) => {
    const path = parentPath ? `${parentPath}-${index}` : String(index);
    const title = node.node_title?.trim() || "(未命名章节)";
    return {
      key: path,
      title: (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span>
            {title}（{getImportanceLevelLabel(node.importance_level)}）
          </span>
          <Tooltip title="复制章节标题">
            <CopyOutlined
              role="button"
              aria-label="复制章节标题"
              tabIndex={0}
              style={{ color: "rgba(0,0,0,0.45)", fontSize: 12 }}
              onClick={(event) => {
                event.stopPropagation();
                copyTitle(title);
              }}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") {
                  return;
                }
                event.preventDefault();
                event.stopPropagation();
                copyTitle(title);
              }}
            />
          </Tooltip>
        </span>
      ),
      children: toTreeData(node.children ?? [], path),
    };
  });
}

// ... component export unchanged ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/components/Blueprint/BlueprintOutlineTreeReadonly.test.tsx`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.tsx \
        frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.test.tsx
git commit -m "fix: restore blueprint readonly tree selection and add copy icon"
```

---

## Task 2: 优化蓝图列表列宽

**Files:**
- Modify: `frontend/src/pages/Knowledge/BlueprintListPage.tsx`

- [ ] **Step 1: Update imports**

在文件顶部 antd import 中增加 `Tooltip`：

```tsx
import { Alert, Button, Card, Form, Input, Popconfirm, Select, Space, Table, Tag, Tooltip, message } from "antd";
```

- [ ] **Step 2: Shrink tag helper**

```tsx
function renderTags(tags?: string[]) {
  if (!tags?.length) {
    return "-";
  }
  return (
    <Space size={[4, 4]} wrap>
      {tags.map((tag) => (
        <Tag key={tag} size="small">
          {tag}
        </Tag>
      ))}
    </Space>
  );
}
```

- [ ] **Step 3: Update column definitions**

替换 `columns` 数组中相关列：

```tsx
{
  title: "蓝图名称",
  dataIndex: "name",
  key: "name",
  width: 260,
  ellipsis: true,
  render: (_value, record) => (
    <Tooltip title={record.name || "-"}>
      <Button
        type="link"
        size="small"
        style={{
          maxWidth: "100%",
          padding: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          display: "inline-block",
          verticalAlign: "bottom",
        }}
        onClick={() => navigate(`/knowledge/blueprints/${record.blueprint_id}`)}
      >
        {record.name || "-"}
      </Button>
    </Tooltip>
  ),
},
{
  title: "来源章节",
  dataIndex: "source_chapter_title",
  key: "source_chapter_title",
  width: 180,
  ellipsis: true,
  render: (value: string | null) => value || "-",
},
{
  title: "产品标签",
  dataIndex: "product_tags",
  key: "product_tags",
  width: 140,
  render: (value: string[]) => renderTags(value),
},
{
  title: "行业标签",
  dataIndex: "industry_tags",
  key: "industry_tags",
  width: 140,
  render: (value: string[]) => renderTags(value),
},
{
  title: "场景标签",
  dataIndex: "scenario_tags",
  key: "scenario_tags",
  width: 140,
  render: (value: string[]) => renderTags(value),
},
{
  title: "状态",
  dataIndex: "status",
  key: "status",
  width: 80,
  render: (value: string) => <Tag size="small">{value || "-"}</Tag>,
},
{
  title: "版本",
  dataIndex: "version",
  key: "version",
  width: 64,
  align: "center",
},
```

- [ ] **Step 4: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS，无 TypeScript 错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Knowledge/BlueprintListPage.tsx
git commit -m "fix: tighten blueprint list column widths and tag sizing"
```

---

## Task 3: 回归验证

**Files:** none（验证任务）

- [ ] **Step 1: Run frontend tests**

Run: `cd frontend && npm test`

Expected: PASS（含新建的 `BlueprintOutlineTreeReadonly.test.tsx`）

- [ ] **Step 2: Manual smoke（design spec §5.1）**

1. 蓝图详情页（只读）→ 点击目录树节点 → 右侧出现「内容描述」「应标/得分/应答提示」
2. 点击复制图标 → Toast「章节标题已复制」，节点保持选中
3. 蓝图列表页 → 名称列约 260px、标签列更窄、版本列紧凑

---

## Spec Coverage Self-Review

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 单击节点选中，右侧展示节点详情 | Task 1 |
| 复制改为旁侧图标 + Tooltip/aria-label | Task 1 |
| 名称列 width 260 + ellipsis + Tooltip | Task 2 |
| 标签列 140 + Tag small | Task 2 |
| 版本列 64 居中 | Task 2 |
| 来源章节 180 | Task 2 |
| 手工 Smoke | Task 3 |
| 不含后端变更 | ✓ 无 backend 任务 |
| 不含默认选中首节点 | ✓ 未列入 |
