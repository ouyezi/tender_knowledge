import { Alert, Button, Card, Empty, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  listActualBidParseTasks,
  type ActualBidParseTaskListItem,
} from "../../services/actualBidParse";
import { listOutlines, type BidOutlineListItem } from "../../services/bidOutlines";

const todoColumns: ColumnsType<ActualBidParseTaskListItem> = [
  { title: "任务 ID", dataIndex: "parse_task_id", key: "parse_task_id", ellipsis: true },
  { title: "导入 ID", dataIndex: "import_id", key: "import_id", ellipsis: true },
  {
    title: "状态",
    dataIndex: "status",
    key: "status",
    width: 120,
    render: (value: string) =>
      value === "ready" ? <Tag color="warning">待确认</Tag> : <Tag>{value}</Tag>,
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
    key: "actions",
    width: 120,
    render: (_value, record) => (
      <Button type="link" size="small">
        <Link to={`/outlines/parse-confirm/${record.parse_task_id}`}>去确认</Link>
      </Button>
    ),
  },
];

export default function OutlineCenterPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [todoTasks, setTodoTasks] = useState<ActualBidParseTaskListItem[]>([]);
  const [outlines, setOutlines] = useState<BidOutlineListItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setTodoTasks([]);
      setOutlines([]);
      return;
    }
    setLoading(true);
    try {
      const [taskResult, outlineResult] = await Promise.all([
        listActualBidParseTasks(selectedKbId, { status: "ready", page_size: 100 }),
        listOutlines(selectedKbId, { page_size: 100 }),
      ]);
      setTodoTasks(taskResult.items ?? []);
      setOutlines(outlineResult.items ?? []);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  const pendingTasks = useMemo(() => todoTasks.filter((item) => item.status === "ready"), [todoTasks]);
  const outlineColumns: ColumnsType<BidOutlineListItem> = [
    { title: "目录名", dataIndex: "outline_name", key: "outline_name", ellipsis: true },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => (
        <Tag color={value === "confirmed" ? "green" : value === "draft" ? "blue" : "default"}>{value}</Tag>
      ),
    },
    {
      title: "项目名",
      dataIndex: "project_name",
      key: "project_name",
      ellipsis: true,
      render: (value: string | null) => value || "-",
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      key: "updated_at",
      width: 180,
      render: (value: string) => (value ? new Date(value).toLocaleString() : "-"),
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      render: (_value, record) => <Link to={`/outlines/${record.bid_outline_id}`}>查看详情</Link>,
    },
  ];

  return (
    <>
      <Card
        title="待处理"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button type="primary" disabled={readOnly}>
              新建目录
            </Button>
          </Space>
        }
      >
        {pendingTasks.length === 0 ? (
          <Empty description="暂无待确认或失败的解析任务" />
        ) : (
          <Table
            rowKey="parse_task_id"
            size="small"
            loading={loading}
            pagination={false}
            columns={todoColumns}
            dataSource={pendingTasks}
          />
        )}
      </Card>
      <Card title="目录">
        {outlines.length === 0 ? (
          <Empty description="暂无目录" />
        ) : (
          <Table
            rowKey="bid_outline_id"
            size="small"
            loading={loading}
            columns={outlineColumns}
            pagination={false}
            dataSource={outlines}
          />
        )}
      </Card>
    </>
  );
}
