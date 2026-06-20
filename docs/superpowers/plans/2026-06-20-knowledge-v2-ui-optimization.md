# Knowledge V2 UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化知识录入 V2 与知识浏览 V2 的前端体验——章节/详情内容格式化预览、可拖拽三栏布局、全页面中文字段与枚举展示、浏览筛选折叠。

**Architecture:** 新建 `knowledgeChunkMeta.ts` 集中中文映射；`buildContentBlocks` + `renderKnowledgeAsset` + `KnowledgeContentViewer` 复用于录入预览与详情；`ResizableWorkspace` 用 Ant Design 嵌套 `Splitter`；三页改造仅换 UI 层，API payload 仍传英文枚举。

**Tech Stack:** React 18, TypeScript, Ant Design 5.28 (`Splitter`), react-markdown 9, remark-gfm 4, vitest + @testing-library/react

**Design spec:** `docs/superpowers/specs/2026-06-20-knowledge-v2-ui-optimization-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `frontend/package.json` | 新增 `react-markdown`、`remark-gfm` |
| `frontend/src/constants/knowledgeChunkMeta.ts` | 字段/枚举中文映射与工具函数 |
| `frontend/src/constants/knowledgeChunkMeta.test.ts` | 元数据字典单元测试 |
| `frontend/src/components/KnowledgeV2/buildContentBlocks.ts` | `content_md` + assets → 有序块 |
| `frontend/src/components/KnowledgeV2/buildContentBlocks.test.ts` | 块切分单元测试 |
| `frontend/src/components/KnowledgeV2/renderKnowledgeAsset.tsx` | 图片/表格资产渲染（从录入页抽出） |
| `frontend/src/components/KnowledgeV2/KnowledgeContentViewer.tsx` | 预览/源码 Segmented 切换 |
| `frontend/src/components/KnowledgeV2/KnowledgeContentViewer.test.tsx` | 预览组件 smoke 测试 |
| `frontend/src/components/KnowledgeV2/ResizableWorkspace.tsx` | 三栏嵌套 Splitter + localStorage |
| `frontend/src/pages/KnowledgeV2/KnowledgeEntryPage.tsx` | 录入页改造 |
| `frontend/src/pages/KnowledgeV2/KnowledgeBrowsePage.tsx` | 浏览页改造 |
| `frontend/src/pages/KnowledgeV2/KnowledgeChunkDetailDrawer.tsx` | 详情 Drawer 改造 |

---

## Task 1: 安装 Markdown 依赖

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 安装依赖**

```bash
cd frontend
npm install react-markdown@^9.0.0 remark-gfm@^4.0.0
```

Expected: `package.json` 与 `package-lock.json` 更新，无 peer dependency 错误。

- [ ] **Step 2: 验证构建**

```bash
cd frontend
npm run build
```

Expected: PASS（TypeScript 编译 + Vite build 成功）

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add react-markdown and remark-gfm for knowledge preview"
```

---

## Task 2: 元数据字典 `knowledgeChunkMeta`

**Files:**
- Create: `frontend/src/constants/knowledgeChunkMeta.ts`
- Create: `frontend/src/constants/knowledgeChunkMeta.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/constants/knowledgeChunkMeta.test.ts
import { describe, expect, it } from "vitest";
import {
  formatBoolean,
  getAssetTypeLabel,
  getEnumLabel,
  getEnumOptions,
  getFieldLabel,
} from "./knowledgeChunkMeta";

describe("knowledgeChunkMeta", () => {
  it("returns Chinese field labels", () => {
    expect(getFieldLabel("knowledge_type")).toBe("知识类型");
    expect(getFieldLabel("issue_date_from")).toBe("生效日期起");
  });

  it("falls back to raw field name for unknown fields", () => {
    expect(getFieldLabel("unknown_field")).toBe("unknown_field");
  });

  it("returns Chinese enum labels", () => {
    expect(getEnumLabel("knowledge_type", "fact")).toBe("事实");
    expect(getEnumLabel("status", "draft")).toBe("草稿");
    expect(getEnumLabel("quote_mode", "full")).toBe("全文引用");
  });

  it("falls back to raw enum value when unknown", () => {
    expect(getEnumLabel("knowledge_type", "custom")).toBe("custom");
    expect(getEnumLabel("knowledge_type", null)).toBe("-");
  });

  it("builds select options with English value and Chinese label", () => {
    const options = getEnumOptions("status");
    expect(options).toContainEqual({ value: "draft", label: "草稿" });
    expect(options).toContainEqual({ value: "active", label: "生效" });
  });

  it("formats booleans in Chinese", () => {
    expect(formatBoolean(true)).toBe("是");
    expect(formatBoolean(false)).toBe("否");
    expect(formatBoolean(null)).toBe("-");
  });

  it("returns asset type labels", () => {
    expect(getAssetTypeLabel("image")).toBe("图片");
    expect(getAssetTypeLabel("table")).toBe("表格");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm test -- src/constants/knowledgeChunkMeta.test.ts
```

