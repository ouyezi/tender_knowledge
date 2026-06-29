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
    expect(getFieldLabel("expire_date_from")).toBe("失效日期起");
    expect(getFieldLabel("block_type_label")).toBe("块类型");
  });

  it("labels qualification_info", () => {
    expect(getFieldLabel("qualification_info")).toBe("资质信息");
  });

  it("falls back to raw field name for unknown fields", () => {
    expect(getFieldLabel("unknown_field")).toBe("unknown_field");
  });

  it("returns Chinese enum labels", () => {
    expect(getEnumLabel("knowledge_type", "fact")).toBe("事实");
    expect(getEnumLabel("knowledge_type", "certificate")).toBe("证书");
    expect(getEnumLabel("status", "draft")).toBe("草稿");
    expect(getEnumLabel("source_type", "qualification")).toBe("资质");
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

  it("returns sync status enum labels", () => {
    expect(getEnumLabel("sync_status", "pending")).toBe("待同步");
    expect(getEnumLabel("sync_status", "synced")).toBe("已同步");
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
