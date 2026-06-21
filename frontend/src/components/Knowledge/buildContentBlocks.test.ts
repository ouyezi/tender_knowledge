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