Expected: FAIL — module `./knowledgeChunkMeta` not found

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/constants/knowledgeChunkMeta.ts
export const FIELD_LABELS: Record<string, string> = {
  title: "标题",
  content: "内容",
  summary: "摘要",
  knowledge_type: "知识类型",
  content_type: "内容类型",
  source_type: "来源类型",
  file_name: "文件名",
  project_name: "项目名称",
  category: "分类",
  status: "状态",
  quote_mode: "引用模式",
  template_type: "模板类型",
  security_level: "安全级别",
  review_status: "审核状态",
  owner: "负责人",
  issue_date: "生效日期",
  expire_date: "失效日期",
  tags: "标签",
  products: "产品",
  industries: "行业",
  customer_types: "客户类型",
  regions: "地区",
  page_start: "起始页",
  page_end: "结束页",
  char_start: "起始字符",
  char_end: "结束字符",
  parent_id: "父级 ID",
  retrieval_weight: "检索权重",
  edit_distance_avg: "平均编辑距离",
  catalog_path: "目录路径",
  variables: "变量",
  exclusion_rules: "排除规则",
  need_parent_context: "需要父级上下文",
  is_template: "是否模板",
  is_immutable: "是否不可变",
  winning_flag: "中标标记",
  keyword: "关键词",
  issue_date_from: "生效日期起",
  issue_date_to: "生效日期止",
  expire_date_from: "失效日期起",
  expire_date_to: "失效日期止",
  id: "ID",
  kb_id: "知识库 ID",
  knowledge_code: "知识编码",
  version: "版本",
  previous_version_id: "上一版本 ID",
  is_latest: "是否最新",
  doc_id: "文档 ID",
  primary_node_id: "主节点 ID",
  token_count: "Token 数",
  content_hash: "内容哈希",
  has_children: "是否有子节点",
  children_count: "子节点数",
  create_time: "创建时间",
  update_time: "更新时间",
  embedding_status: "向量状态",
  previous_version: "上一版本",
  asset_code: "资产编码",
  chunk_id: "知识块 ID",
  table_type: "表格类型",
  image_type: "图片类型",
  allow_row_filter: "允许行过滤",
  required_with_text: "与正文绑定",
  position_hint: "位置提示",
  image_caption: "图片说明",
  image_ocr_text: "图片 OCR",
  llm_summary: "LLM 摘要",
  table_summary: "表格摘要",
  table_schema: "表格结构",
  table_headers: "表头",
  table_rows: "表格行",
};

export const ENUM_LABELS: Record<string, Record<string, string>> = {
  knowledge_type: {
    fact: "事实",
    template: "模板",
    solution: "方案",
    case: "案例",
    table: "表格",
    image: "图片",
  },
  content_type: { text: "文本", mixed: "混合" },
  source_type: {
    bid: "标书",
    proposal: "投标方案",
    qualification: "资质",
    contract: "合同",
    manual: "手册",
    wiki: "百科",
    case: "案例",
  },
  category: {
    qualification: "资质",
    technical: "技术",
    business: "商务",
    legal: "法务",
    personnel: "人员",
    price: "报价",
    case: "案例",
    template: "模板",
  },
  status: {
    draft: "草稿",
    active: "生效",
    deprecated: "已废弃",
    disabled: "已禁用",
  },
  security_level: { public: "公开", internal: "内部", confidential: "机密" },
  review_status: { pending: "待审核", approved: "已通过", rejected: "已驳回" },
  quote_mode: { full: "全文引用", partial: "部分引用" },
  template_type: {
    commitment: "承诺函",
    authorization: "授权书",
    response: "响应说明",
    technical_solution: "技术方案",
    implementation_plan: "实施方案",
    service_plan: "服务方案",
    quotation: "报价",
  },
  embedding_status: { pending: "待处理", ready: "已完成", failed: "失败" },
};

export const ASSET_TYPE_LABELS: Record<string, string> = {
  image: "图片",
  table: "表格",
};

export const BOOLEAN_OPTIONS = [
  { value: "true", label: "是" },
  { value: "false", label: "否" },
] as const;

export function getFieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

export function getEnumLabel(field: string, value: string | null | undefined): string {
  if (!value) return "-";
  return ENUM_LABELS[field]?.[value] ?? value;
}

export function getEnumOptions(field: string): { value: string; label: string }[] {
  const labels = ENUM_LABELS[field];
  if (!labels) return [];
  return Object.entries(labels).map(([value, label]) => ({ value, label }));
}

export function formatBoolean(value: boolean | null | undefined): string {
  if (value === true) return "是";
  if (value === false) return "否";
  return "-";
}

