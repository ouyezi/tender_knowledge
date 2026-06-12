import { Alert, Card, Empty, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useState } from "react";
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
  { title: "状态", dataIndex: "status", key: "status" },
  { title: "创建时间", dataIndex: "created_at", key: "created_at" },
];

export default function TemplateLibraryCenterPage() {
  const { selectedKbId } = useKBContext();
  const [libraries, setLibraries] = useState<TemplateLibraryListItem[]>([]);
  const [tasks, setTasks] = useState<TemplateParseTaskListItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setLibraries([]);
      setTasks([]);
      return;
    }
    setLoading(true);
    try {
      const [libResult, taskResult] = await Promise.all([
        listTemplateLibraries(selectedKbId),
        listParseTasks(selectedKbId),
      ]);
      setLibraries(libResult.items ?? []);
      setTasks(taskResult.items ?? []);
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

  const pendingTasks = tasks.filter((t) =>
    ["parse_ready", "running", "pending", "failed"].includes(t.status),
  );

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
    </>
  );
}
