import { Alert, Button, Card, Descriptions, Drawer, Empty, Spin, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useKBContext } from "../../layout/KBContext";
import {
  getCandidate,
  listCandidates,
  type CandidateDetail,
  type CandidateListItem,
} from "../../services/candidates";

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  pending: { color: "warning", label: "待处理" },
  pending_confirm: { color: "processing", label: "待确认" },
  confirmed: { color: "success", label: "已确认" },
  rejected: { color: "default", label: "已拒绝" },
};

const SOURCE_CHANNEL_LABEL: Record<string, string> = {
  document: "文档",
  template: "模板",
  all: "全部",
};

const CANDIDATE_TYPE_LABEL: Record<string, string> = {
  ku: "知识单元",
  wiki: "Wiki",
};

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function renderSourceTraceDetail(trace?: CandidateDetail["source_trace"]) {
  if (!trace || Object.keys(trace).length === 0) {
    return <Empty description="暂无来源追溯信息" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  const entries = Object.entries(trace).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return (
    <Descriptions column={1} size="small" bordered>
      {entries.map(([key, value]) => (
        <Descriptions.Item key={key} label={key}>
          {String(value)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

export default function CandidateCenterPage() {
  const { selectedKbId } = useKBContext();
  const [items, setItems] = useState<CandidateListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>();
  const [detail, setDetail] = useState<CandidateDetail>();

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listCandidates(selectedKbId, { page, page_size: pageSize });
      setItems(result.items ?? []);
      setTotal(result.total ?? 0);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openDetail = useCallback(
    async (record: CandidateListItem) => {
      if (!selectedKbId) {
        return;
      }
      setSelectedCandidateId(record.candidate_id);
      setDetailOpen(true);
      setDetail(undefined);
      setDetailLoading(true);
      try {
        const next = await getCandidate(selectedKbId, record.candidate_id);
        setDetail(next);
      } catch (error) {
        setDetail({
          candidate_id: record.candidate_id,
          source_channel: record.source_channel,
          title: record.title,
          summary: record.summary,
          status: record.status,
          candidate_type: record.candidate_type,
          source_trace: record.source_trace,
          created_at: record.created_at,
        });
        message.warning(`详情加载失败，已展示列表摘要：${(error as Error).message}`);
      } finally {
        setDetailLoading(false);
      }
    },
    [selectedKbId],
  );

  const columns: ColumnsType<CandidateListItem> = useMemo(
    () => [
      {
        title: "标题",
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        render: (value: string) => value || "-",
      },
      {
        title: "类型",
        dataIndex: "candidate_type",
        key: "candidate_type",
        width: 120,
        render: (value: string) => CANDIDATE_TYPE_LABEL[value] ?? value ?? "-",
      },
      {
        title: "来源",
        dataIndex: "source_channel",
        key: "source_channel",
        width: 100,
        render: (value: string) => SOURCE_CHANNEL_LABEL[value] ?? value ?? "-",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (value: string) => {
          const meta = STATUS_TAG[value] ?? { color: "default", label: value || "-" };
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        render: (value: string) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        render: (_value, record) => (
          <Button type="link" size="small" onClick={() => void openDetail(record)}>
            查看详情
          </Button>
        ),
      },
    ],
    [openDetail],
  );

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card title="候选知识">
        <Table
          rowKey="candidate_id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          locale={{ emptyText: <Empty description="暂无候选知识" /> }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (count) => `共 ${count} 条`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>

      <Drawer
        title={detail?.title ?? "候选详情"}
        width={720}
        open={detailOpen}
        onClose={() => {
          setDetailOpen(false);
          setSelectedCandidateId(undefined);
          setDetail(undefined);
        }}
        destroyOnClose
      >
        {detailLoading ? (
          <Spin />
        ) : detail ? (
          <>
            <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="候选 ID">{detail.candidate_id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {(() => {
                  const meta = STATUS_TAG[detail.status] ?? { color: "default", label: detail.status };
                  return <Tag color={meta.color}>{meta.label}</Tag>;
                })()}
              </Descriptions.Item>
              <Descriptions.Item label="类型">
                {detail.candidate_type
                  ? (CANDIDATE_TYPE_LABEL[detail.candidate_type] ?? detail.candidate_type)
                  : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {SOURCE_CHANNEL_LABEL[detail.source_channel] ?? detail.source_channel}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间" span={2}>
                {formatDateTime(detail.created_at)}
              </Descriptions.Item>
              {detail.summary ? (
                <Descriptions.Item label="摘要" span={2}>
                  {detail.summary}
                </Descriptions.Item>
              ) : null}
            </Descriptions>

            <Typography.Title level={5}>来源追溯</Typography.Title>
            <div style={{ marginBottom: 16 }}>{renderSourceTraceDetail(detail.source_trace)}</div>

            <Typography.Title level={5}>内容预览</Typography.Title>
            {detail.content ? (
              <Typography.Paragraph
                style={{
                  whiteSpace: "pre-wrap",
                  maxHeight: 360,
                  overflow: "auto",
                  marginBottom: 0,
                  padding: 12,
                  background: "#fafafa",
                  borderRadius: 6,
                }}
              >
                {detail.content}
              </Typography.Paragraph>
            ) : (
              <Empty description="暂无内容预览" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </>
        ) : selectedCandidateId ? (
          <Empty description="未找到候选详情" />
        ) : null}
      </Drawer>
    </>
  );
}