export function getAssetTypeLabel(assetType: string): string {
  return ASSET_TYPE_LABELS[assetType] ?? assetType;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm test -- src/constants/knowledgeChunkMeta.test.ts
```

Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/constants/knowledgeChunkMeta.ts frontend/src/constants/knowledgeChunkMeta.test.ts
git commit -m "feat(frontend): add knowledge chunk Chinese field and enum metadata"
```

---

## Task 3: 内容块切分 `buildContentBlocks`

**Files:**
- Create: `frontend/src/components/KnowledgeV2/buildContentBlocks.ts`
- Create: `frontend/src/components/KnowledgeV2/buildContentBlocks.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/KnowledgeV2/buildContentBlocks.test.ts
import { describe, expect, it } from "vitest";
import { buildContentBlocks } from "./buildContentBlocks";

const baseAsset = {
  asset_type: "image",
  asset_code: null,
  char_end: null,
  page_start: null,
  page_end: null,
  raw_markdown: null,
  image_storage_url: "http://example.com/a.png",
};

describe("buildContentBlocks", () => {
  it("returns a single text block for plain markdown without assets", () => {
    const blocks = buildContentBlocks({
      contentMd: "# Hello\n\nWorld",
      assets: [],
      sectionCharStart: 100,
    });
    expect(blocks).toEqual([{ type: "text", content: "# Hello\n\nWorld" }]);
  });

  it("interleaves text and positioned assets by char_start relative to section", () => {
    const blocks = buildContentBlocks({
      contentMd: "AAAA\n\nBBBB",
      sectionCharStart: 100,
      assets: [
        { id: 1, ...baseAsset, char_start: 104 },
        { id: 2, ...baseAsset, asset_type: "table", char_start: 110, raw_markdown: "|h|\n|-|\n|v|" },
      ],
    });
    expect(blocks).toEqual([
      { type: "text", content: "AAAA" },
      { type: "asset", asset: expect.objectContaining({ id: 1 }) },
      { type: "text", content: "\n\nBBBB" },
      { type: "asset", asset: expect.objectContaining({ id: 2 }) },
    ]);
  });

  it("appends assets without char_start to the end", () => {
    const blocks = buildContentBlocks({
      contentMd: "only text",
      assets: [{ id: 9, ...baseAsset, char_start: null }],
    });
    expect(blocks).toEqual([
      { type: "text", content: "only text" },
      { type: "asset", asset: expect.objectContaining({ id: 9 }) },
    ]);
  });

  it("ignores assets whose char_start falls outside the section range", () => {
    const blocks = buildContentBlocks({
      contentMd: "section",
      sectionCharStart: 50,
      assets: [{ id: 3, ...baseAsset, char_start: 10 }],
    });
    expect(blocks).toEqual([{ type: "text", content: "section" }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm test -- src/components/KnowledgeV2/buildContentBlocks.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/components/KnowledgeV2/buildContentBlocks.ts
export interface KnowledgeAssetLike {
  id: number;
  asset_type: string;
  asset_code?: string | null;
  char_start: number | null;
  char_end?: number | null;
  page_start?: number | null;
  page_end?: number | null;
  raw_markdown: string | null;
  image_storage_url?: string | null;
}

export type ContentBlock =
  | { type: "text"; content: string }
  | { type: "asset"; asset: KnowledgeAssetLike };

export interface BuildContentBlocksInput {
  contentMd: string;
  assets: KnowledgeAssetLike[];
  sectionCharStart?: number | null;
}

interface PositionedAsset {
  asset: KnowledgeAssetLike;
  relativeOffset: number;
}

function toRelativeOffset(
  asset: KnowledgeAssetLike,
  sectionCharStart: number | null | undefined,
  contentLength: number,
): number | null {
  if (asset.char_start === null || asset.char_start === undefined) {
    return null;
  }
  if (sectionCharStart === null || sectionCharStart === undefined) {
    return null;
  }
  const relative = asset.char_start - sectionCharStart;
  if (relative < 0 || relative > contentLength) {
    return null;
  }
  return relative;
}

export function buildContentBlocks(input: BuildContentBlocksInput): ContentBlock[] {
  const { contentMd, assets, sectionCharStart } = input;
  const positioned: PositionedAsset[] = [];
  const unpositioned: KnowledgeAssetLike[] = [];

  for (const asset of assets) {
    const relativeOffset = toRelativeOffset(asset, sectionCharStart, contentMd.length);
    if (relativeOffset === null) {
      unpositioned.push(asset);
      continue;
    }
    positioned.push({ asset, relativeOffset });
  }

  positioned.sort((a, b) => {
    if (a.relativeOffset !== b.relativeOffset) {
      return a.relativeOffset - b.relativeOffset;
    }
    return a.asset.id - b.asset.id;
  });

  const blocks: ContentBlock[] = [];
  let cursor = 0;

  for (const item of positioned) {
    if (item.relativeOffset > cursor) {
      blocks.push({ type: "text", content: contentMd.slice(cursor, item.relativeOffset) });
    }
    blocks.push({ type: "asset", asset: item.asset });
    cursor = Math.max(cursor, item.relativeOffset);
  }

  if (cursor < contentMd.length) {
    blocks.push({ type: "text", content: contentMd.slice(cursor) });
  }

  if (blocks.length === 0 && contentMd) {
    blocks.push({ type: "text", content: contentMd });
  }

  for (const asset of unpositioned) {
    blocks.push({ type: "asset", asset });
  }

  return blocks;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm test -- src/components/KnowledgeV2/buildContentBlocks.test.ts
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/KnowledgeV2/buildContentBlocks.ts frontend/src/components/KnowledgeV2/buildContentBlocks.test.ts
git commit -m "feat(frontend): add content block builder for inline asset preview"
```

---

## Task 4: 资产渲染模块 `renderKnowledgeAsset`

**Files:**
- Create: `frontend/src/components/KnowledgeV2/renderKnowledgeAsset.tsx`

从 `KnowledgeEntryPage.tsx` 抽出 `parseMarkdownTable` 与 `renderAsset`，供预览组件与详情 Drawer 共用。

- [ ] **Step 1: 创建共享渲染模块**

```tsx
// frontend/src/components/KnowledgeV2/renderKnowledgeAsset.tsx
import type { ReactNode } from "react";
import type { KnowledgeAssetLike } from "./buildContentBlocks";

export function parseMarkdownTable(raw?: string | null): { headers: string[]; rows: string[][] } | null {
  if (!raw) return null;
  const lines = raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return null;
  const separator = lines[1].replace(/\|/g, "").replace(/[-:\s]/g, "");
  if (separator.length > 0) return null;

  const parseLine = (line: string) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());

  const headers = parseLine(lines[0]);
  if (headers.length === 0) return null;
  const rows = lines.slice(2).map(parseLine).filter((row) => row.length > 0);
  return { headers, rows };
}

export function renderKnowledgeAsset(asset: KnowledgeAssetLike): ReactNode {
  if (asset.asset_type === "image" && asset.image_storage_url) {
    return (
      <img
        src={asset.image_storage_url}
        alt={asset.asset_code ?? `image-${asset.id}`}
        style={{ maxWidth: "100%", border: "1px solid #f0f0f0", borderRadius: 6 }}
      />
    );
  }
  if (asset.asset_type === "table") {
    const table = parseMarkdownTable(asset.raw_markdown);
    if (table) {
      return (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {table.headers.map((header) => (
                  <th
                    key={header}
                    style={{ border: "1px solid #f0f0f0", textAlign: "left", padding: 8, background: "#fafafa" }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, index) => (
                <tr key={`r-${index}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`c-${index}-${cellIndex}`} style={{ border: "1px solid #f0f0f0", padding: 8 }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
  }
  return (
    <pre style={{ whiteSpace: "pre-wrap", margin: 0, background: "#fafafa", padding: 12, borderRadius: 6 }}>
      {asset.raw_markdown || "(无预览数据)"}
    </pre>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/KnowledgeV2/renderKnowledgeAsset.tsx
git commit -m "feat(frontend): extract shared knowledge asset renderer"
```

---

## Task 5: 内容预览组件 `KnowledgeContentViewer`

**Files:**
- Create: `frontend/src/components/KnowledgeV2/KnowledgeContentViewer.tsx`
- Create: `frontend/src/components/KnowledgeV2/KnowledgeContentViewer.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/KnowledgeV2/KnowledgeContentViewer.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import KnowledgeContentViewer from "./KnowledgeContentViewer";

describe("KnowledgeContentViewer", () => {
  it("renders markdown heading in preview mode by default", () => {
    render(
      <KnowledgeContentViewer
        contentMd={"# 章节标题\n\n正文段落"}
        assets={[]}
        sectionCharStart={0}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "章节标题" })).toBeInTheDocument();
    expect(screen.getByText("正文段落")).toBeInTheDocument();
  });

  it("switches to source mode and shows raw markdown", async () => {
    const user = userEvent.setup();
    render(
      <KnowledgeContentViewer contentMd={"# 标题"} assets={[]} sectionCharStart={0} />,
    );
    await user.click(screen.getByText("源码"));
    expect(screen.getByText("# 标题")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm test -- src/components/KnowledgeV2/KnowledgeContentViewer.test.tsx
```

Expected: FAIL — component not found

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/KnowledgeV2/KnowledgeContentViewer.tsx
import { Collapse, Segmented, Space } from "antd";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getAssetTypeLabel } from "../../constants/knowledgeChunkMeta";
import { buildContentBlocks, type KnowledgeAssetLike } from "./buildContentBlocks";
import { renderKnowledgeAsset } from "./renderKnowledgeAsset";

export type ContentViewMode = "preview" | "source";

interface KnowledgeContentViewerProps {
  contentMd: string;
  assets: KnowledgeAssetLike[];
  sectionCharStart?: number | null;
  showModeToggle?: boolean;
  defaultMode?: ContentViewMode;
}

export default function KnowledgeContentViewer({
  contentMd,
  assets,
  sectionCharStart,
  showModeToggle = true,
  defaultMode = "preview",
}: KnowledgeContentViewerProps) {
  const [mode, setMode] = useState<ContentViewMode>(defaultMode);

  const blocks = useMemo(
    () => buildContentBlocks({ contentMd, assets, sectionCharStart }),
    [assets, contentMd, sectionCharStart],
  );

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {showModeToggle ? (
        <Segmented
          value={mode}
          options={[
            { label: "预览", value: "preview" },
            { label: "源码", value: "source" },
          ]}
          onChange={(value) => setMode(value as ContentViewMode)}
        />
      ) : null}

      {mode === "preview" ? (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {blocks.map((block, index) => {
            if (block.type === "text") {
              if (!block.content.trim()) return null;
              return (
                <div key={`text-${index}`} className="knowledge-content-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.content}</ReactMarkdown>
                </div>
              );
            }
            return <div key={`asset-${block.asset.id}`}>{renderKnowledgeAsset(block.asset)}</div>;
          })}
        </Space>
      ) : (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, background: "#fafafa", padding: 12, borderRadius: 6 }}>
            {contentMd || "-"}
          </pre>
          {assets.length ? (
            <Collapse
              items={assets.map((asset) => ({
                key: String(asset.id),
                label: `${getAssetTypeLabel(asset.asset_type)} #${asset.id}`,
                children: (
                  <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{asset.raw_markdown || "(无源码)"}</pre>
                ),
              }))}
            />
          ) : null}
        </Space>
      )}
    </Space>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm test -- src/components/KnowledgeV2/KnowledgeContentViewer.test.tsx
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/KnowledgeV2/KnowledgeContentViewer.tsx frontend/src/components/KnowledgeV2/KnowledgeContentViewer.test.tsx
git commit -m "feat(frontend): add knowledge content viewer with preview and source modes"
```

---

## Task 6: 可拖拽三栏 `ResizableWorkspace`

**Files:**
- Create: `frontend/src/components/KnowledgeV2/ResizableWorkspace.tsx`

- [ ] **Step 1: 创建 ResizableWorkspace**

```tsx
// frontend/src/components/KnowledgeV2/ResizableWorkspace.tsx
import { Splitter } from "antd";
import type { ReactNode } from "react";
import { useCallback, useMemo, useState } from "react";

