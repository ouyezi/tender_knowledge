# 目录节点内容查看（Drawer）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在目录详情页目录树节点悬停时显示「查看内容」，点击后在右侧 Drawer 拼接展示该节点及全部子孙目录的正文（含节标题）。

**Architecture:** 后端新增 `outline_node_content_service` 对 outline 子树前序遍历，逐节点复用 `build_section_content` 聚合 `blocks_v1`；暴露 `GET .../nodes/{id}/content`；前端 `OutlineNodeContentDrawer` 用 `RichContentViewer` 渲染各节，`OutlineTreeEditor` 增加 hover 按钮。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 | React 18, Ant Design 5, Vite, Vitest | pytest

**Design doc:** `docs/superpowers/specs/2026-06-16-outline-node-content-view-design.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/src/services/outline_node_content_service.py` | 子树遍历 + 逐节 `build_section_content` |
| `backend/src/api/routes/bid_outlines.py` | 注册 GET content 路由 |
| `backend/tests/unit/test_outline_node_content_service.py` | 服务层单测 |
| `backend/tests/contract/test_bid_outline_node_content.py` | HTTP 契约测试 |
| `frontend/src/services/bidOutlines.ts` | `getOutlineNodeContent` API client |
| `frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.tsx` | 内容 Drawer |
| `frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.test.tsx` | Drawer 单测 |
| `frontend/src/pages/OutlineCenter/OutlineTreeEditor.tsx` | hover「查看内容」按钮 |
| `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx` | 挂载 Drawer、传 callback |

---

## Task 1: `outline_node_content_service` 服务层

