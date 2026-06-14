import { Drawer, List, Spin, Table, Tag, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  listDownstreamEntries,
  listTasks,
  type DownstreamEntryItem,
  type ImportTaskItem,
} from "../../services/fileImports";

interface TaskLogDrawerProps {
  open: boolean;
  kbId?: string;
  importId?: string;
  onClose: () => void;
}

export default function TaskLogDrawer({ open, kbId, importId, onClose }: TaskLogDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState<ImportTaskItem[]>([]);
  const [entries, setEntries] = useState<DownstreamEntryItem[]>([]);

  useEffect(() => {
    if (!open || !kbId || !importId) {
      return;
    }
    setLoading(true);
    Promise.all([listTasks(kbId, importId), listDownstreamEntries(kbId, importId)])
      .then(([taskResp, entryResp]) => {
        setTasks(taskResp.items ?? []);
        setEntries(entryResp.items ?? []);
      })
      .catch((error: unknown) => {
        message.error((error as Error).message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [open, kbId, importId]);

  const taskColumns = useMemo(
    () => [
      { title: "任务类型", dataIndex: "task_type", key: "task_type" },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "重试次数",
        dataIndex: "retry_count",
        key: "retry_count",
      },
    ],
    [],
  );

  return (
    <Drawer title="任务日志" width={760} open={open} onClose={onClose} destroyOnHidden>
      {loading ? (
        <Spin />
      ) : (
        <>
          <Table rowKey="task_id" columns={taskColumns} dataSource={tasks} pagination={false} />
          <List
            header="任务日志明细"
            style={{ marginTop: 16 }}
            dataSource={tasks.flatMap((task) =>
              (task.log_lines ?? []).map((line) => ({
                key: `${task.task_id}-${line.ts}-${line.message}`,
                label: `${task.task_type} [${line.level}]`,
                ts: line.ts,
                message: line.message,
              })),
            )}
            renderItem={(item) => (
              <List.Item key={item.key}>
                {item.ts} - {item.label}: {item.message}
              </List.Item>
            )}
          />
          <List
            header="下游任务占位"
            style={{ marginTop: 16 }}
            dataSource={entries}
            renderItem={(entry) => (
              <List.Item key={entry.entry_id}>
                {entry.task_type} / {entry.status} / {entry.created_at ?? "-"}
              </List.Item>
            )}
          />
        </>
      )}
    </Drawer>
  );
}
