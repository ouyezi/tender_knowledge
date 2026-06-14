import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  getCandidateAuditLog,
  listCandidateAuditLogs,
  type CandidateAuditAction,
  type CandidateAuditLogItem,
} from "../../services/candidateAudit";

const ACTION_LABEL: Record<CandidateAuditAction, string> = {
  edit: "编辑",
  publish: "发布",
  publish_failed: "发布失败",
  ignore: "忽略",
  merge: "合并",
  split: "拆分",
  batch_confirm: "批量确认",
  batch_reject: "批量驳回",
};

const ACTION_COLOR: Record<CandidateAuditAction, string> = {
  edit: "processing",
  publish: "success",
  publish_failed: "error",
  ignore: "default",
  merge: "purple",
  split: "cyan",
  batch_confirm: "gold",
  batch_reject: "orange",
};

interface AuditFilterValues {
  candidate_id?: string;
  batch_id?: string;
  action?: CandidateAuditAction;
  operator_id?: string;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function CandidateAuditPanel() {
  const { selectedKbId } = useKBContext();
  const [form] = Form.useForm<AuditFilterValues>();
  const [filters, setFilters] = useState<AuditFilterValues>({});
  const [items, setItems] = useState<CandidateAuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<CandidateAuditLogItem>();

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listCandidateAuditLogs(selectedKbId, {
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

  const openDetail = useCallback(
    async (record: CandidateAuditLogItem) => {
      if (!selectedKbId) {
        return;
      }
      setDetailOpen(true);
      setDetail(undefined);
      setDetailLoading(true);
      try {
        const next = await getCandidateAuditLog(selectedKbId, record.audit_id);
        setDetail(next);
      } catch (error) {
        message.error((error as Error).message);
        setDetail(record);
      } finally {
        setDetailLoading(false);
      }
    },
    [selectedKbId],
  );

  const columns: ColumnsType<CandidateAuditLogItem> = useMemo(
    () => [
      {
        title: "时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        render: (value: string) => formatDateTime(value),
      },
      {
        title: "动作",
        dataIndex: "action",
        key: "action",
        width: 120,
        render: (value: CandidateAuditAction) => (
          <Tag color={ACTION_COLOR[value] ?? "default"}>{ACTION_LABEL[value] ?? value}</Tag>
        ),
      },
      {
        title: "候选 ID",
        dataIndex: "candidate_id",
        key: "candidate_id",
        ellipsis: true,
      },
      {
        title: "操作者",
        dataIndex: "operator_id",
        key: "operator_id",
        width: 120,
      },
      {
        title: "批次",
        dataIndex: "batch_id",
        key: "batch_id",
        width: 140,
        ellipsis: true,
        render: (value?: string | null) => value ?? "-",
      },
      {
        title: "操作",
        key: "actions",
        width: 90,
        render: (_value, record) => (
          <Button type="link" size="small" onClick={() => void openDetail(record)}>
            详情
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
      <Card
        title="候选确认操作日志"
        extra={
          <Link to="/candidates">
            <Button type="link">返回候选列表</Button>
          </Link>
        }
      >
        <Form
          form={form}
          layout="inline"
          style={{ marginBottom: 16 }}
          onFinish={() => {
            setFilters(form.getFieldsValue());
            setPage(1);
          }}
        >
          <Form.Item name="candidate_id" label="候选 ID">
            <Input placeholder="doc_... / tpl_..." style={{ width: 220 }} allowClear />
          </Form.Item>
          <Form.Item name="batch_id" label="批次 ID">
            <Input placeholder="UUID" style={{ width: 220 }} allowClear />
          </Form.Item>
          <Form.Item name="action" label="动作">
            <Select
              allowClear
              placeholder="全部动作"
              style={{ width: 140 }}
              options={Object.entries(ACTION_LABEL).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item name="operator_id" label="操作者">
            <Input placeholder="admin" style={{ width: 120 }} allowClear />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                查询
              </Button>
              <Button
                onClick={() => {
                  form.resetFields();
                  setFilters({});
                  setPage(1);
                }}
              >
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>

        <Table
          rowKey="audit_id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          locale={{ emptyText: <Empty description="暂无操作日志" /> }}
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
        title="审计详情"
        width={640}
        open={detailOpen}
        onClose={() => {
          setDetailOpen(false);
          setDetail(undefined);
        }}
        destroyOnHidden
      >
        {detailLoading ? (
          <Typography.Text type="secondary">加载中...</Typography.Text>
        ) : detail ? (
          <>
            <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="audit_id">{detail.audit_id}</Descriptions.Item>
              <Descriptions.Item label="candidate_id">{detail.candidate_id}</Descriptions.Item>
              <Descriptions.Item label="action">
                <Tag color={ACTION_COLOR[detail.action] ?? "default"}>
                  {ACTION_LABEL[detail.action] ?? detail.action}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="operator_id">{detail.operator_id}</Descriptions.Item>
              <Descriptions.Item label="trace_id">{detail.trace_id}</Descriptions.Item>
              <Descriptions.Item label="batch_id">{detail.batch_id ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="created_at">
                {formatDateTime(detail.created_at)}
              </Descriptions.Item>
            </Descriptions>
            <Typography.Title level={5}>detail</Typography.Title>
            <pre
              style={{
                margin: 0,
                padding: 12,
                background: "#fafafa",
                borderRadius: 6,
                maxHeight: 420,
                overflow: "auto",
              }}
            >
              {JSON.stringify(detail.detail, null, 2)}
            </pre>
          </>
        ) : (
          <Empty description="未找到审计详情" />
        )}
      </Drawer>
    </>
  );
}
