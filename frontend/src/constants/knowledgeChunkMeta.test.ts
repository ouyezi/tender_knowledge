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
