import { Alert, Button, Card, Empty, Modal, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  applyParseDiff,
  getParseTask,
  listParseTasks,
  listTemplateLibraries,
  publishTemplateLibrary,
  rejectParseDiff,
  type TemplateStructureDiff,
  type TemplateLibraryListItem,
  type TemplateParseTaskListItem,
} from "../../services/templates";
import PublishModal from "./PublishModal";

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
  const [publishTarget, setPublishTarget] = useState<TemplateLibraryListItem | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [diffTaskMap, setDiffTaskMap] = useState<Record<string, TemplateStructureDiff | null>>({});
  const [reviewingTask, setReviewingTask] = useState<TemplateParseTaskListItem | null>(null);
  const [reviewing, setReviewing] = useState(false);

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
      const mergedTasks = Array.from(merged.values());
      setTasks(mergedTasks);
      const parseReadyTasks = mergedTasks.filter((item) => item.status === "parse_ready");
      const details = await Promise.all(
        parseReadyTasks.map(async (item) => {
          const detail = await getParseTask(selectedKbId, item.parse_task_id);
          return [item.parse_task_id, detail.structure_diff ?? null] as const;
        }),
      );
      setDiffTaskMap(Object.fromEntries(details));
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
  const columns = useMemo<ColumnsType<TemplateParseTaskListItem>>(
    () => [
      ...todoColumns,
      {
        title: "结构差异",
        key: "structure_diff",
        render: (_value, record) => {
          const diff = diffTaskMap[record.parse_task_id];
          if (diff?.status === "pending_review") {
            return <Tag color="warning">待审核</Tag>;
          }
          return "—";
        },
      },
      {
        title: "审核操作",
        key: "diff_actions",
        render: (_value, record) => {
          const diff = diffTaskMap[record.parse_task_id];
          if (diff?.status === "pending_review") {
            return (
              <Button type="link" size="small" onClick={() => setReviewingTask(record)}>
                Diff 审核
              </Button>
            );
          }
          return "—";
        },
      },
    ],
    [diffTaskMap],
  );
  const libraryColumnsWithActions = useMemo<ColumnsType<TemplateLibraryListItem>>(
    () => [
      ...libraryColumns,
      {
        title: "操作",
        key: "actions",
        render: (_value, record) => (
          <Button size="small" onClick={() => setPublishTarget(record)}>
            发布
          </Button>
        ),
      },
    ],
    [],
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
            columns={columns}
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
          columns={libraryColumnsWithActions}
          dataSource={libraries}
          locale={{ emptyText: "暂无模板库" }}
        />
      </Card>
      <PublishModal
        open={!!publishTarget}
        targetName={publishTarget?.library_name ?? ""}
        defaultTargetType="library"
        confirmLoading={publishing}
        onCancel={() => setPublishTarget(null)}
        onSubmit={async (values) => {
          if (!selectedKbId || !publishTarget) return;
          setPublishing(true);
          try {
            const result = await publishTemplateLibrary(selectedKbId, publishTarget.template_library_id, {
              cascade_templates: values.cascade_templates ?? true,
              version_note: values.version_note ?? null,
            });
            message.success(`模板库发布成功，版本 ${result.version}`);
            setPublishTarget(null);
            void loadData();
          } catch (err) {
            message.error((err as Error).message);
          } finally {
            setPublishing(false);
          }
        }}
      />
      <Modal
        title="结构差异审核"
        open={!!reviewingTask}
        onCancel={() => setReviewingTask(null)}
        confirmLoading={reviewing}
        footer={[
          <Button key="cancel" onClick={() => setReviewingTask(null)}>
            关闭
          </Button>,
          <Button
            key="reject"
            danger
            loading={reviewing}
            onClick={() => {
              void (async () => {
                if (!selectedKbId || !reviewingTask) return;
                const diff = diffTaskMap[reviewingTask.parse_task_id];
                if (!diff) return;
                setReviewing(true);
                try {
                  await rejectParseDiff(selectedKbId, reviewingTask.parse_task_id, { diff_id: diff.diff_id });
                  message.success("已拒绝结构差异");
                  setReviewingTask(null);
                  void loadData();
                } catch (err) {
                  message.error((err as Error).message);
                } finally {
                  setReviewing(false);
                }
              })();
            }}
          >
            拒绝
          </Button>,
          <Button
            key="apply"
            type="primary"
            loading={reviewing}
            onClick={() => {
              void (async () => {
                if (!selectedKbId || !reviewingTask) return;
                const diff = diffTaskMap[reviewingTask.parse_task_id];
                if (!diff) return;
                setReviewing(true);
                try {
                  await applyParseDiff(selectedKbId, reviewingTask.parse_task_id, { diff_id: diff.diff_id });
                  message.success("已应用结构差异");
                  setReviewingTask(null);
                  void loadData();
                } catch (err) {
                  message.error((err as Error).message);
                } finally {
                  setReviewing(false);
                }
              })();
            }}
          >
            应用
          </Button>,
        ]}
      >
        {reviewingTask && diffTaskMap[reviewingTask.parse_task_id] ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div>任务：{reviewingTask.parse_task_id}</div>
            <div>
              变更统计：
              新增 {diffTaskMap[reviewingTask.parse_task_id]?.diff_payload?.summary?.added ?? 0} /
              删除 {diffTaskMap[reviewingTask.parse_task_id]?.diff_payload?.summary?.removed ?? 0} /
              修改 {diffTaskMap[reviewingTask.parse_task_id]?.diff_payload?.summary?.changed ?? 0}
            </div>
          </Space>
        ) : (
          <Empty description="暂无可审核差异" />
        )}
      </Modal>
      <style>{`
        .parse-task-highlight-row > td {
          background: #fffbe6 !important;
          transition: background 0.3s ease;
        }
      `}</style>
    </>
  );
}