const STORAGE_KEY = "knowledge-v2-entry-layout";
const DEFAULT_OUTER: [number, number] = [20, 80];
const DEFAULT_INNER: [number, number] = [56.25, 43.75];

interface StoredLayout {
  outer: [number, number];
  inner: [number, number];
}

function readStoredLayout(): StoredLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { outer: DEFAULT_OUTER, inner: DEFAULT_INNER };
    const parsed = JSON.parse(raw) as StoredLayout;
    if (!Array.isArray(parsed.outer) || !Array.isArray(parsed.inner)) {
      return { outer: DEFAULT_OUTER, inner: DEFAULT_INNER };
    }
    return {
      outer: [Number(parsed.outer[0]) || DEFAULT_OUTER[0], Number(parsed.outer[1]) || DEFAULT_OUTER[1]],
      inner: [Number(parsed.inner[0]) || DEFAULT_INNER[0], Number(parsed.inner[1]) || DEFAULT_INNER[1]],
    };
  } catch {
    return { outer: DEFAULT_OUTER, inner: DEFAULT_INNER };
  }
}

interface ResizableWorkspaceProps {
  treePanel: ReactNode;
  previewPanel: ReactNode;
  entryPanel: ReactNode;
}

export default function ResizableWorkspace({ treePanel, previewPanel, entryPanel }: ResizableWorkspaceProps) {
  const initial = useMemo(() => readStoredLayout(), []);
  const [outerSizes, setOuterSizes] = useState<[number, number]>(initial.outer);
  const [innerSizes, setInnerSizes] = useState<[number, number]>(initial.inner);

  const persistLayout = useCallback((outer: [number, number], inner: [number, number]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ outer, inner }));
    } catch {
      // ignore storage failures
    }
  }, []);

  return (
    <Splitter
      style={{ width: "100%", minHeight: "calc(100vh - 280px)" }}
      onResizeEnd={(sizes) => {
        const next: [number, number] = [Number(sizes[0]), Number(sizes[1])];
        setOuterSizes(next);
        persistLayout(next, innerSizes);
      }}
    >
      <Splitter.Panel size={`${outerSizes[0]}%`} min="200px">
        {treePanel}
      </Splitter.Panel>
      <Splitter.Panel size={`${outerSizes[1]}%`} min="200px">
        <Splitter
          onResizeEnd={(sizes) => {
            const next: [number, number] = [Number(sizes[0]), Number(sizes[1])];
            setInnerSizes(next);
            persistLayout(outerSizes, next);
          }}
        >
          <Splitter.Panel size={`${innerSizes[0]}%`} min="200px">
            {previewPanel}
          </Splitter.Panel>
          <Splitter.Panel size={`${innerSizes[1]}%`} min="200px">
            {entryPanel}
          </Splitter.Panel>
        </Splitter>
      </Splitter.Panel>
    </Splitter>
  );
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd frontend
npm run build
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/KnowledgeV2/ResizableWorkspace.tsx
git commit -m "feat(frontend): add resizable three-column workspace for knowledge entry"
```

---

## Task 7: 改造知识录入页 `KnowledgeEntryPage`

**Files:**
- Modify: `frontend/src/pages/KnowledgeV2/KnowledgeEntryPage.tsx`

- [ ] **Step 1: 移除页内重复的 `parseMarkdownTable` / `renderAsset`**

删除 `KnowledgeEntryPage.tsx` 中第 113–193 行的 `parseMarkdownTable` 与 `renderAsset` 函数（已由 `renderKnowledgeAsset.tsx` 替代）。

- [ ] **Step 2: 更新 imports**

在文件顶部添加：

```typescript
import KnowledgeContentViewer from "../../components/KnowledgeV2/KnowledgeContentViewer";
import ResizableWorkspace from "../../components/KnowledgeV2/ResizableWorkspace";
import {
  getEnumOptions,
  getFieldLabel,
} from "../../constants/knowledgeChunkMeta";
```

- [ ] **Step 3: 顶部文档选择改为单行**

将：

```tsx
<Card title="选择来源文档">
  <Select ... />
