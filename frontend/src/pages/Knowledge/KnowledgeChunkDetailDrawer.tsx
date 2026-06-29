import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { DownOutlined, UpOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import KnowledgeContentViewer from "../../components/Knowledge/KnowledgeContentViewer";
import KnowledgeSummarySection from "../../components/Knowledge/KnowledgeSummarySection";
import { renderKnowledgeAsset } from "../../components/Knowledge/renderKnowledgeAsset";
import {
  formatBoolean,
  getAssetTypeLabel,
  getEnumLabel,
  getFieldLabel,
} from "../../constants/knowledgeChunkMeta";
import { getKnowledgeChunk, type ChunkAssetDetail, type KnowledgeChunkDetail } from "../../services/knowledgeChunks";

const { Text } = Typography;

interface KnowledgeChunkDetailDrawerProps {
  kbId: string;
  chunkId?: number;
  open: boolean;
  reloadKey?: number;
  onClose: () => void;
  onOpenChunk: (chunkId: number) => void;
}

const EMBEDDING_STATUS_COLORS: Record<string, string> = {
  pending: "warning",
  indexing: "processing",
  ready: "success",
  failed: "error",
  skipped: "default",
};

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function renderPrimitive(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "boolean") {
    return formatBoolean(value);
  }
  if (typeof value === "object") {
    return <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(value, null, 2)}</pre>;
  }
  return String(value);
}

function renderTagList(values?: string[]) {
  if (!values?.length) {
    return "-";
  }
  return (
    <Space size={[4, 4]} wrap>
      {values.map((value, index) => (
        <Tag key={`tag-${index}-${value}`}>{value || "-"}</Tag>
      ))}
    </Space>
  );
}

function renderQualificationInfo(value?: string | null) {
  const lines = (value || "")
    .split(";")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) {
    return "-";
  }
  return (
    <span style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
      {lines.join("\n")}
    </span>
  );
}

const DESCRIPTION_LABEL_STYLE = { width: 112, minWidth: 112, verticalAlign: "top" as const };
const DESCRIPTION_CONTENT_STYLE = { wordBreak: "break-word" as const };
const DESCRIPTION_STYLES = {
  label: DESCRIPTION_LABEL_STYLE,
  content: DESCRIPTION_CONTENT_STYLE,
};
const MERGED_DESCRIPTIONS_STYLE = { marginTop: -1 };

function CoreInfoSection({
  detail,
  catalogPathText,
  onOpenChunk,
}: {
  detail: KnowledgeChunkDetail;
  catalogPathText: string;
  onOpenChunk: (chunkId: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const imageAssets = detail.assets.filter((asset) => asset.asset_type === "image");

  useEffect(() => {
    setExpanded(false);
  }, [detail.id]);

  return (
    <Card title="核心信息" size="small">
      <Descriptions bordered column={2} size="small" styles={DESCRIPTION_STYLES}>
        <Descriptions.Item label={getFieldLabel("id")}>{detail.id}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("knowledge_code")}>{detail.knowledge_code}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("title")}>
          <Text strong ellipsis={{ tooltip: detail.title || "-" }} style={{ display: "block" }}>
            {detail.title || "-"}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("business_line_labels")}>
          {renderTagList(detail.business_line_labels)}
        </Descriptions.Item>
      </Descriptions>

      <Descriptions
        bordered
        column={1}
        size="small"
        style={MERGED_DESCRIPTIONS_STYLE}
        styles={DESCRIPTION_STYLES}
      >
        <Descriptions.Item label={getFieldLabel("summary")}>
          <KnowledgeSummarySection summary={detail.summary} imageAssets={imageAssets} />
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("qualification_info")}>
          {renderQualificationInfo(detail.qualification_info)}
        </Descriptions.Item>
      </Descriptions>

      <Descriptions
        bordered
        column={2}
        size="small"
        style={MERGED_DESCRIPTIONS_STYLE}
        styles={DESCRIPTION_STYLES}
      >
        <Descriptions.Item label={getFieldLabel("expire_date")}>
          <Space size={8}>
            <span>{detail.expire_date || "-"}</span>
            {detail.is_expired ? <Tag color="error">已过期</Tag> : null}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("update_time")}>{formatDateTime(detail.update_time)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("embedding_status")}>
          <Tag color={EMBEDDING_STATUS_COLORS[detail.embedding_status] ?? "default"}>
            {getEnumLabel("embedding_status", detail.embedding_status)}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("knowledge_type")}>
          {getEnumLabel("knowledge_type", detail.knowledge_type)}
        </Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 12, textAlign: "center" }}>
        <Button
          type="link"
          size="small"
          icon={expanded ? <UpOutlined /> : <DownOutlined />}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收起其它属性" : "展开其它属性"}
        </Button>
      </div>

      {expanded ? (
        <MoreInfo
          detail={detail}
          catalogPathText={catalogPathText}
          onOpenChunk={onOpenChunk}
        />
      ) : null}
    </Card>
  );
}

