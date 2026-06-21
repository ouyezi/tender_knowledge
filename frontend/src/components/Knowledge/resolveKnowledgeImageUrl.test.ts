import { describe, expect, it } from "vitest";
import { resolveImageRefToMediaUrl, resolveMarkdownImageSrc } from "./resolveKnowledgeImageUrl";

describe("resolveKnowledgeImageUrl", () => {
  const imageRefMap = {
    "images/docx-img-005.jpeg": "asset-uuid-1",
    "images/fig-1.png": "asset-uuid-2",
  };

  it("resolves image refs via basename fallback", () => {
    expect(resolveImageRefToMediaUrl("kb-1", "images/docx-img-005.jpeg", imageRefMap)).toBe(
      "/api/v1/kbs/kb-1/media/asset-uuid-1",
    );
    expect(resolveImageRefToMediaUrl("kb-1", "docx-img-005.jpeg", imageRefMap)).toBe(
      "/api/v1/kbs/kb-1/media/asset-uuid-1",
    );
  });

  it("resolves markdown image src to absolute api url", () => {
    expect(resolveMarkdownImageSrc("images/docx-img-005.jpeg", "kb-1", imageRefMap)).toBe(
      "/api/v1/kbs/kb-1/media/asset-uuid-1",
    );
    expect(resolveMarkdownImageSrc("/api/v1/kbs/kb-1/media/asset-uuid-2", "kb-1", imageRefMap)).toBe(
      "/api/v1/kbs/kb-1/media/asset-uuid-2",
    );
  });
});
