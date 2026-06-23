import { FileSearchOutlined } from "@ant-design/icons";
import { Button, Descriptions, Empty, Modal, Tag, Tooltip } from "antd";
import { useState } from "react";
import { getFieldLabel } from "../../constants/knowledgeChunkMeta";
import {
  formatExtractedFacts,
  getImageInformationRole,
  hasImageExtraction,
  type ImageExtractionFields,
} from "./imageExtractionUtils";

interface KnowledgeImageWithExtractionProps {
  src: string;
  alt?: string;
  asset?: ImageExtractionFields;
}

function roleLabel(role: "core" | "auxiliary" | null): string | null {
  if (role === "core") {
    return "核心信息";
  }
  if (role === "auxiliary") {
    return "辅助信息";
  }
  return null;
}

export default function KnowledgeImageWithExtraction({
  src,
  alt,
  asset,
}: KnowledgeImageWithExtractionProps) {
  const [open, setOpen] = useState(false);
  const extraction = asset ?? {};
  const role = getImageInformationRole(extraction);
  const roleText = roleLabel(role);

  return (
    <>
      <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
        <img
          src={src}
          alt={alt ?? "image"}
          style={{ maxWidth: "100%", border: "1px solid #f0f0f0", borderRadius: 6, display: "block" }}
        />
        <Tooltip title="查看图片内容提取信息">
          <Button
            type="primary"
            size="small"
            icon={<FileSearchOutlined />}
            aria-label="查看图片内容提取信息"
            onClick={() => setOpen(true)}
            style={{
              position: "absolute",
              top: 8,
              right: 8,
              boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
            }}
          >
            提取信息
          </Button>
        </Tooltip>
      </div>

      <Modal
        title="图片内容提取信息"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={640}
      >
        {!hasImageExtraction(extraction) ? (
          <Empty
            description={
              asset
                ? "暂无提取信息，请对该知识块执行「构建索引」或「重新索引」"
                : "暂无提取信息（图片资产未关联，请重新索引后刷新详情）"
            }
          />
        ) : (
          <>
            {roleText ? (
              <Tag color={role === "core" ? "blue" : "default"} style={{ marginBottom: 12 }}>
                {roleText}
              </Tag>
            ) : null}
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label={getFieldLabel("image_caption")}>
                {extraction.image_caption?.trim() || "-"}
              </Descriptions.Item>
              <Descriptions.Item label={getFieldLabel("image_ocr_text")}>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                  {extraction.image_ocr_text?.trim() || "-"}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="结构化事实">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                  {formatExtractedFacts(extraction.extracted_facts) || "-"}
                </pre>
              </Descriptions.Item>
              {extraction.llm_summary?.trim() ? (
                <Descriptions.Item label={getFieldLabel("llm_summary")}>
                  {extraction.llm_summary}
                </Descriptions.Item>
              ) : null}
            </Descriptions>
          </>
        )}
      </Modal>
    </>
  );
}
