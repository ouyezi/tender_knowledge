import { Alert, Button, Card, Input, Select, Space, Table, Tabs, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useKBContext } from "../../layout/KBContext";
import {
  listRetrievalTraces,
  type ListRetrievalTracesParams,
  type RetrievalTraceListItem,
} from "../../services/retrieval";
import EvalSetPanel from "./EvalSetPanel";
import FeedbackPanel from "./FeedbackPanel";
import StrategyVersionPanel from "./StrategyVersionPanel";
import TraceDetailDrawer from "./TraceDetailDrawer";

const INTENT_OPTIONS = [
  { label: "知识检索", value: "knowledge_lookup" },
  { label: "目录匹配", value: "directory_match" },
  { label: "模块建议", value: "module_suggestion" },
  { label: "素材推荐", value: "material_recommend" },
];

const STATUS_OPTIONS = [
  { label: "成功", value: "success" },
  { label: "部分成功", value: "partial" },
  { label: "失败", value: "failed" },
];

function TraceTab({ kbId }: { kbId: string }) {
  const [rows, setRows] = useState<RetrievalTraceListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [intent, setIntent] = useState<string>();
  const [status, setStatus] = useState<string>();
  const [operatorId, setOperatorId] = useState("");
  const [activeTraceId, setActiveTraceId] = useState<string>();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: ListRetrievalTracesParams = {
        page_size: 50,
        intent,
        status,
        operator_id: operatorId.trim() || undefined,
      };
      const data = await listRetrievalTraces(kbId, params);
      setRows(data.items ?? []);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [intent, kbId, operatorId, status]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const columns: ColumnsType<RetrievalTraceListItem> = useMemo(
    () => [
      {
        title: "trace_id",
        dataIndex: "trace_id",
        key: "trace_id",
        ellipsis: true,
      },
      {
        title: "意图",
        dataIndex: "intent",
        key: "intent",
        width: 140,
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (value: string) => (
          <Tag color={value === "success" ? "green" : value === "failed" ? "red" : "gold"}>{value}</Tag>
        ),
      },
      {
        title: "耗时",
        dataIndex: "latency_ms",
        key: "latency_ms",
        width: 100,
        render: (value: number) => `${value} ms`,
      },
      {
        title: "结果数",
        dataIndex: "result_count",
        key: "result_count",
        width: 90,
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        render: (value: string) => (value ? new Date(value).toLocaleString() : "-"),
      },
      {
        title: "操作",
        key: "action",
        width: 110,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            onClick={() => {
              setActiveTraceId(record.trace_id);
              setDrawerOpen(true);
            }}
          >
            查看详情
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Space wrap>
        <Select
          allowClear
          placeholder="意图"
          style={{ width: 180 }}
          options={INTENT_OPTIONS}
          value={intent}
          onChange={setIntent}
        />
        <Select
          allowClear
          placeholder="状态"
          style={{ width: 140 }}
          options={STATUS_OPTIONS}
          value={status}
          onChange={setStatus}
        />
        <Input
          placeholder="操作人ID"
          style={{ width: 220 }}
          value={operatorId}
          onChange={(event) => setOperatorId(event.target.value)}
        />
        <Button onClick={() => void loadData()}>刷新</Button>
      </Space>
      <Table
        rowKey="trace_id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={rows}
        pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
      />
      <TraceDetailDrawer
        open={drawerOpen}
        kbId={kbId}
        traceId={activeTraceId}
        onClose={() => {
          setDrawerOpen(false);
          setActiveTraceId(undefined);
        }}
      />
    </Space>
  );
}

export default function RetrievalOptimizationCenterPage() {
  const { selectedKbId, readOnly } = useKBContext();

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <Card title="检索优化中心">
      <Tabs
        defaultActiveKey="trace"
        items={[
          {
            key: "trace",
            label: "Trace",
            children: <TraceTab kbId={selectedKbId} />,
          },
          {
            key: "feedback",
            label: "反馈",
            children: <FeedbackPanel kbId={selectedKbId} readOnly={readOnly} />,
          },
          {
            key: "eval",
            label: "评测集",
            children: <EvalSetPanel kbId={selectedKbId} readOnly={readOnly} />,
          },
          {
            key: "strategy",
            label: "策略版本",
            children: <StrategyVersionPanel kbId={selectedKbId} readOnly={readOnly} />,
          },
        ]}
      />
      <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
        说明：本页用于查看检索 Trace、提交反馈、维护评测集并管理策略版本。
      </Typography.Paragraph>
    </Card>
  );
}
