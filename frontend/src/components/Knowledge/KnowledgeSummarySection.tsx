import { Collapse, Typography } from "antd";
import type { ImageExtractionFields } from "./imageExtractionUtils";
import { buildCoreImageSummaryLines, isCoreImageAsset } from "./imageExtractionUtils";

const { Text, Paragraph } = Typography;

interface KnowledgeSummarySectionProps {
  summary: string | null | undefined;
  imageAssets: ImageExtractionFields[];
}

export default function KnowledgeSummarySection({ summary, imageAssets }: KnowledgeSummarySectionProps) {
  const coreLines = buildCoreImageSummaryLines(imageAssets);
  const hasCoreImages = imageAssets.some(isCoreImageAsset);

  return (
    <div>
      <Paragraph style={{ marginBottom: hasCoreImages && coreLines.length ? 8 : 0 }}>
        {summary?.trim() || "-"}
      </Paragraph>
      {hasCoreImages && coreLines.length ? (
        <Collapse
          ghost
          size="small"
          style={{
            marginTop: 4,
            background: "#f6ffed",
            border: "1px solid #b7eb8f",
            borderRadius: 6,
          }}
          items={[
            {
              key: "core-images",
              label: (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  图片核心信息（已纳入摘要参考）
                </Text>
              ),
              children: (
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {coreLines.map((line, index) => (
                    <li key={index} style={{ marginBottom: 4 }}>
                      <Text style={{ fontSize: 13 }}>{line}</Text>
                    </li>
                  ))}
                </ul>
              ),
            },
          ]}
        />
      ) : null}
    </div>
  );
}