function MoreInfo({
  detail,
  catalogPathText,
  onOpenChunk,
}: {
  detail: KnowledgeChunkDetail;
  catalogPathText: string;
  onOpenChunk: (chunkId: number) => void;
}) {
  return (
    <>
      <Descriptions
        bordered
        column={2}
        size="small"
        style={{ marginTop: 12 }}
        styles={DESCRIPTION_STYLES}
      >
        <Descriptions.Item label={getFieldLabel("block_type_label")}>
          {detail.block_type_label || detail.block_type_code || "-"}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("application_type_label")}>
          {detail.application_type_label || detail.application_type_code || "-"}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("status")}>{getEnumLabel("status", detail.status)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("content_type")}>
          {getEnumLabel("content_type", detail.content_type)}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("file_name")}>{detail.file_name || "-"}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("review_status")}>
          {getEnumLabel("review_status", detail.review_status)}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("security_level")}>
          {getEnumLabel("security_level", detail.security_level)}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("owner")}>{detail.owner || "-"}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("version")}>{detail.version}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("is_latest")}>{formatBoolean(detail.is_latest)}</Descriptions.Item>
      </Descriptions>

      <Descriptions
        bordered
        column={1}
        size="small"
        style={MERGED_DESCRIPTIONS_STYLE}
        styles={DESCRIPTION_STYLES}
      >
        <Descriptions.Item label={getFieldLabel("previous_version")}>
          {detail.previous_version ? (
            <Space>
              <Text>{`${detail.previous_version.title} (v${detail.previous_version.version})`}</Text>
              <Button type="link" size="small" onClick={() => onOpenChunk(detail.previous_version!.id)}>
                查看上一版本
              </Button>
            </Space>
          ) : (
            "-"
          )}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("tags")}>{renderTagList(detail.tags)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("regions")}>{renderTagList(detail.regions)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("catalog_path")}>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{catalogPathText}</pre>
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("content_hash")}>{detail.content_hash || "-"}</Descriptions.Item>
      </Descriptions>

      <Descriptions
        bordered
        column={2}
        size="small"
        style={MERGED_DESCRIPTIONS_STYLE}
        styles={DESCRIPTION_STYLES}
      >
        <Descriptions.Item label={getFieldLabel("doc_id")}>{detail.doc_id}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("primary_node_id")}>{detail.primary_node_id}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("is_template")}>{formatBoolean(detail.is_template)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("template_type")}>
          {getEnumLabel("template_type", detail.template_type)}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("token_count")}>{detail.token_count}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("create_time")}>{formatDateTime(detail.create_time)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("kb_id")}>{detail.kb_id}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("previous_version_id")}>
          {detail.previous_version_id ?? "-"}
        </Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("has_children")}>{formatBoolean(detail.has_children)}</Descriptions.Item>
        <Descriptions.Item label={getFieldLabel("children_count")}>{detail.children_count}</Descriptions.Item>
      </Descriptions>
    </>
  );
}