**Files:**
- Create: `backend/src/services/outline_node_content_service.py`
- Create: `backend/tests/unit/test_outline_node_content_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_outline_node_content_service.py
from uuid import uuid4

import pytest

from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.content_blocks import parse_content
from src.services.outline_node_content_service import (
    OutlineNodeNotFoundError,
    OutlineNotFoundError,
    build_outline_subtree_content,
)


def _seed_outline_tree(db_session, kb_id):
    file_import = FileImport(
        kb_id=kb_id,
        file_name="content.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{kb_id}/content.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="content.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="测试目录",
        created_by="admin",
    )
    db_session.add(outline)
    db_session.flush()

    h1_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="父章节",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    p1_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=1,
        content_preview="父正文",
        tree_version=1,
    )
    h2_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="子章节",
        level=2,
        sort_order=2,
        tree_version=1,
    )
    p2_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=3,
        content_preview="子正文",
        tree_version=1,
    )
    db_session.add_all([h1_tree, p1_tree, h2_tree, p2_tree])
    db_session.flush()

    parent = BidOutlineNode(
        kb_id=kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="父目录",
        level=1,
        sort_order=0,
        source_node_id=h1_tree.node_id,
    )
    child = BidOutlineNode(
        kb_id=kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=parent.outline_node_id,
        title="子目录",
        level=2,
        sort_order=0,
        source_node_id=h2_tree.node_id,
    )
    no_source = BidOutlineNode(
        kb_id=kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=parent.outline_node_id,
        title="无源节点",
        level=2,
        sort_order=1,
        source_node_id=None,
    )
    db_session.add_all([parent, child, no_source])
    db_session.commit()
    return outline, document, parent, child, no_source


def test_build_outline_subtree_content_parent_includes_descendants(db_session, seeded_kb):
    outline, _, parent, child, no_source = _seed_outline_tree(db_session, seeded_kb.kb_id)

    result = build_outline_subtree_content(
        db_session,
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        outline_node_id=parent.outline_node_id,
    )

    assert result["outline_node_id"] == str(parent.outline_node_id)
    assert result["title"] == "父目录"
    assert len(result["sections"]) == 3
    assert [s["title"] for s in result["sections"]] == ["父目录", "子目录", "无源节点"]

    parent_section = result["sections"][0]
    child_section = result["sections"][1]
    no_source_section = result["sections"][2]

    parent_doc = parse_content(parent_section["content"])
    assert [b.get("text") for b in parent_doc.blocks if b.get("type") == "paragraph"] == ["父正文"]
    assert parent_section["has_content"] is True

    child_doc = parse_content(child_section["content"])
    assert [b.get("text") for b in child_doc.blocks if b.get("type") == "paragraph"] == ["子正文"]
    assert child_section["has_content"] is True

    assert no_source_section["has_content"] is False
    assert no_source_section["empty_reason"] == "no_source_node"


def test_build_outline_subtree_content_leaf_only_self(db_session, seeded_kb):
    outline, _, parent, child, _ = _seed_outline_tree(db_session, seeded_kb.kb_id)

    result = build_outline_subtree_content(
        db_session,
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        outline_node_id=child.outline_node_id,
    )

    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "子目录"


def test_build_outline_subtree_content_empty_body(db_session, seeded_kb):
    outline, document, parent, _, _ = _seed_outline_tree(db_session, seeded_kb.kb_id)
    empty_heading = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="空节",
        level=1,
        sort_order=10,
        tree_version=1,
    )
    db_session.add(empty_heading)
    parent.source_node_id = empty_heading.node_id
    db_session.commit()

    result = build_outline_subtree_content(
        db_session,
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        outline_node_id=parent.outline_node_id,
    )

    assert result["sections"][0]["has_content"] is False
    assert result["sections"][0]["empty_reason"] == "empty_body"


def test_build_outline_subtree_content_outline_not_found(db_session, seeded_kb):
    with pytest.raises(OutlineNotFoundError):
        build_outline_subtree_content(
            db_session,
            kb_id=seeded_kb.kb_id,
            bid_outline_id=uuid4(),
            outline_node_id=uuid4(),
        )


def test_build_outline_subtree_content_node_not_found(db_session, seeded_kb):
    outline, _, _, _, _ = _seed_outline_tree(db_session, seeded_kb.kb_id)
    with pytest.raises(OutlineNodeNotFoundError):
        build_outline_subtree_content(
            db_session,
            kb_id=seeded_kb.kb_id,
            bid_outline_id=outline.bid_outline_id,
            outline_node_id=uuid4(),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/unit/test_outline_node_content_service.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.outline_node_content_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/outline_node_content_service.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.services.content_blocks import blocks_v1, parse_content
from src.services.section_content_builder import build_section_content


class OutlineNotFoundError(Exception):
    pass


class OutlineNodeNotFoundError(Exception):
    pass


def _collect_subtree_ids(
    nodes_by_id: dict[UUID, BidOutlineNode],
    children_by_parent: dict[UUID | None, list[BidOutlineNode]],
    root_id: UUID,
) -> list[UUID]:
    ordered: list[UUID] = []

    def walk(node_id: UUID) -> None:
        ordered.append(node_id)
        for child in children_by_parent.get(node_id, []):
            walk(child.outline_node_id)

    walk(root_id)
    return ordered


def _serialize_section(node: BidOutlineNode, *, document_id: UUID, db: Session) -> dict[str, Any]:
    if node.source_node_id is None:
        content = blocks_v1([])
        return {
            "outline_node_id": str(node.outline_node_id),
            "title": node.title,
            "level": node.level,
            "sort_order": node.sort_order,
            "source_node_id": None,
            "content": content,
            "has_content": False,
            "empty_reason": "no_source_node",
        }

    content = build_section_content(
        db,
        document_id=document_id,
        heading_node_id=node.source_node_id,
    )
    parsed = parse_content(content)
    has_content = len(parsed.blocks) > 0
    return {
        "outline_node_id": str(node.outline_node_id),
        "title": node.title,
        "level": node.level,
        "sort_order": node.sort_order,
        "source_node_id": str(node.source_node_id),
        "content": content,
        "has_content": has_content,
        "empty_reason": None if has_content else "empty_body",
    }


def build_outline_subtree_content(
    db: Session,
    *,
    kb_id: UUID,
    bid_outline_id: UUID,
    outline_node_id: UUID,
) -> dict[str, Any]:
    outline = (
        db.query(BidOutline)
        .filter(BidOutline.kb_id == kb_id, BidOutline.bid_outline_id == bid_outline_id)
        .one_or_none()
    )
    if outline is None:
        raise OutlineNotFoundError

    nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
        )
        .order_by(
            BidOutlineNode.level.asc(),
            BidOutlineNode.sort_order.asc(),
            BidOutlineNode.created_at.asc(),
        )
        .all()
    )
    nodes_by_id = {node.outline_node_id: node for node in nodes}
    if outline_node_id not in nodes_by_id:
        raise OutlineNodeNotFoundError

    children_by_parent: dict[UUID | None, list[BidOutlineNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)
    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.sort_order, item.created_at))

    subtree_ids = _collect_subtree_ids(nodes_by_id, children_by_parent, outline_node_id)
    root = nodes_by_id[outline_node_id]
    sections = [
        _serialize_section(nodes_by_id[node_id], document_id=outline.source_doc_id, db=db)
        for node_id in subtree_ids
    ]

    return {
        "outline_node_id": str(root.outline_node_id),
        "title": root.title,
        "bid_outline_id": str(outline.bid_outline_id),
        "source_doc_id": str(outline.source_doc_id),
        "sections": sections,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/unit/test_outline_node_content_service.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/outline_node_content_service.py backend/tests/unit/test_outline_node_content_service.py
git commit -m "feat: add outline subtree content aggregation service"
```

