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
    if (asset.char_start === null || asset.char_start === undefined) {
      unpositioned.push(asset);
      continue;
    }
    const relativeOffset = toRelativeOffset(asset, sectionCharStart, contentMd.length);
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
