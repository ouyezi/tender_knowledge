import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  getCandidate,
  listCandidates,
  type BatchOperationResult,
  type CandidateDetail,
  type CandidateListItem,
  type ListCandidatesParams,
} from "../../services/candidates";
import BatchConfirmModal from "./BatchConfirmModal";
import BatchResultDrawer from "./BatchResultDrawer";
import CandidateDetailDrawer from "./CandidateDetailDrawer";
import CandidateMergeModal from "./CandidateMergeModal";
import CandidateSplitModal from "./CandidateSplitModal";

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

const DEFAULT_FILTERS: ListCandidatesParams = {
  status: "pending",
};

interface CandidateFilterFormValues {
  status?: string;
  source_channel?: string;
  candidate_type?: string;
  confidence_min?: number;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function toListParams(values: CandidateFilterFormValues): ListCandidatesParams {
  const params: ListCandidatesParams = {};
  if (values.status) {
    params.status = values.status;
  }
  if (values.source_channel) {
    params.source_channel = values.source_channel;
  }
  if (values.candidate_type) {
    params.candidate_type = values.candidate_type;
  }
  if (values.confidence_min !== undefined && values.confidence_min !== null) {
    params.confidence_min = values.confidence_min;
  }
  return params;
}

export default function CandidateCenterPage() {
  const navigate = useNavigate();
  const { selectedKbId } = useKBContext();
  const [form] = Form.useForm<CandidateFilterFormValues>();
  const [filters, setFilters] = useState<ListCandidatesParams>(DEFAULT_FILTERS);
  const [items, setItems] = useState<CandidateListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<CandidateDetail>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [splitOpen, setSplitOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchResultOpen, setBatchResultOpen] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchOperationResult>();

  const selectedRows = useMemo(
    () => items.filter((item) => selectedRowKeys.includes(item.candidate_id)),
    [items, selectedRowKeys],
  );

  const splitCandidateRow = useMemo(
    () => (selectedRows.length === 1 ? selectedRows[0] : undefined),
    [selectedRows],
  );

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listCandidates(selectedKbId, {
        page,
        page_size: pageSize,
        ...filters,
      });
      setItems(result.items ?? []);
      setTotal(result.total ?? 0);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleSearch = useCallback(() => {
    const values = form.getFieldsValue();
    setFilters(toListParams(values));
    setPage(1);
  }, [form]);

  const handleReset = useCallback(() => {
    form.resetFields();
    setFilters(DEFAULT_FILTERS);
    setPage(1);
  }, [form]);

  const openDetail = useCallback(
    async (record: CandidateListItem) => {
      if (!selectedKbId) {
        return;
      }
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

  const handleBatchComplete = useCallback(
    (result: BatchOperationResult) => {
      setBatchResult(result);
      setBatchResultOpen(true);
      setSelectedRowKeys([]);
      void loadData();
    },
    [loadData],
  );

  const handleMergeSplitSuccess = useCallback(() => {
    setSelectedRowKeys([]);
    void loadData();
  }, [loadData]);

  const handleDetailSaved = useCallback((nextDetail: CandidateDetail) => {
    setDetail(nextDetail);
    setItems((prev) =>
      prev.map((item) =>
        item.candidate_id === nextDetail.candidate_id
          ? {
              ...item,
              title: nextDetail.title,
              summary: nextDetail.summary,
            }
          : item,
      ),
    );
  }, []);

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
        width: 160,
        render: (_value, record) => (
          <Space size="small">
            <Button type="link" size="small" onClick={() => void openDetail(record)}>
              查看详情
            </Button>
            <Button
              type="link"
              size="small"
              onClick={() => navigate(`/candidates/confirm/${record.candidate_id}`)}
            >
              发布
            </Button>
          </Space>
        ),
      },
    ],
    [navigate, openDetail],
  );

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card
        title="候选知识"
        extra={
          <Link to="/candidates/audit">
            <Button type="link">操作日志</Button>
          </Link>
        }
      >
        <Form
          form={form}
          layout="inline"
          initialValues={{ status: "pending" }}
          style={{ marginBottom: 16 }}
          onFinish={handleSearch}
        >
          <Form.Item name="status" label="状态">
            <Select
              allowClear
              placeholder="全部状态"
              style={{ width: 140 }}
              options={Object.entries(STATUS_TAG).map(([value, meta]) => ({
                value,
                label: meta.label,
              }))}
            />
          </Form.Item>
          <Form.Item name="source_channel" label="来源">
            <Select
              allowClear
              placeholder="全部来源"
              style={{ width: 140 }}
              options={[
                { value: "all", label: SOURCE_CHANNEL_LABEL.all },
                { value: "document", label: SOURCE_CHANNEL_LABEL.document },
                { value: "template", label: SOURCE_CHANNEL_LABEL.template },
              ]}
            />
          </Form.Item>
          <Form.Item name="candidate_type" label="类型">
            <Select
              allowClear
              placeholder="全部类型"
              style={{ width: 140 }}
              options={Object.entries(CANDIDATE_TYPE_LABEL).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item name="confidence_min" label="最低置信度">
            <InputNumber min={0} max={1} step={0.1} placeholder="0-1" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                查询
              </Button>
              <Button onClick={handleReset}>重置</Button>
            </Space>
          </Form.Item>
        </Form>

        {selectedRowKeys.length > 0 ? (
          <Space style={{ marginBottom: 16 }}>
            <span>已选 {selectedRowKeys.length} 条</span>
            <Button type="primary" onClick={() => setBatchOpen(true)}>
              批量确认
            </Button>
            <Button
              disabled={selectedRows.length < 2}
              onClick={() => setMergeOpen(true)}
            >
              合并
            </Button>
            <Button
              disabled={selectedRows.length !== 1 || splitCandidateRow?.source_channel !== "document"}
              onClick={() => setSplitOpen(true)}
            >
              拆分
            </Button>
          </Space>
        ) : null}

        <Table
          rowKey="candidate_id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys as string[]),
          }}
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

      {detailOpen ? (
        <CandidateDetailDrawer
          kbId={selectedKbId}
          open={detailOpen}
          loading={detailLoading}
          detail={detail}
          onClose={() => {
            setDetailOpen(false);
            setDetail(undefined);
          }}
          onSaved={handleDetailSaved}
        />
      ) : null}

      <CandidateMergeModal
        kbId={selectedKbId}
        open={mergeOpen}
        selected={selectedRows}
        onClose={() => setMergeOpen(false)}
        onSuccess={handleMergeSplitSuccess}
      />

      <CandidateSplitModal
        kbId={selectedKbId}
        open={splitOpen}
        candidate={splitCandidateRow}
        onClose={() => setSplitOpen(false)}
        onSuccess={handleMergeSplitSuccess}
      />

      <BatchConfirmModal
        kbId={selectedKbId}
        open={batchOpen}
        selected={selectedRows}
        onClose={() => setBatchOpen(false)}
        onComplete={handleBatchComplete}
      />

      <BatchResultDrawer
        open={batchResultOpen}
        result={batchResult}
        onClose={() => setBatchResultOpen(false)}
      />
    </>
  );
}
