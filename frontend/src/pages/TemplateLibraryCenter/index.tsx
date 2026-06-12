import { Alert, Button, Card, Empty, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  listParseTasks,
  listTemplateLibraries,
  type TemplateLibraryListItem,
  type TemplateParseTaskListItem,
} from "../../services/templates";

const libraryColumns: ColumnsType<TemplateLibraryListItem> = [
  { title: "名称", dataIndex: "library_name", key: "library_name" },
  { title: "类型", dataIndex: "library_type", key: "library_type" },
  { title: "状态", dataIndex: "status", key: "status" },
  { title: "版本", dataIndex: "version", key: "version" },
  { title: "更新时间", dataIndex: "updated_at", key: "updated_at" },
];

const todoColumns: ColumnsType<TemplateParseTaskListItem> = [
  { title: "任务 ID", dataIndex: "parse_task_id", key: "parse_task_id", ellipsis: true },
  { title: "导入 ID", dataIndex: "import_id", key: "import_id", ellipsis: true },
  {
    title: "状态",
    dataIndex: "status",
    key: "status",
    render: (value: string) => {
      if (value === "parse_ready") return <Tag color="warning">待确认</Tag>;
      if (value === "running") return <Tag color="processing">解析中</Tag>;
      if (value === "pending") return <Tag>排队中</Tag>;
      if (value === "failed") return <Tag color="error">失败</Tag>;
      return value;
    },
  },
  {
    title: "创建时间",
    dataIndex: "created_at",
    key: "created_at",
    render: (value: string) => (value ? new Date(value).toLocaleString() : "-"),
  },
  {
    title: "操作",
    key: "actions",
    width: 120,
    render: (_value, record) =>
      record.status === "parse_ready" ? (
        <Button type="link" size="small">
          <Link to={`/template-libraries/parse-confirm/${record.parse_task_id}`}>去确认</Link>
        </Button>
      ) : (
        "—"
      ),
  },
];

export default function TemplateLibraryCenterPage() {
  const { selectedKbId } = useKBContext();
  const [searchParams] = useSearchParams();
  const [libraries, setLibraries] = useState<TemplateLibraryListItem[]>([]);
  const [tasks, setTasks] = useState<TemplateParseTaskListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [highlightedTaskId, setHighlightedTaskId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setLibraries([]);
      setTasks([]);
      return;
    }
    setLoading(true);
    try {
      const statuses = ["parse_ready", "running", "pending", "failed"];
      const [libResult, ...taskResults] = await Promise.all([
        listTemplateLibraries(selectedKbId),
        ...statuses.map((status) => listParseTasks(selectedKbId, { page_size: 100, status })),
      ]);
      setLibraries(libResult.items ?? []);
      const merged = new Map<string, TemplateParseTaskListItem>();
      for (const result of taskResults) {
        for (const item of result.items ?? []) {
          if (!merged.has(item.parse_task_id)) {
            merged.set(item.parse_task_id, item);
          }
        }
      }
      setTasks(Array.from(merged.values()));
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

  const pendingTasks = useMemo(
    () => tasks.filter((t) => ["parse_ready", "running", "pending", "failed"].includes(t.status)),
    [tasks],
  );

  useEffect(() => {
    const taskId = searchParams.get("highlight");
    if (!taskId || pendingTasks.length === 0) {
      return;
    }
    const exists = pendingTasks.some((item) => item.parse_task_id === taskId);
    if (!exists) {
      return;
    }
    setHighlightedTaskId(taskId);
    const timer = window.setTimeout(() => {
      const el = document.getElementById(`parse-task-${taskId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 80);
    const clearTimer = window.setTimeout(() => setHighlightedTaskId(null), 4000);
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(clearTimer);
    };
  }, [pendingTasks, searchParams]);

  return (
    <>
      <Card title="待处理" style={{ marginBottom: 16 }} loading={loading}>
        {pendingTasks.length === 0 ? (
          <Empty description="暂无待确认或失败的解析任务" />
        ) : (
          <Table
            rowKey="parse_task_id"
            size="small"
            pagination={false}
            columns={todoColumns}
            dataSource={pendingTasks}
            onRow={(record) => ({
              id: `parse-task-${record.parse_task_id}`,
            })}
            rowClassName={(record) =>
              highlightedTaskId === record.parse_task_id ? "parse-task-highlight-row" : ""
            }
          />
        )}
      </Card>
      <Card title="模板库" loading={loading}>
        <Table
          rowKey="template_library_id"
          columns={libraryColumns}
          dataSource={libraries}
          locale={{ emptyText: "暂无模板库" }}
        />
      </Card>
      <style>{`
        .parse-task-highlight-row > td {
          background: #fffbe6 !important;
          transition: background 0.3s ease;
        }
      `}</style>
    </>
  );
}
