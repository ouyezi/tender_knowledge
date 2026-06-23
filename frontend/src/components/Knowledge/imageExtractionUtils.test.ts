import { describe, expect, it } from "vitest";
import {
  buildCoreImageSummaryLines,
  formatExtractedFacts,
  getImageInformationRole,
  hasImageExtraction,
  isCoreImageAsset,
} from "./imageExtractionUtils";

describe("imageExtractionUtils", () => {
  it("detects extraction presence", () => {
    expect(hasImageExtraction({})).toBe(false);
    expect(hasImageExtraction({ image_caption: "证书" })).toBe(true);
  });

  it("reads information_role from extracted_facts", () => {
    expect(getImageInformationRole({ extracted_facts: { information_role: "core" } })).toBe("core");
    expect(getImageInformationRole({ extracted_facts: { information_role: "auxiliary" } })).toBe("auxiliary");
  });

  it("treats auxiliary role as non-core", () => {
    expect(
      isCoreImageAsset({
        extracted_facts: { information_role: "auxiliary" },
        image_ocr_text: "ISO9001 质量管理体系认证证书",
      }),
    ).toBe(false);
  });

  it("infers core image from cert keywords", () => {
    expect(isCoreImageAsset({ image_caption: "ISO9001 认证证书" })).toBe(true);
    expect(isCoreImageAsset({ image_caption: "门店外观照片" })).toBe(false);
  });

  it("formats extracted facts for display", () => {
    const text = formatExtractedFacts({
      cert_name: "ISO9001",
      information_role: "core",
      confidence: "high",
    });
    expect(text).toContain("证书名称：ISO9001");
    expect(text).not.toContain("information_role");
  });

  it("builds summary lines only for core images", () => {
    const lines = buildCoreImageSummaryLines([
      { image_caption: "商品展示图", extracted_facts: { information_role: "auxiliary" } },
      { image_caption: "营业执照", image_ocr_text: "统一社会信用代码" },
    ]);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain("营业执照");
  });
});
