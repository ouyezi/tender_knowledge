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
  image_caption?: string | null;
  image_ocr_text?: string | null;
  extracted_facts?: Record<string, unknown> | null;
  llm_summary?: string | null;
}

export type ContentBlock =
  | { type: "text"; content: string }
  | { type: "asset"; asset: KnowledgeAssetLike };

export interface BuildContentBlocksInput {
  contentMd: string;
  assets: KnowledgeAssetLike[];
  sectionCharStart?: number | null;
  sectionCharEnd?: number | null;
}

interface PositionedAsset {
  asset: KnowledgeAssetLike;
  relativeOffset: number;
}

function normalizeTableMarkdown(text: string): string {
  return text
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .join("\n");
}

function tableAlreadyInlineInContent(raw: string, contentMd: string): boolean {
  const normalized = normalizeTableMarkdown(raw);
  return Boolean(normalized && contentMd.includes(normalized));
}

function assetVisibleInContent(asset: KnowledgeAssetLike, contentMd: string): boolean {
  if (asset.asset_type === "table") {
    const raw = (asset.raw_markdown || "").trim();
    if (!raw) {
      return false;
    }
    if (tableAlreadyInlineInContent(raw, contentMd)) {
      return false;
    }
    const header = raw.split("\n", 1)[0].trim();
    if (header.length >= 3) {
      return contentMd.includes(header);
    }
    return contentMd.includes(raw);
  }
  if (asset.asset_type === "image") {
    const raw = (asset.raw_markdown || "").trim();
    if (raw && contentMd.includes(raw)) {
      return false;
    }
    const storageUrl = (asset.image_storage_url || "").trim();
    if (storageUrl && contentMd.includes(storageUrl)) {
      return false;
    }
    const filename = storageUrl ? storageUrl.split("/").pop() || "" : "";
    if (filename && contentMd.includes(filename)) {
      return false;
    }
  }
  return true;
}

function assetDedupeKey(asset: KnowledgeAssetLike): string {
  if (asset.asset_type === "table") {
    return [
      asset.asset_type,
      asset.char_start,
      asset.char_end,
      normalizeTableMarkdown(asset.raw_markdown || ""),
    ].join("|");
  }
  if (asset.asset_type === "image") {
    return [
      asset.asset_type,
      asset.char_start,
      asset.char_end,
      asset.image_storage_url || "",
      asset.raw_markdown || "",
    ].join("|");
  }
  return [asset.asset_type, asset.char_start, asset.char_end, asset.id].join("|");
}

function filterAssetsForContent(assets: KnowledgeAssetLike[], contentMd: string): KnowledgeAssetLike[] {
  if (!contentMd.trim()) {
    return [];
  }
  const seen = new Set<string>();
  const filtered: KnowledgeAssetLike[] = [];
  for (const asset of assets) {
    if (!assetVisibleInContent(asset, contentMd)) {
      continue;
    }
    const key = assetDedupeKey(asset);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    filtered.push(asset);
  }
  return filtered;
}

function toRelativeOffset(
  asset: KnowledgeAssetLike,
  sectionCharStart: number | null | undefined,
  sectionCharEnd: number | null | undefined,
  contentLength: number,
): number | null {
  if (asset.char_start === null || asset.char_start === undefined) {
    return null;
  }
  if (sectionCharStart === null || sectionCharStart === undefined) {
    return null;
  }
  if (
    sectionCharEnd !== null &&
    sectionCharEnd !== undefined &&
    asset.char_end !== null &&
    asset.char_end !== undefined &&
    asset.char_end > sectionCharEnd
  ) {
    return null;
  }
  const relative = asset.char_start - sectionCharStart;
  if (relative < 0 || relative > contentLength) {
    return null;
  }
  return relative;
}

export function buildContentBlocks(input: BuildContentBlocksInput): ContentBlock[] {
  const { contentMd, sectionCharStart, sectionCharEnd } = input;
  const assets = filterAssetsForContent(input.assets, contentMd);
  const positioned: PositionedAsset[] = [];
  const unpositioned: KnowledgeAssetLike[] = [];

  for (const asset of assets) {
    if (asset.char_start === null || asset.char_start === undefined) {
      unpositioned.push(asset);
      continue;
    }
    const relativeOffset = toRelativeOffset(asset, sectionCharStart, sectionCharEnd, contentMd.length);
    if (relativeOffset === null) {
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