---

## Task 2: API 路由与契约测试

**Files:**
- Modify: `backend/src/api/routes/bid_outlines.py`（在 `get_bid_outline_nodes` 之后添加 handler）
- Create: `backend/tests/contract/test_bid_outline_node_content.py`

- [ ] **Step 1: Write the failing contract test**

```python
# backend/tests/contract/test_bid_outline_node_content.py
from src.services.content_blocks import parse_content
from tests.contract.test_bid_outline_nodes import _seed_outline_with_nodes


def test_get_outline_node_content(client, db_session, seeded_kb):
    outline, root_a, _, root_c, child_c, source_tree_node = _seed_outline_with_nodes(
        db_session, seeded_kb
    )

    paragraph = __import__("src.models.document_tree_node", fromlist=["DocumentTreeNode"]).DocumentTreeNode
    from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType

    doc = outline.source_doc_id
    p = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=doc,
        parent_id=None,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=1,
        content_preview="第一章正文",
        tree_version=1,
    )
    db_session.add(p)
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes/{root_c.outline_node_id}/content",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["outline_node_id"] == str(root_c.outline_node_id)
    assert data["title"] == "第三章"
    assert len(data["sections"]) == 2
    assert data["sections"][0]["title"] == "第三章"
    assert data["sections"][1]["title"] == "第三章-子章节"


def test_get_outline_node_content_not_found(client, db_session, seeded_kb):
    from uuid import uuid4

    outline, root_a, _, _, _, _ = _seed_outline_with_nodes(db_session, seeded_kb)
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes/{uuid4()}/content",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "OUTLINE_NODE_NOT_FOUND"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/contract/test_bid_outline_node_content.py -v`

Expected: FAIL with 404 route not found or 405

- [ ] **Step 3: Add route handler**

在 `backend/src/api/routes/bid_outlines.py` 顶部增加 import：

```python
from src.services.outline_node_content_service import (
    OutlineNodeNotFoundError,
    OutlineNotFoundError,
    build_outline_subtree_content,
)
```

在 `@router.get("/{bid_outline_id}/nodes")` 之后添加：

```python
@router.get("/{bid_outline_id}/nodes/{outline_node_id}/content")
def get_bid_outline_node_content(
    kb_id: UUID,
    bid_outline_id: UUID,
    outline_node_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        payload = build_outline_subtree_content(
            db,
            kb_id=kb_id,
            bid_outline_id=bid_outline_id,
            outline_node_id=outline_node_id,
        )
    except OutlineNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )
    except OutlineNodeNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error(
                "OUTLINE_NODE_NOT_FOUND",
                "Bid outline node not found",
                trace_id=get_trace_id(),
            ),
        )
    return success(payload, trace_id=get_trace_id())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/contract/test_bid_outline_node_content.py -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/bid_outlines.py backend/tests/contract/test_bid_outline_node_content.py
git commit -m "feat: expose GET bid outline node subtree content API"
```

---

## Task 3: 前端 API client

**Files:**
- Modify: `frontend/src/services/bidOutlines.ts`

- [ ] **Step 1: Add types and `getOutlineNodeContent`**

在 `BidOutlineNodesResult` 之后添加：

```typescript
export interface OutlineNodeContentSection {
  outline_node_id: string;
  title: string;
  level: number;
  sort_order: number;
  source_node_id: string | null;
  content: string;
  has_content: boolean;
  empty_reason: "no_source_node" | "empty_body" | null;
}

export interface OutlineNodeContentResult {
  outline_node_id: string;
  title: string;
  bid_outline_id: string;
  source_doc_id: string;
  sections: OutlineNodeContentSection[];
}
```

在文件末尾添加：

```typescript
export async function getOutlineNodeContent(
  kbId: string,
  bidOutlineId: string,
  outlineNodeId: string,
): Promise<OutlineNodeContentResult> {
  return apiRequest<OutlineNodeContentResult>(
    `/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/nodes/${outlineNodeId}/content`,
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run build`

