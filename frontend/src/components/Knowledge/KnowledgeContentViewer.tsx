import { Collapse, Segmented, Space } from "antd";
import { Children, cloneElement, isValidElement, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getAssetTypeLabel } from "../../constants/knowledgeChunkMeta";
import { buildContentBlocks, type KnowledgeAssetLike } from "./buildContentBlocks";
import KnowledgeImageWithExtraction from "./KnowledgeImageWithExtraction";
import { renderKnowledgeAsset } from "./renderKnowledgeAsset";
import { resolveMarkdownImageSrc, toAbsoluteMediaUrl } from "./resolveKnowledgeImageUrl";

export type ContentViewMode = "preview" | "source";

interface KnowledgeContentViewerProps {
  contentMd: string;
  assets: KnowledgeAssetLike[];
  sectionCharStart?: number | null;
  sectionCharEnd?: number | null;
  showModeToggle?: boolean;
  defaultMode?: ContentViewMode;
  kbId?: string;
  imageRefMap?: Record<string, string>;
  showImageExtraction?: boolean;
}

function extractMediaAssetId(url: string): string | null {
  const match = url.match(/\/media\/([0-9a-fA-F-]{36})/);
  return match?.[1] ?? null;
}

function withIndexedChildKeys(children: ReactNode, prefix: string): ReactNode {
  return Children.toArray(children).map((child, index) =>
    isValidElement(child) ? cloneElement(child, { key: `${prefix}-${index}` }) : child,
  );
}

export default function KnowledgeContentViewer({
  contentMd,
  assets,
  sectionCharStart,
  sectionCharEnd,
  showModeToggle = true,
  defaultMode = "preview",
  kbId,
  imageRefMap,
  showImageExtraction = false,
}: KnowledgeContentViewerProps) {
  const [mode, setMode] = useState<ContentViewMode>(defaultMode);

  const imageAssetByUrl = useMemo(() => {
    const byUrl = new Map<string, KnowledgeAssetLike>();
    const byMediaId = new Map<string, KnowledgeAssetLike>();
    for (const asset of assets) {
      if (asset.asset_type !== "image" || !asset.image_storage_url) {
        continue;
      }
      const absoluteUrl = toAbsoluteMediaUrl(asset.image_storage_url);
      byUrl.set(absoluteUrl, asset);
      byUrl.set(asset.image_storage_url, asset);
      const mediaId = extractMediaAssetId(absoluteUrl) ?? extractMediaAssetId(asset.image_storage_url);
      if (mediaId) {
        byMediaId.set(mediaId, asset);
      }
    }
    return { byUrl, byMediaId };
  }, [assets]);

  const blocks = useMemo(
    () => buildContentBlocks({ contentMd, assets, sectionCharStart, sectionCharEnd }),
    [assets, contentMd, sectionCharStart, sectionCharEnd],
  );

  const markdownComponents = useMemo(
    () => ({
      tr: ({ children, ...props }: { children?: ReactNode }) => (
        <tr {...props}>{withIndexedChildKeys(children, "md-cell")}</tr>
      ),
      img: ({ src, alt }: { src?: string; alt?: string }) => {
        const resolvedSrc = resolveMarkdownImageSrc(src, kbId, imageRefMap);
        if (!resolvedSrc) {
          return <span style={{ color: "#999" }}>[图片无法加载]</span>;
        }
        const absoluteSrc = toAbsoluteMediaUrl(resolvedSrc);
        const mediaId = extractMediaAssetId(absoluteSrc) ?? extractMediaAssetId(resolvedSrc);
        const matchedAsset =
          imageAssetByUrl.byUrl.get(absoluteSrc) ??
          imageAssetByUrl.byUrl.get(resolvedSrc) ??
          (mediaId ? imageAssetByUrl.byMediaId.get(mediaId) : undefined);
        if (showImageExtraction) {
          return (
            <KnowledgeImageWithExtraction src={absoluteSrc} alt={alt ?? "image"} asset={matchedAsset} />
          );
        }
        return (
          <img
            src={absoluteSrc}
            alt={alt ?? "image"}
            style={{ maxWidth: "100%", border: "1px solid #f0f0f0", borderRadius: 6 }}
          />
        );
      },
    }),
    [imageAssetByUrl, imageRefMap, kbId, showImageExtraction],
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
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {block.content}
                  </ReactMarkdown>
                </div>
              );
            }
            return (
              <div key={`asset-${block.asset.id}`}>
                {renderKnowledgeAsset(block.asset, { showExtraction: showImageExtraction })}
              </div>
            );
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