export default function KnowledgeChunkDetailDrawer({
  kbId,
  chunkId,
  open,
  reloadKey = 0,
  onClose,
  onOpenChunk,
}: KnowledgeChunkDetailDrawerProps) {
  const [detail, setDetail] = useState<KnowledgeChunkDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const loadDetail = useCallback(
    async (targetChunkId?: number) => {
      if (!targetChunkId) {
        setDetail(null);
        return;
      }
      setLoading(true);
      try {
        const result = await getKnowledgeChunk(kbId, targetChunkId);
        setDetail(result);
      } catch (error) {
        message.error((error as Error).message);
        setDetail(null);
      } finally {
        setLoading(false);
      }
    },
    [kbId],
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    void loadDetail(chunkId);
  }, [chunkId, loadDetail, open, reloadKey]);

  useEffect(() => {
    if (!open || !detail || detail.embedding_status !== "indexing") {
      return;
    }
    const timer = window.setInterval(() => {
      void loadDetail(chunkId);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [chunkId, detail?.embedding_status, loadDetail, open]);

  const catalogPathText = useMemo(() => JSON.stringify(detail?.catalog_path ?? [], null, 2), [detail?.catalog_path]);
  const sectionCharStart = detail?.section_char_start ?? null;

  return (
    <Drawer
      title={detail ? `知识详情 #${detail.id}` : "知识详情"}
      width={980}
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      {loading ? (
        <div style={{ minHeight: 180, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Spin />
        </div>
      ) : null}

      {!loading && !detail ? <Empty description="未找到知识详情" /> : null}

      {!loading && detail ? (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {detail.is_expired ? (
            <Alert
              type="warning"
              showIcon
              message="该知识已过期"
              description="当前知识已超过失效日期，建议优先核验并更新内容后再使用。"
            />
          ) : null}

          <CoreInfoSection
            detail={detail}
            catalogPathText={catalogPathText}
            onOpenChunk={onOpenChunk}
          />

          <Card title={getFieldLabel("content")}>
            <KnowledgeContentViewer
              contentMd={detail.content || ""}
              assets={detail.assets}
              sectionCharStart={sectionCharStart}
              kbId={kbId}
              imageRefMap={detail.image_ref_map}
              showImageExtraction
            />
          </Card>

          <Card title={`关联资产 (${detail.assets.length})`}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {detail.assets.map((asset: ChunkAssetDetail) => (
                <Card
                  key={asset.id}
                  size="small"
                  title={`${getAssetTypeLabel(asset.asset_type)} #${asset.id}`}
                  styles={{ body: { overflow: "auto" } }}
                >
                  <Descriptions bordered size="small" column={2} style={{ marginBottom: 12 }}>
                    <Descriptions.Item label={getFieldLabel("asset_code")}>{asset.asset_code || "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("chunk_id")}>{asset.chunk_id ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("page_start")}>{asset.page_start ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("page_end")}>{asset.page_end ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("char_start")}>{asset.char_start ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("char_end")}>{asset.char_end ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("table_type")}>{asset.table_type || "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("image_type")}>{asset.image_type || "-"}</Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("allow_row_filter")}>
                      {renderPrimitive(asset.allow_row_filter)}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("required_with_text")}>
                      {renderPrimitive(asset.required_with_text)}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("position_hint")}>
                      {asset.position_hint || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("image_caption")}>
                      {asset.image_caption || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("image_ocr_text")} span={2}>
                      {asset.image_ocr_text || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("extracted_facts")} span={2}>
                      {renderPrimitive(asset.extracted_facts)}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("llm_summary")} span={2}>
                      {asset.llm_summary || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("table_summary")} span={2}>
                      {asset.table_summary || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("table_schema")} span={2}>
                      {renderPrimitive(asset.table_schema)}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("table_headers")} span={2}>
                      {renderPrimitive(asset.table_headers)}
                    </Descriptions.Item>
                    <Descriptions.Item label={getFieldLabel("table_rows")} span={2}>
                      {renderPrimitive(asset.table_rows)}
                    </Descriptions.Item>
                  </Descriptions>
                  {renderKnowledgeAsset(asset, { showExtraction: true })}
                </Card>
              ))}
              {!detail.assets.length ? <Empty description="暂无关联资产" /> : null}
            </Space>
          </Card>
        </Space>
      ) : null}
    </Drawer>
  );
}