</Card>
```

替换为：

```tsx
<div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
  <span>来源文档：</span>
  <Select
    style={{ width: 420, maxWidth: "100%", flex: 1 }}
    loading={loadingDocuments}
    placeholder="请选择文档"
    value={selectedDocId}
    options={documents.map((doc) => ({
      label: doc.source_type === "template" ? `${doc.document_name}（模板）` : doc.document_name,
      value: doc.doc_id,
    }))}
    onChange={(value) => setSelectedDocId(value)}
  />
</div>
```

- [ ] **Step 4: 三栏改为 ResizableWorkspace**

将 `<Row gutter={16}>...</Row>` 三列布局替换为：

```tsx
<ResizableWorkspace
  treePanel={
    <Card title="目录树" bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
      {loadingTree ? <Spin /> : (
        <Tree
          treeData={toTreeData(treeNodes)}
          selectedKeys={selectedNodeId ? [selectedNodeId] : []}
          onSelect={(keys) => setSelectedNodeId(keys[0] as string | undefined)}
        />
      )}
    </Card>
  }
  previewPanel={
    <Card
      title="章节预览"
      extra={
        <Button disabled={!preview || readOnly} onClick={() => void handlePrefill()}>
          添加到知识库
        </Button>
      }
      bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}
    >
      {loadingPreview ? <Spin /> : null}
      {!loadingPreview && !preview ? <Text type="secondary">请选择目录节点查看内容</Text> : null}
      {preview ? (
        <KnowledgeContentViewer
          contentMd={preview.content_md}
          assets={preview.assets}
          sectionCharStart={preview.char_start}
        />
      ) : null}
    </Card>
  }
  entryPanel={
    <Card title="知识录入" bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
      {/* 保持现有 rightExpanded / prefilling / Form 逻辑 */}
    </Card>
  }
