import { Button, Card, Descriptions, Drawer, Empty, Space, Spin, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getKnowledgeChunk, type ChunkAssetDetail, type KnowledgeChunkDetail } from "../../services/knowledgeChunks";

const { Text } = Typography;

interface KnowledgeChunkDetailDrawerProps {
  kbId: string;
  chunkId?: number;
  open: boolean;
  onClose: () => void;
  onOpenChunk: (chunkId: number) => void;
}

const EMBEDDING_STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: "warning", label: "待处理" },
  ready: { color: "success", label: "已完成" },
  failed: { color: "error", label: "失败" },
};

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function renderPrimitive(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "object") {
    return (
      <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(value, null, 2)}</pre>
    );
  }
  return String(value);
}

function parseMarkdownTable(raw?: string | null): { headers: string[]; rows: string[][] } | null {
  if (!raw) {
    return null;
  }
  const lines = raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) {
    return null;
  }
  const separator = lines[1].replace(/\|/g, "").replace(/[-:\s]/g, "");
  if (separator.length > 0) {
    return null;
  }
  const parseLine = (line: string) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  const headers = parseLine(lines[0]);
  const rows = lines.slice(2).map(parseLine).filter((row) => row.length > 0);
  return { headers, rows };
}

function renderAssetPreview(asset: ChunkAssetDetail) {
  if (asset.asset_type === "image" && asset.image_storage_url) {
    return (
      <img
        src={asset.image_storage_url}
        alt={asset.asset_code ?? `asset-${asset.id}`}
        style={{ maxWidth: "100%", border: "1px solid #f0f0f0", borderRadius: 6 }}
      />
    );
  }
  if (asset.asset_type === "table") {
    const table = parseMarkdownTable(asset.raw_markdown);
    if (table) {
      return (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {table.headers.map((header) => (
                  <th
                    key={header}
                    style={{
                      border: "1px solid #f0f0f0",
                      textAlign: "left",
                      padding: 8,
                      background: "#fafafa",
                    }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={`row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`cell-${rowIndex}-${cellIndex}`} style={{ border: "1px solid #f0f0f0", padding: 8 }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
  }
  return (
    <pre style={{ margin: 0, whiteSpace: "pre-wrap", background: "#fafafa", borderRadius: 6, padding: 12 }}>
      {asset.raw_markdown || "(无可预览内容)"}
    </pre>
  );
}

function BaseInfo({ detail, onOpenChunk }: { detail: KnowledgeChunkDetail; onOpenChunk: (chunkId: number) => void }) {
  const embeddingMeta =
    EMBEDDING_STATUS_META[detail.embedding_status] ?? {
      color: "default",
      label: detail.embedding_status || "-",
    };

  return (
    <Descriptions title="基础信息" bordered column={2} size="small">
      <Descriptions.Item label="id">{detail.id}</Descriptions.Item>
      <Descriptions.Item label="kb_id">{detail.kb_id}</Descriptions.Item>
      <Descriptions.Item label="knowledge_code">{detail.knowledge_code}</Descriptions.Item>
      <Descriptions.Item label="version">{detail.version}</Descriptions.Item>
      <Descriptions.Item label="previous_version_id">{detail.previous_version_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="is_latest">{String(detail.is_latest)}</Descriptions.Item>
      <Descriptions.Item label="title">{detail.title || "-"}</Descriptions.Item>
      <Descriptions.Item label="summary">{detail.summary || "-"}</Descriptions.Item>
      <Descriptions.Item label="knowledge_type">{detail.knowledge_type || "-"}</Descriptions.Item>
      <Descriptions.Item label="content_type">{detail.content_type || "-"}</Descriptions.Item>
      <Descriptions.Item label="doc_id">{detail.doc_id}</Descriptions.Item>
      <Descriptions.Item label="file_name">{detail.file_name || "-"}</Descriptions.Item>
      <Descriptions.Item label="source_type">{detail.source_type || "-"}</Descriptions.Item>
      <Descriptions.Item label="project_name">{detail.project_name || "-"}</Descriptions.Item>
      <Descriptions.Item label="page_start">{detail.page_start ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="page_end">{detail.page_end ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="char_start">{detail.char_start ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="char_end">{detail.char_end ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="primary_node_id">{detail.primary_node_id}</Descriptions.Item>
      <Descriptions.Item label="parent_id">{detail.parent_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="category">{detail.category || "-"}</Descriptions.Item>
      <Descriptions.Item label="status">{detail.status || "-"}</Descriptions.Item>
      <Descriptions.Item label="security_level">{detail.security_level || "-"}</Descriptions.Item>
      <Descriptions.Item label="review_status">{detail.review_status || "-"}</Descriptions.Item>
      <Descriptions.Item label="owner">{detail.owner || "-"}</Descriptions.Item>
      <Descriptions.Item label="quote_mode">{detail.quote_mode || "-"}</Descriptions.Item>
      <Descriptions.Item label="template_type">{detail.template_type || "-"}</Descriptions.Item>
      <Descriptions.Item label="retrieval_weight">{detail.retrieval_weight}</Descriptions.Item>
      <Descriptions.Item label="edit_distance_avg">{detail.edit_distance_avg ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="token_count">{detail.token_count}</Descriptions.Item>
      <Descriptions.Item label="content_hash">{detail.content_hash || "-"}</Descriptions.Item>
      <Descriptions.Item label="has_children">{String(detail.has_children)}</Descriptions.Item>
      <Descriptions.Item label="children_count">{detail.children_count}</Descriptions.Item>
      <Descriptions.Item label="is_template">{String(detail.is_template)}</Descriptions.Item>
      <Descriptions.Item label="is_immutable">{String(detail.is_immutable)}</Descriptions.Item>
      <Descriptions.Item label="winning_flag">{String(detail.winning_flag)}</Descriptions.Item>
      <Descriptions.Item label="need_parent_context">{String(detail.need_parent_context)}</Descriptions.Item>
      <Descriptions.Item label="issue_date">{detail.issue_date || "-"}</Descriptions.Item>
      <Descriptions.Item label="expire_date">{detail.expire_date || "-"}</Descriptions.Item>
      <Descriptions.Item label="create_time">{formatDateTime(detail.create_time)}</Descriptions.Item>
      <Descriptions.Item label="update_time">{formatDateTime(detail.update_time)}</Descriptions.Item>
      <Descriptions.Item label="embedding_status">
        <Tag color={embeddingMeta.color}>{embeddingMeta.label}</Tag>
      </Descriptions.Item>
      <Descriptions.Item label="previous_version">
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
    </Descriptions>
  );
}

export default function KnowledgeChunkDetailDrawer({
  kbId,
  chunkId,
  open,
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
  }, [chunkId, loadDetail, open]);

  const catalogPathText = useMemo(() => JSON.stringify(detail?.catalog_path ?? [], null, 2), [detail?.catalog_path]);
  const tagsText = useMemo(() => JSON.stringify(detail?.tags ?? [], null, 2), [detail?.tags]);
  const productsText = useMemo(() => JSON.stringify(detail?.products ?? [], null, 2), [detail?.products]);
  const industriesText = useMemo(() => JSON.stringify(detail?.industries ?? [], null, 2), [detail?.industries]);
  const customerTypesText = useMemo(
    () => JSON.stringify(detail?.customer_types ?? [], null, 2),
    [detail?.customer_types],
  );
  const regionsText = useMemo(() => JSON.stringify(detail?.regions ?? [], null, 2), [detail?.regions]);
  const variablesText = useMemo(() => JSON.stringify(detail?.variables ?? [], null, 2), [detail?.variables]);
  const exclusionRulesText = useMemo(
    () => JSON.stringify(detail?.exclusion_rules ?? [], null, 2),
    [detail?.exclusion_rules],
  );

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
          <BaseInfo detail={detail} onOpenChunk={onOpenChunk} />

          <Card title="内容">
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{detail.content || "-"}</pre>
          </Card>

          <Card title="结构字段">
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="catalog_path">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{catalogPathText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="tags">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{tagsText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="products">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{productsText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="industries">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{industriesText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="customer_types">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{customerTypesText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="regions">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{regionsText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="variables">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{variablesText}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="exclusion_rules">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{exclusionRulesText}</pre>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title={`关联资产 (${detail.assets.length})`}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {detail.assets.map((asset) => (
                <Card
                  key={asset.id}
                  size="small"
                  title={`${asset.asset_type} #${asset.id}`}
                  bodyStyle={{ overflow: "auto" }}
                >
                  <Descriptions bordered size="small" column={2} style={{ marginBottom: 12 }}>
                    <Descriptions.Item label="asset_code">{asset.asset_code || "-"}</Descriptions.Item>
                    <Descriptions.Item label="chunk_id">{asset.chunk_id ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label="page_start">{asset.page_start ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label="page_end">{asset.page_end ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label="char_start">{asset.char_start ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label="char_end">{asset.char_end ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label="table_type">{asset.table_type || "-"}</Descriptions.Item>
                    <Descriptions.Item label="image_type">{asset.image_type || "-"}</Descriptions.Item>
                    <Descriptions.Item label="allow_row_filter">
                      {renderPrimitive(asset.allow_row_filter)}
                    </Descriptions.Item>
                    <Descriptions.Item label="required_with_text">
                      {renderPrimitive(asset.required_with_text)}
                    </Descriptions.Item>
                    <Descriptions.Item label="position_hint">{asset.position_hint || "-"}</Descriptions.Item>
                    <Descriptions.Item label="image_caption">{asset.image_caption || "-"}</Descriptions.Item>
                    <Descriptions.Item label="image_ocr_text" span={2}>
                      {asset.image_ocr_text || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label="llm_summary" span={2}>
                      {asset.llm_summary || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label="table_summary" span={2}>
                      {asset.table_summary || "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label="table_schema" span={2}>
                      {renderPrimitive(asset.table_schema)}
                    </Descriptions.Item>
                    <Descriptions.Item label="table_headers" span={2}>
                      {renderPrimitive(asset.table_headers)}
                    </Descriptions.Item>
                    <Descriptions.Item label="table_rows" span={2}>
                      {renderPrimitive(asset.table_rows)}
                    </Descriptions.Item>
                  </Descriptions>
                  {renderAssetPreview(asset)}
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
