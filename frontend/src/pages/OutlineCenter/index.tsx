import { Alert, Button, Card, Empty, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  getActualBidParseTask,
  listActualBidParseTasks,
  type ActualBidParseTaskDetail,
  type ActualBidParseTaskListItem,
} from "../../services/actualBidParse";
import { listOutlines, type BidOutlineListItem } from "../../services/bidOutlines";
import { triggerChapterPatternMining } from "../../services/chapterPatterns";
import ParseTaskLogDrawer from "./ParseTaskLogDrawer";

const OUTLINE_WARNING_LABELS: Record<string, string> = {
  embedded_document_detected: "内嵌附件",
  high_l1_ratio: "L1占比偏高",
  flat_fallback: "扁平回退",
  empty_outline: "空目录",
  high_review_ratio: "待复核偏多",
};

function buildTodoColumns(onViewLog: (task: ActualBidParseTaskListItem) => void): ColumnsType<ActualBidParseTaskListItem> {
  return [
    { title: "文件名", dataIndex: "file_name", key: "file_name", ellipsis: true },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => {
        if (value === "ready") return <Tag color="warning">待确认</Tag>;
        if (value === "failed") return <Tag color="error">失败</Tag>;
        return <Tag>{value}</Tag>;
      },
    },
    {
      title: "节点 / L1%",
      key: "quality",
      render: (_value, record) => {
        const q = record.outline_quality;
        if (!q) return "—";
        return `${q.node_count} / ${Math.round(q.l1_ratio * 100)}%`;
      },
    },
    {
      title: "警告",
      key: "warnings",
      render: (_value, record) =>
        (record.outline_quality?.warnings ?? []).map((w) => (
          <Tag key={w} color="warning">
            {OUTLINE_WARNING_LABELS[w] ?? w}
          </Tag>
        )),
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
      width: 180,
      render: (_value, record) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => onViewLog(record)}>
            查看日志
          </Button>
          {record.status === "ready" ? (
            <Link to={`/outlines/parse-confirm/${record.parse_task_id}`}>去确认</Link>
          ) : null}
        </Space>
      ),
    },
  ];
}

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
    title: "章节数",
    dataIndex: "node_count",
    key: "node_count",
    width: 90,
    render: (value: number | undefined) => (value != null ? value : "—"),
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

export default function OutlineCenterPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [todoTasks, setTodoTasks] = useState<ActualBidParseTaskListItem[]>([]);
  const [outlines, setOutlines] = useState<BidOutlineListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [mining, setMining] = useState(false);
  const [logDrawerOpen, setLogDrawerOpen] = useState(false);
  const [logLoading, setLogLoading] = useState(false);
  const [logTask, setLogTask] = useState<ActualBidParseTaskDetail | null>(null);

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setTodoTasks([]);
      setOutlines([]);
      return;
    }
    setLoading(true);
    try {
      const [readyResult, failedResult, outlineResult] = await Promise.all([
        listActualBidParseTasks(selectedKbId, { status: "ready", page_size: 100 }),
        listActualBidParseTasks(selectedKbId, { status: "failed", page_size: 100 }),
        listOutlines(selectedKbId, { page_size: 100 }),
      ]);
      const merged = [...(readyResult.items ?? []), ...(failedResult.items ?? [])].sort((a, b) =>
        (b.created_at ?? "").localeCompare(a.created_at ?? ""),
      );
      setTodoTasks(merged);
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

  const handleViewLog = useCallback(
    async (task: ActualBidParseTaskListItem) => {
      if (!selectedKbId) return;
      setLogDrawerOpen(true);
      setLogLoading(true);
      setLogTask(null);
      try {
        const detail = await getActualBidParseTask(selectedKbId, task.parse_task_id);
        setLogTask(detail);
      } catch (error) {
        message.error((error as Error).message);
        setLogDrawerOpen(false);
      } finally {
        setLogLoading(false);
      }
    },
    [selectedKbId],
  );

  const handleMineChapterPatterns = useCallback(async () => {
    if (!selectedKbId) return;
    setMining(true);
    try {
      const task = await triggerChapterPatternMining(selectedKbId, { min_frequency: 2 });
      message.success(`已触发挖掘任务：${task.mining_task_id}`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setMining(false);
    }
  }, [selectedKbId]);

  const todoColumns = useMemo(() => buildTodoColumns((task) => void handleViewLog(task)), [handleViewLog]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card
        title="待处理"
        style={{ marginBottom: 16 }}
        extra={
          <Button loading={mining} disabled={readOnly} onClick={() => void handleMineChapterPatterns()}>
            挖掘章节模式
          </Button>
        }
      >
        {todoTasks.length === 0 ? (
          <Empty description="暂无待确认或失败的解析任务" />
        ) : (
          <Table
            rowKey="parse_task_id"
            size="small"
            loading={loading}
            pagination={false}
            columns={todoColumns}
            dataSource={todoTasks}
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
      <ParseTaskLogDrawer
        open={logDrawerOpen}
        loading={logLoading}
        task={logTask}
        onClose={() => {
          setLogDrawerOpen(false);
          setLogTask(null);
        }}
      />
    </>
  );
}