/>
```

- [ ] **Step 5: 表单 label 中文化 + 枚举改 Select**

将所有 `Form.Item` 的 `label="knowledge_type"` 等改为 `label={getFieldLabel("knowledge_type")}`。

以下字段由 `Input` 改为 `Select` + `getEnumOptions`：

| 字段 | 组件 |
|------|------|
| knowledge_type | `<Select options={getEnumOptions("knowledge_type")} allowClear />` |
| content_type | `<Select options={getEnumOptions("content_type")} allowClear />` |
| source_type | `<Select options={getEnumOptions("source_type")} allowClear />` |
| category | `<Select options={getEnumOptions("category")} allowClear />` |
| status | `<Select options={getEnumOptions("status")} allowClear />` |
| quote_mode | `<Select options={getEnumOptions("quote_mode")} allowClear />` |
| security_level | `<Select options={getEnumOptions("security_level")} allowClear />` |
| review_status | `<Select options={getEnumOptions("review_status")} allowClear />` |
| template_type | `<Select options={getEnumOptions("template_type")} allowClear />` |

JSON 文本域 label 示例：

```tsx
<Form.Item name="catalog_path_json" label={`${getFieldLabel("catalog_path")}(JSON 数组)`}>
```

布尔 Switch 保持，label 用 `getFieldLabel("is_template")` 等。

- [ ] **Step 6: 验证构建**

```bash
cd frontend
npm run build
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/KnowledgeV2/KnowledgeEntryPage.tsx
git commit -m "feat(frontend): improve knowledge entry page layout and Chinese form labels"
```

---

## Task 8: 改造知识浏览页 `KnowledgeBrowsePage`

**Files:**
- Modify: `frontend/src/pages/KnowledgeV2/KnowledgeBrowsePage.tsx`

- [ ] **Step 1: 添加 imports 与展开状态**

```typescript
import {
  getEnumLabel,
  getFieldLabel,
  BOOLEAN_OPTIONS,
} from "../../constants/knowledgeChunkMeta";
```

在组件内添加：

```typescript
const [filtersExpanded, setFiltersExpanded] = useState(false);
```

- [ ] **Step 2: 重构筛选表单为收起/展开**

将现有 `<Row gutter={12}>` 内全部 `Form.Item` 拆为两组：

**始终可见（收起态一行）** — 使用 `layout="inline"` 或 `Row` + `flex`：

```tsx
<Row gutter={12} align="middle">
  <Col flex="1 1 160px">
    <Form.Item name="category" label={getFieldLabel("category")}>
      <Input allowClear />
    </Form.Item>
  </Col>
  <Col flex="1 1 160px">
    <Form.Item name="knowledge_type" label={getFieldLabel("knowledge_type")}>
      <Input allowClear />
    </Form.Item>
  </Col>
  <Col flex="1 1 160px">
    <Form.Item name="status" label={getFieldLabel("status")}>
      <Input allowClear />
    </Form.Item>
  </Col>
  <Col flex="2 1 220px">
    <Form.Item name="keyword" label={getFieldLabel("keyword")}>
      <Input allowClear placeholder="匹配 title/summary" />
    </Form.Item>
  </Col>
  <Col flex="0 0 auto">
    <Space>
      <Button type="primary" onClick={applyFilters}>查询</Button>
      <Button onClick={resetFilters}>重置</Button>
      <Button type="link" onClick={() => setFiltersExpanded((v) => !v)}>
        {filtersExpanded ? "收起筛选" : "展开更多筛选"}
      </Button>
    </Space>
  </Col>
