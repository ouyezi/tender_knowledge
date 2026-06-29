import { describe, expect, it } from "vitest";
import {
  buildAutoCreatePayload,
  buildPrefillMetadata,
  collectCheckedNodeIds,
  withRetry,
} from "./batchIngestUtils";
import type { NodePreview, PrefillResult, TreeNode } from "../../services/knowledgeChunks";

const tree: TreeNode[] = [
  {
    node_id: "a",
    title: "第一章",
    parent_id: null,
    level: 1,
    sort_order: 0,
    ingested: false,
    children: [
      {
        node_id: "b",
        title: "1.1",
        parent_id: "a",
        level: 2,
        sort_order: 0,
        ingested: false,
        children: [],
      },
      {
        node_id: "c",
        title: "1.2",
        parent_id: "a",
        level: 2,
        sort_order: 1,
        ingested: false,
        children: [],
      },
    ],
  },
  {
    node_id: "d",
    title: "第二章",
    parent_id: null,
    level: 1,
    sort_order: 1,
    ingested: false,
    children: [],
  },
];

describe("collectCheckedNodeIds", () => {
  it("returns checked ids in preorder", () => {
    expect(collectCheckedNodeIds(tree, ["c", "a", "d"])).toEqual(["a", "c", "d"]);
  });

  it("ignores unchecked ids", () => {
    expect(collectCheckedNodeIds(tree, ["b"])).toEqual(["b"]);
  });
});

describe("buildPrefillMetadata", () => {
  it("includes catalog and asset summary for prefill context", () => {
    const metadata = buildPrefillMetadata({
      preview: {
        title: "1.1 资质",
        content_md: "正文",
        content_type: "mixed",
        char_start: null,
        char_end: null,
        page_start: null,
        page_end: null,
        catalog_path: [{ node_id: "b", title: "1.1 资质", level: 2 }],
        assets: [{ asset_type: "table", asset_code: null, char_start: 0, raw_markdown: null, image_storage_url: null }],
      },
      documentName: "标书.docx",
      sourceType: "bid",
    });
    expect(metadata.chapter_title).toBe("1.1 资质");
    expect(metadata.file_name).toBe("标书.docx");
    expect(metadata.content_type_hint).toBe("mixed");
    expect(metadata.asset_summary).toMatchObject({ has_table: true, total: 1 });
  });
});

describe("buildAutoCreatePayload", () => {
  const preview: NodePreview = {
    title: "节点标题",
    content_md: "# 正文",
    content_type: "markdown",
    char_start: 10,
    char_end: 20,
    page_start: 1,
    page_end: 2,
    catalog_path: [{ node_id: "b", title: "1.1", level: 2 }],
    assets: [],
  };
  const prefill: PrefillResult = {
    title: "AI 标题",
    summary: "摘要",
    knowledge_type: "technical",
    content_type: "markdown",
    file_name: "标书.docx",
    block_type_code: "qualification_document",
    application_type_code: "preferred_reference",
    business_line_codes: ["general"],
    tags: ["tag1"],
    regions: [],
    status: "draft",
    security_level: "internal",
    review_status: "pending",
    is_template: false,
    template_type: null,
    qualification_info: "ISO9001|CERT-001|2024-01-01|2026-12-31",
    expire_date: "2026-12-31",
  };

  it("maps preview + prefill to create payload with force defaults", () => {
    const payload = buildAutoCreatePayload({
      docId: "doc-1",
      nodeId: "b",
      preview,
      prefill,
      documentName: "标书.docx",
      sourceType: "bid",
    });
    expect(payload).toMatchObject({
      doc_id: "doc-1",
      primary_node_id: "b",
      title: "AI 标题",
      content: "# 正文",
      summary: "摘要",
      catalog_path: preview.catalog_path,
      qualification_info: "ISO9001|CERT-001|2024-01-01|2026-12-31",
      expire_date: "2026-12-31",
      block_type_code: "qualification_document",
      application_type_code: "preferred_reference",
      business_line_codes: ["general"],
    });
  });

  it("falls back to preview title when prefill title empty", () => {
    const payload = buildAutoCreatePayload({
      docId: "doc-1",
      nodeId: "b",
      preview,
      prefill: { ...prefill, title: "" },
    });
    expect(payload.title).toBe("节点标题");
  });

  it("normalizes invalid expire_date to null", () => {
    const payload = buildAutoCreatePayload({
      docId: "doc-1",
      nodeId: "b",
      preview,
      prefill: { ...prefill, expire_date: "invalid" },
    });
    expect(payload.expire_date).toBeNull();
  });
});

describe("normalizeOptionalDate", () => {
  it("accepts ISO dates and rejects empty or malformed values", async () => {
    const { normalizeOptionalDate } = await import("./batchIngestUtils");
    expect(normalizeOptionalDate("2024-06-26")).toBe("2024-06-26");
    expect(normalizeOptionalDate("")).toBeNull();
    expect(normalizeOptionalDate("  ")).toBeNull();
    expect(normalizeOptionalDate("2024/06/26")).toBeNull();
    expect(normalizeOptionalDate(null)).toBeNull();
  });
});

describe("withRetry", () => {
  it("retries once on failure", async () => {
    let calls = 0;
    const result = await withRetry(async () => {
      calls += 1;
      if (calls === 1) throw new Error("fail");
      return "ok";
    });
    expect(result).toBe("ok");
    expect(calls).toBe(2);
  });

  it("throws after second failure", async () => {
    await expect(
      withRetry(async () => {
        throw new Error("always fail");
      }),
    ).rejects.toThrow("always fail");
  });
});
