import { Descriptions, Drawer, Empty, Spin, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import RichContentViewer from "../../components/RichContentViewer";
import {
  getKnowledgeUnit,
  getManualAsset,
  getWiki,
  type KnowledgeUnitItem,
  type ManualAssetItem,
  type WikiItem,
} from "../../services/knowledgeAssets";

export type KnowledgeAssetType = "ku" | "wiki" | "manual_asset";

type KnowledgeDetail = KnowledgeUnitItem | WikiItem | ManualAssetItem;

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  published: { color: "success", label: "已发布" },
  draft: { color: "default", label: "草稿" },
  archived: { color: "default", label: "已归档" },
};

const SOURCE_TRACE_LABELS: Record<string, string> = {
  import_id: "导入 ID",
  candidate_id: "候选 ID",
  source_doc_id: "来源文档 ID",
  source_node_id: "来源节点 ID",
};

export interface KnowledgeDetailDrawerProps {
  kbId: string;
  open: boolean;
  assetType: KnowledgeAssetType;
  assetId?: string;
  onClose: () => void;
}

function renderSourceTrace(detail: KnowledgeDetail) {
  const traceEntries: Array<[string, string]> = [];
  if (detail.import_id) {
    traceEntries.push(["import_id", detail.import_id]);
  }
  if (detail.candidate_id) {
    traceEntries.push(["candidate_id", detail.candidate_id]);
  }
  if (detail.source_doc_id) {
    traceEntries.push(["source_doc_id", detail.source_doc_id]);
  }
  if ("source_node_id" in detail && detail.source_node_id) {
    traceEntries.push(["source_node_id", detail.source_node_id]);
  }

  if (traceEntries.length === 0) {
    return <Empty description="暂无来源追溯信息" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <Descriptions column={1} size="small" bordered>
      {traceEntries.map(([key, value]) => (
        <Descriptions.Item key={key} label={SOURCE_TRACE_LABELS[key] ?? key}>
          {value}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

function getAssetId(detail: KnowledgeDetail, assetType: KnowledgeAssetType): string {
  if (assetType === "ku" && "ku_id" in detail) {
    return detail.ku_id;
  }
  if (assetType === "wiki" && "wiki_id" in detail) {
    return detail.wiki_id;
  }
  if (assetType === "manual_asset" && "manual_asset_id" in detail) {
    return detail.manual_asset_id;
  }
  return "-";
}

function getTypeLabel(detail: KnowledgeDetail, assetType: KnowledgeAssetType): string {
  if (assetType === "ku" && "knowledge_type" in detail) {
    return detail.knowledge_type;
  }
  if (assetType === "wiki" && "wiki_type" in detail) {
    return detail.wiki_type ?? "-";
  }
  if (assetType === "manual_asset" && "asset_type" in detail) {
    return detail.asset_type;
  }
  return "-";
}

export default function KnowledgeDetailDrawer({
  kbId,
  open,
  assetType,
  assetId,
  onClose,
}: KnowledgeDetailDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<KnowledgeDetail>();

  const loadDetail = useCallback(async () => {
    if (!assetId) {
      setDetail(undefined);
      return;
    }
    setLoading(true);
    try {
      if (assetType === "ku") {
        setDetail(await getKnowledgeUnit(kbId, assetId));
      } else if (assetType === "wiki") {
        setDetail(await getWiki(kbId, assetId));
      } else {
        setDetail(await getManualAsset(kbId, assetId));
      }
    } catch {
      setDetail(undefined);
    } finally {
      setLoading(false);
    }
  }, [assetId, assetType, kbId]);

  useEffect(() => {
    if (!open || !assetId) {
      setDetail(undefined);
      return;
    }
    void loadDetail();
  }, [open, assetId, loadDetail]);

  const content =
    detail && "content" in detail ? (detail.content ?? undefined) : undefined;

  return (
    <Drawer
      title={detail?.title ?? "知识详情"}
      width={720}
      open={open}
      onClose={onClose}
      destroyOnHidden
    >
      {loading ? (
        <Spin />
      ) : detail ? (
        <>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="ID">{getAssetId(detail, assetType)}</Descriptions.Item>
            <Descriptions.Item label="状态">
              {(() => {
                const meta = STATUS_TAG[detail.status] ?? {
                  color: "default",
                  label: detail.status,
                };
                return <Tag color={meta.color}>{meta.label}</Tag>;
              })()}
            </Descriptions.Item>
            <Descriptions.Item label="类型">{getTypeLabel(detail, assetType)}</Descriptions.Item>
            <Descriptions.Item label="可检索">
              {detail.searchable ? "是" : "否"}
            </Descriptions.Item>
            {"usage_hint" in detail && detail.usage_hint ? (
              <Descriptions.Item label="使用提示" span={2}>
                {detail.usage_hint}
              </Descriptions.Item>
            ) : null}
            {detail.summary ? (
              <Descriptions.Item label="摘要" span={2}>
                {detail.summary}
              </Descriptions.Item>
            ) : null}
            {assetType === "manual_asset" &&
            "storage_path" in detail &&
            detail.storage_path ? (
              <Descriptions.Item label="存储路径" span={2}>
                <Typography.Text copyable>{detail.storage_path}</Typography.Text>
              </Descriptions.Item>
            ) : null}
          </Descriptions>

          <Typography.Title level={5}>来源追溯</Typography.Title>
          <div style={{ marginBottom: 16 }}>{renderSourceTrace(detail)}</div>

          <Typography.Title level={5}>正文</Typography.Title>
          <div
            style={{
              padding: 12,
              background: "#fafafa",
              borderRadius: 6,
              maxHeight: 480,
              overflow: "auto",
            }}
          >
            <RichContentViewer kbId={kbId} content={content} />
          </div>
        </>
      ) : (
        <Empty description="未找到知识详情" />
      )}
    </Drawer>
  );
}