</Row>
```

**展开后追加** — `{filtersExpanded ? <Row>...</Row> : null}` 包含：
`source_type`, `products`, `industries`, `regions`, `tags`, `security_level`,
`is_template`, `winning_flag`, `review_status`,
`issue_date_from/to`, `expire_date_from/to`。

展开区的 `is_template` / `winning_flag` 使用：

```tsx
<Select allowClear options={[...BOOLEAN_OPTIONS]} />
```

所有 label 使用 `getFieldLabel(...)`。

将原底部 `查询/重置` Space 移除（已并入首行）；筛选方案 `Select` + 保存/删除按钮移到展开区底部或展开区最后一行。

- [ ] **Step 3: 列表列名中文化 + 枚举 Tag**

```typescript
const columns: ColumnsType<KnowledgeChunkListItem> = useMemo(
  () => [
    {
      title: getFieldLabel("title"),
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (_value, record) => (
        <Button type="link" size="small" onClick={() => setDetailChunkId(record.id)}>
          {record.title || "-"}
        </Button>
      ),
    },
    {
      title: getFieldLabel("version"),
      dataIndex: "version",
      key: "version",
      width: 120,
    },
    {
      title: getFieldLabel("category"),
      dataIndex: "category",
      key: "category",
      width: 140,
      render: (value: string) => getEnumLabel("category", value) || "-",
    },
    {
      title: getFieldLabel("knowledge_type"),
      dataIndex: "knowledge_type",
      key: "knowledge_type",
      width: 160,
      render: (value: string) => <Tag>{getEnumLabel("knowledge_type", value)}</Tag>,
    },
    {
      title: getFieldLabel("status"),
      dataIndex: "status",
      key: "status",
      width: 140,
      render: (value: string) => <Tag>{getEnumLabel("status", value)}</Tag>,
    },
    {
      title: getFieldLabel("token_count"),
      dataIndex: "token_count",
      key: "token_count",
      width: 120,
    },
    {
      title: getFieldLabel("update_time"),
      dataIndex: "update_time",
      key: "update_time",
      width: 190,
      render: (value: string | null) => formatDateTime(value),
    },
  ],
  [],
);
```

- [ ] **Step 4: 验证构建与测试**

```bash
cd frontend
npm run build
npm test
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/KnowledgeV2/KnowledgeBrowsePage.tsx
git commit -m "feat(frontend): collapse browse filters and localize table columns"
```

---

## Task 9: 改造知识详情 Drawer `KnowledgeChunkDetailDrawer`

**Files:**
- Modify: `frontend/src/pages/KnowledgeV2/KnowledgeChunkDetailDrawer.tsx`

- [ ] **Step 1: 更新 imports，移除重复函数**

添加：

```typescript
import KnowledgeContentViewer from "../../components/KnowledgeV2/KnowledgeContentViewer";
import { renderKnowledgeAsset } from "../../components/KnowledgeV2/renderKnowledgeAsset";
import {
  formatBoolean,
  getAssetTypeLabel,
  getEnumLabel,
  getFieldLabel,
} from "../../constants/knowledgeChunkMeta";
```

删除本地的 `parseMarkdownTable`、`renderAssetPreview`（改用 `renderKnowledgeAsset`）。

删除 `EMBEDDING_STATUS_META` 硬编码，改用 `getEnumLabel("embedding_status", ...)` + 保留颜色映射：

```typescript
const EMBEDDING_STATUS_COLORS: Record<string, string> = {
  pending: "warning",
  ready: "success",
  failed: "error",
};
```

- [ ] **Step 2: BaseInfo 全部 label 中文化 + 枚举/布尔中文**

将每个 `<Descriptions.Item label="knowledge_type">` 改为 `label={getFieldLabel("knowledge_type")}`。

枚举字段内容改为 `getEnumLabel("knowledge_type", detail.knowledge_type)`；
布尔字段改为 `formatBoolean(detail.is_template)` 等。

`embedding_status`：

```tsx
<Descriptions.Item label={getFieldLabel("embedding_status")}>
  <Tag color={EMBEDDING_STATUS_COLORS[detail.embedding_status] ?? "default"}>
    {getEnumLabel("embedding_status", detail.embedding_status)}
  </Tag>
