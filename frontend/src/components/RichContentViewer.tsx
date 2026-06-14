import { Empty, Typography } from "antd";

interface ContentBlock {
  type: string;
  text?: string;
  asset_id?: string | null;
  fallback?: string;
  alt?: string;
}

interface Props {
  kbId: string;
  content?: string | null;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function parseBlocks(raw?: string | null): { format: string; blocks: ContentBlock[]; plain?: string } {
  if (!raw) return { format: "plain", blocks: [], plain: "" };
  try {
    const payload = JSON.parse(raw);
    if (payload?.format === "blocks_v1" && Array.isArray(payload.blocks)) {
      return { format: "blocks_v1", blocks: payload.blocks };
    }
  } catch {
    /* plain */
  }
  return { format: "plain", blocks: [], plain: raw };
}

export default function RichContentViewer({ kbId, content }: Props) {
  const doc = parseBlocks(content);
  if (doc.format === "plain") {
    const text = (doc.plain ?? "").trim();
    return text ? (
      <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{text}</Typography.Paragraph>
    ) : (
      <Empty description="暂无正文" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    );
  }
  if (doc.blocks.length === 0) {
    return <Empty description="暂无正文" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {doc.blocks.map((block, idx) => {
        if (block.type === "paragraph" || block.type === "table") {
          return (
            <Typography.Paragraph key={idx} style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
              {block.text}
            </Typography.Paragraph>
          );
        }
        if (block.type === "image") {
          if (!block.asset_id) {
            return (
              <Typography.Text key={idx} type="secondary">
                {block.fallback ?? "[image]"}
              </Typography.Text>
            );
          }
          const src = `${API_BASE}/api/v1/kbs/${kbId}/media/${block.asset_id}`;
          return (
            <img
              key={idx}
              src={src}
              alt={block.alt ?? "image"}
              style={{ maxWidth: "100%", height: "auto" }}
            />
          );
        }
        return null;
      })}
    </div>
  );
}