Expected: build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/bidOutlines.ts
git commit -m "feat: add getOutlineNodeContent API client"
```

---

## Task 4: `OutlineNodeContentDrawer` 组件

**Files:**
- Create: `frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.tsx`
- Create: `frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import OutlineNodeContentDrawer from "./OutlineNodeContentDrawer";
import * as bidOutlines from "../../services/bidOutlines";

vi.mock("../../services/bidOutlines", () => ({
  getOutlineNodeContent: vi.fn(),
}));

describe("OutlineNodeContentDrawer", () => {
  it("renders section titles and paragraph content", async () => {
    vi.mocked(bidOutlines.getOutlineNodeContent).mockResolvedValue({
      outline_node_id: "n1",
      title: "技术方案",
      bid_outline_id: "o1",
      source_doc_id: "d1",
      sections: [
        {
          outline_node_id: "n1",
          title: "技术方案",
          level: 1,
          sort_order: 0,
          source_node_id: "s1",
          content: JSON.stringify({
            format: "blocks_v1",
            blocks: [{ type: "paragraph", text: "正文段落" }],
          }),
          has_content: true,
          empty_reason: null,
        },
        {
          outline_node_id: "n2",
          title: "子节",
          level: 2,
          sort_order: 0,
          source_node_id: null,
          content: JSON.stringify({ format: "blocks_v1", blocks: [] }),
          has_content: false,
          empty_reason: "no_source_node",
        },
      ],
    });

    render(
      <OutlineNodeContentDrawer
        open
        kbId="kb-1"
        bidOutlineId="o1"
        outlineNodeId="n1"
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("技术方案 — 章节内容")).toBeInTheDocument();
      expect(screen.getByText("正文段落")).toBeInTheDocument();
      expect(screen.getByText("子节")).toBeInTheDocument();
      expect(screen.getByText("暂无关联正文")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- OutlineNodeContentDrawer.test.tsx`

Expected: FAIL — module not found

- [ ] **Step 3: Implement Drawer**

```tsx
// frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.tsx
import { Alert, Button, Drawer, Space, Spin, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import RichContentViewer from "../../components/RichContentViewer";
import {
  getOutlineNodeContent,
  type OutlineNodeContentResult,
} from "../../services/bidOutlines";

type Props = {
  open: boolean;
  kbId?: string;
  bidOutlineId?: string;
  outlineNodeId?: string | null;
  onClose: () => void;
};

function sectionTitleLevel(level: number): 4 | 5 {
  return level <= 1 ? 4 : 5;
}

export default function OutlineNodeContentDrawer({
  open,
  kbId,
  bidOutlineId,
  outlineNodeId,
  onClose,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<OutlineNodeContentResult | null>(null);

  const reload = useCallback(async () => {
    if (!kbId || !bidOutlineId || !outlineNodeId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getOutlineNodeContent(kbId, bidOutlineId, outlineNodeId);
      setData(result);
    } catch (err) {
      setError((err as Error).message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [kbId, bidOutlineId, outlineNodeId]);

  useEffect(() => {
    if (open) void reload();
  }, [open, reload]);

  const hasAnyContent = data?.sections.some((section) => section.has_content) ?? false;

  return (
    <Drawer
      title={data ? `${data.title} — 章节内容` : "章节内容"}
      width={720}
      open={open}
      onClose={onClose}
      extra={<Button onClick={() => void reload()}>刷新</Button>}
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button size="small" onClick={() => void reload()}>
              重试
            </Button>
          }
        />
      ) : null}
      <Spin spinning={loading}>
        {data && !hasAnyContent ? (
          <Alert type="info" showIcon message="该目录下暂无正文内容" style={{ marginBottom: 16 }} />
        ) : null}
        {data?.sections.map((section, index) => (
          <div
            key={section.outline_node_id}
            style={{
              marginBottom: index < data.sections.length - 1 ? 24 : 0,
              paddingLeft: (section.level - 1) * 16,
            }}
          >
            {section.level >= 3 ? (
              <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                {section.title}
              </Typography.Text>
            ) : (
              <Typography.Title level={sectionTitleLevel(section.level)} style={{ marginTop: 0 }}>
                {section.title}
              </Typography.Title>
            )}
            {section.empty_reason === "no_source_node" ? (
              <Typography.Text type="secondary">暂无关联正文</Typography.Text>
            ) : (
              <RichContentViewer kbId={kbId ?? ""} content={section.content} />
            )}
          </div>
        ))}
      </Spin>
    </Drawer>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- OutlineNodeContentDrawer.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.tsx frontend/src/pages/OutlineCenter/OutlineNodeContentDrawer.test.tsx
git commit -m "feat: add OutlineNodeContentDrawer for subtree content preview"
```

---

## Task 5: 目录树 hover 按钮与详情页集成

**Files:**
- Modify: `frontend/src/pages/OutlineCenter/OutlineTreeEditor.tsx`
- Modify: `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx`

- [ ] **Step 1: Update `OutlineTreeEditor`**

```tsx
// 新增 import
import { Button, Card, Tag, Tree } from "antd";
import { useState } from "react";

// Props 增加
type OutlineTreeEditorProps = {
  roots: OutlineTreeNode[];
  selectedId: string | null;
  onSelect: (outlineNodeId: string) => void;
  onDropNode: (dragId: string, dropId: string, dropToGap: boolean) => void;
  onViewContent?: (outlineNodeId: string) => void;
};

// 将 toTreeData 改为接收 hoveredId / setHoveredId / onViewContent
function toTreeData(
  nodes: OutlineTreeNode[],
  hoveredId: string | null,
  setHoveredId: (id: string | null) => void,
  onViewContent?: (outlineNodeId: string) => void,
): DataNode[] {
  return nodes.map((node) => ({
    key: node.outline_node_id,
    title: (
      <span
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
        onMouseEnter={() => setHoveredId(node.outline_node_id)}
        onMouseLeave={() => setHoveredId(null)}
      >
        <span>
          {node.title} <Tag style={{ marginInlineStart: 8 }}>L{node.level}</Tag>
        </span>
        {onViewContent && hoveredId === node.outline_node_id ? (
          <Button
            type="link"
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              onViewContent(node.outline_node_id);
            }}
          >
            查看内容
          </Button>
        ) : null}
      </span>
    ),
    children: toTreeData(node.children ?? [], hoveredId, setHoveredId, onViewContent),
  }));
}

// 组件内
const [hoveredId, setHoveredId] = useState<string | null>(null);
// treeData={toTreeData(roots, hoveredId, setHoveredId, onViewContent)}
```

- [ ] **Step 2: Wire `OutlineDetailPage`**

```tsx
// import OutlineNodeContentDrawer
import OutlineNodeContentDrawer from "./OutlineNodeContentDrawer";

// state
const [contentDrawerNodeId, setContentDrawerNodeId] = useState<string | null>(null);

// OutlineTreeEditor
<OutlineTreeEditor
  roots={treeRoots}
  selectedId={selectedNodeId}
  onSelect={setSelectedNodeId}
  onDropNode={handleDropNode}
  onViewContent={setContentDrawerNodeId}
/>

// 在 return 末尾、其他 Drawer 旁
<OutlineNodeContentDrawer
  open={contentDrawerNodeId != null}
  kbId={selectedKbId}
  bidOutlineId={bidOutlineId}
  outlineNodeId={contentDrawerNodeId}
  onClose={() => setContentDrawerNodeId(null)}
/>
```

- [ ] **Step 3: Manual smoke test**

1. 启动 backend + frontend
2. 打开目录详情页，悬停节点见「查看内容」
3. 点击后 Drawer 展示多节标题与正文

- [ ] **Step 4: Run full test suites**

Run:
```bash
cd backend && ../.venv/bin/python -m pytest tests/unit/test_outline_node_content_service.py tests/contract/test_bid_outline_node_content.py -v
cd ../frontend && npm test -- OutlineNodeContentDrawer.test.tsx && npm run build
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/OutlineCenter/OutlineTreeEditor.tsx frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx
git commit -m "feat: add hover view-content button on outline tree"
```

---

## Spec Coverage Check

| Spec 要求 | Task |
|-----------|------|
| 悬停「查看内容」按钮 | Task 5 |
| 右侧 Drawer 720px | Task 4 |
| 子树含子孙正文 | Task 1 |
| 每节展示标题 | Task 4 |
| `empty_reason` 空态 | Task 1, 4 |
| 复用 `build_section_content` | Task 1 |
| 复用 `RichContentViewer` | Task 4 |
| 后端单测 | Task 1 |
| 契约测试 | Task 2 |
| 前端单测 | Task 4 |