</Descriptions.Item>
```

- [ ] **Step 3: 内容区改用 KnowledgeContentViewer**

将：

```tsx
<Card title="内容">
  <pre>...</pre>
</Card>
```

替换为：

```tsx
<Card title={getFieldLabel("content")}>
  <KnowledgeContentViewer
    contentMd={detail.content || ""}
    assets={detail.assets}
    sectionCharStart={detail.char_start}
  />
</Card>
```

- [ ] **Step 4: 结构字段 label 中文化 + Tag 列表**

`tags` / `products` / `industries` / `customer_types` / `regions` 改为：

```tsx
<Descriptions.Item label={getFieldLabel("tags")}>
  {detail.tags?.length ? detail.tags.map((tag) => <Tag key={tag}>{tag}</Tag>) : "-"}
</Descriptions.Item>
```

`catalog_path` / `variables` / `exclusion_rules` 保留 JSON `<pre>`，仅 label 中文化。

- [ ] **Step 5: 关联资产卡片标题与元数据中文化**

卡片 title：

```tsx
title={`${getAssetTypeLabel(asset.asset_type)} #${asset.id}`}
```

`Descriptions.Item label` 全部 `getFieldLabel(...)`；布尔用 `formatBoolean`；预览用 `renderKnowledgeAsset(asset)`。

- [ ] **Step 6: 验证**

```bash
cd frontend
npm run build
npm test
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/KnowledgeV2/KnowledgeChunkDetailDrawer.tsx
git commit -m "feat(frontend): localize knowledge detail drawer and add formatted content preview"
```

---

## Task 10: 全量回归与验收

**Files:**（只读检查，无新文件）

- [ ] **Step 1: 跑全部前端测试**

```bash
cd frontend
npm test
```

Expected: 全部 PASS

- [ ] **Step 2: 生产构建**

```bash
cd frontend
npm run build
```

Expected: PASS

- [ ] **Step 3: 手动冒烟（开发服务器）**

```bash
cd frontend
npm run dev
```

浏览器验证 design spec §13 七条验收标准：

1. `/knowledge-v2/entry` — 章节预览默认格式化 + 内联资产，可切源码
2. 两处 Splitter 可拖，刷新后宽度恢复
3. 顶部文档选择单行，无 Card
4. 录入表单中文 label + 中文枚举选项；Network 面板确认提交 payload 仍为英文枚举值
5. `/knowledge-v2/browse` — 默认 4 字段一行，展开后完整筛选
6. 列表列名中文，`status`/`knowledge_type` 显示中文 Tag
7. 详情 Drawer 内容默认格式化，字段 label 中文

- [ ] **Step 4: 最终 Commit（若有遗漏文件）**

```bash
git status
# 若有未提交改动：
git add -A
git commit -m "chore(frontend): complete knowledge V2 UI optimization verification"
```

---

## Spec Coverage Checklist

| Spec 要求 | 对应 Task |
|-----------|-----------|
| §6 共享预览组件（模式 C） | Task 3, 4, 5 |
| §5 元数据字典 | Task 2 |
| §7 录入页（单行文档、Splitter、中文表单） | Task 6, 7 |
| §8 浏览页（筛选折叠、列表中文） | Task 8 |
| §9 详情页（格式化内容、全中文） | Task 9 |
| §10 依赖变更 | Task 1 |
| §12 测试 | Task 2, 3, 5, 10 |
