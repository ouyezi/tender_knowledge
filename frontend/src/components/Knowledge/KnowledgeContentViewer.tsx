import { Collapse, Segmented, Space } from "antd";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getAssetTypeLabel } from "../../constants/knowledgeChunkMeta";
import { buildContentBlocks, type KnowledgeAssetLike } from "./buildContentBlocks";
import { renderKnowledgeAsset } from "./renderKnowledgeAsset";
import { resolveMarkdownImageSrc } from "./resolveKnowledgeImageUrl";

export type ContentViewMode = "preview" | "source";

interface KnowledgeContentViewerProps {
  contentMd: string;
  assets: KnowledgeAssetLike[];
  sectionCharStart?: number | null;
  showModeToggle?: boolean;
  defaultMode?: ContentViewMode;
  kbId?: string;
  imageRefMap?: Record<string, string>;
}

export default function KnowledgeContentViewer({
  contentMd,
  assets,
  sectionCharStart,
  showModeToggle = true,
  defaultMode = "preview",
  kbId,
  imageRefMap,
}: KnowledgeContentViewerProps) {
  const [mode, setMode] = useState<ContentViewMode>(defaultMode);

  const blocks = useMemo(
    () => buildContentBlocks({ contentMd, assets, sectionCharStart }),
    [assets, contentMd, sectionCharStart],
  );

  const markdownComponents = useMemo(
    () => ({
      img: ({ src, alt }: { src?: string; alt?: string }) => {
        const resolvedSrc = resolveMarkdownImageSrc(src, kbId, imageRefMap);
        if (!resolvedSrc) {
          return <span style={{ color: "#999" }}>[图片无法加载]</span>;
        }
        return (
          <img
            src={resolvedSrc}
            alt={alt ?? "image"}
            style={{ maxWidth: "100%", border: "1px solid #f0f0f0", borderRadius: 6 }}
          />
        );
      },
    }),
    [imageRefMap, kbId],
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
            return <div key={`asset-${block.asset.id}`}>{renderKnowledgeAsset(block.asset)}</div>;
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
