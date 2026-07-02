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
        { id: 2, ...baseAsset, char_start: 110 },
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

  it("ignores assets that extend beyond section char_end", () => {
    const blocks = buildContentBlocks({
      contentMd: "法人代表身份证明",
      sectionCharStart: 6776,
      sectionCharEnd: 6915,
      assets: [
        {
          id: 7,
          ...baseAsset,
          asset_type: "table",
          char_start: 6814,
          char_end: 200845,
          raw_markdown: "| 指标 | 2019 |\n| --- | --- |",
        },
      ],
    });
    expect(blocks).toEqual([{ type: "text", content: "法人代表身份证明" }]);
  });

  it("filters table assets whose header is not present in section markdown", () => {
    const blocks = buildContentBlocks({
      contentMd: "## 法人代表身份证明\n\n兹证明王海锋同志为我单位法定代表人。",
      sectionCharStart: 100,
      sectionCharEnd: 250,
      assets: [
        {
          id: 8,
          ...baseAsset,
          asset_type: "table",
          char_start: 120,
          char_end: 180,
          raw_markdown: "| 指标 | 2019 |\n| --- | --- |",
        },
      ],
    });
    expect(blocks).toEqual([
      {
        type: "text",
        content: "## 法人代表身份证明\n\n兹证明王海锋同志为我单位法定代表人。",
      },
    ]);
  });

  it("does not duplicate table assets already present in section markdown", () => {
    const table = "| 员工痛点 | 消费场景少 |\n| --- | --- |\n| 使用体感差 | 无新意 |";
    const contentMd = `## 2.1 痛点\n\n${table}\n`;
    const blocks = buildContentBlocks({
      contentMd,
      sectionCharStart: 100,
      sectionCharEnd: 500,
      assets: [
        {
          id: 11,
          ...baseAsset,
          asset_type: "table",
          char_start: 115,
          char_end: 200,
          raw_markdown: table,
        },
        {
          id: 12,
          ...baseAsset,
          asset_type: "table",
          char_start: 115,
          char_end: 200,
          raw_markdown: table,
        },
      ],
    });
    expect(blocks).toEqual([{ type: "text", content: contentMd }]);
  });

  it("strips table-ref placeholders from preview text blocks", () => {
    const table = "|列A|列B|\n|---|---|\n|1|2|";
    const contentMd = `章节正文\n\n<!-- table-ref:tables/t0244.json -->\n${table}\n`;
    const blocks = buildContentBlocks({
      contentMd,
      sectionCharStart: 0,
      sectionCharEnd: contentMd.length,
      assets: [],
    });
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ type: "text" });
    if (blocks[0].type === "text") {
      expect(blocks[0].content).not.toContain("table-ref");
      expect(blocks[0].content).toContain(table);
    }
  });
});
