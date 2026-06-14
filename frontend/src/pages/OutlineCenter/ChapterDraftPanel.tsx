import { Alert, Button, Card, Descriptions, List, Space, Spin, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  accept,
  discard,
  getDraft,
  getTask,
  regenerate,
  type ChapterDraft,
  type GenerationTask,
  type UserChapterSelection,
} from "../../services/generation";
import SnapshotDetailDrawer from "./SnapshotDetailDrawer";

interface Props {
  kbId: string;
  taskId?: string | null;
  variableValues?: Record<string, string>;
  userChapterSelections?: UserChapterSelection[];
}

export function ChapterDraftPanel({ kbId, taskId, variableValues, userChapterSelections }: Props) {
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(taskId ?? null);
  const [task, setTask] = useState<GenerationTask | null>(null);
  const [draft, setDraft] = useState<ChapterDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const [activeSnapshotId, setActiveSnapshotId] = useState<string | null>(null);

  const pollTask = useCallback(async () => {
    if (!currentTaskId) return;
    const taskData = await getTask(kbId, currentTaskId);
    setTask(taskData);
    if (taskData.draft_id) {
      const draftData = await getDraft(kbId, taskData.draft_id);
      setDraft(draftData);
    }
  }, [currentTaskId, kbId]);

  useEffect(() => {
    setCurrentTaskId(taskId ?? null);
  }, [taskId]);

  useEffect(() => {
    if (!currentTaskId) return;
    setLoading(true);
    let timer: number | undefined;
    let stopped = false;

    const tick = async () => {
      if (stopped) return;
      try {
        const taskData = await getTask(kbId, currentTaskId);
        setTask(taskData);
        if (taskData.draft_id) {
          const draftData = await getDraft(kbId, taskData.draft_id);
          setDraft(draftData);
        }
        if (taskData.status !== "completed" && taskData.status !== "failed") {
          timer = window.setTimeout(() => void tick(), 2000);
        }
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        if (!stopped) setLoading(false);
      }
    };
    void tick();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [currentTaskId, kbId]);

  const statusColor = useMemo(() => {
    if (task?.status === "completed") return "green";
    if (task?.status === "failed") return "red";
    if (task?.status === "running") return "blue";
    return "default";
  }, [task?.status]);

  if (!currentTaskId) {
    return <Alert type="info" showIcon message="请先在上一步点击“开始生成草稿”" />;
  }

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Card size="small" title="生成任务状态" extra={<Tag color={statusColor}>{task?.status ?? "pending"}</Tag>}>
        <Spin spinning={loading}>
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="task_id">{task?.task_id ?? currentTaskId}</Descriptions.Item>
            <Descriptions.Item label="draft_id">{task?.draft_id ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="started_at">
              {task?.started_at ? new Date(task.started_at).toLocaleString() : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="completed_at">
              {task?.completed_at ? new Date(task.completed_at).toLocaleString() : "-"}
            </Descriptions.Item>
          </Descriptions>
          {task?.error_message ? <Alert style={{ marginTop: 12 }} type="error" showIcon message={task.error_message} /> : null}
          <Space style={{ marginTop: 12 }}>
            <Button onClick={() => void pollTask()}>刷新任务</Button>
            <Button
              disabled={!task?.snapshot_id}
              onClick={() => {
                setActiveSnapshotId(task?.snapshot_id ?? null);
                setSnapshotOpen(true);
              }}
            >
              查看 Snapshot
            </Button>
          </Space>
        </Spin>
      </Card>

      <Card size="small" title={`草稿内容 ${draft ? `(${draft.version_tag})` : ""}`}>
        {!draft ? (
          <Typography.Text type="secondary">任务未完成或尚未返回草稿。</Typography.Text>
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space>
              <Tag color={draft.outcome_status === "accepted" ? "green" : draft.outcome_status === "discarded" ? "red" : "default"}>
                {draft.outcome_status}
              </Tag>
              <Tag>{draft.is_active ? "active" : "inactive"}</Tag>
            </Space>
            <List
              bordered
              dataSource={draft.paragraphs ?? []}
              renderItem={(item) => (
                <List.Item>
                  <Space direction="vertical" size={6} style={{ width: "100%" }}>
                    <Typography.Text strong>段落 {item.paragraph_index + 1}</Typography.Text>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>{item.text}</Typography.Paragraph>
                    <Space wrap>
                      {(item.citations ?? []).map((cite, idx) => (
                        <Tag key={`${item.paragraph_index}-${idx}`}>
                          {cite.source_type}: {cite.source_label}
                        </Tag>
                      ))}
                    </Space>
                  </Space>
                </List.Item>
              )}
            />
            {(draft.conflict_hints?.length ?? 0) > 0 ? (
              <Alert
                type="warning"
                showIcon
                message="冲突提示"
                description={
                  <Space direction="vertical">
                    {draft.conflict_hints.map((item, idx) => (
                      <Typography.Text key={idx}>{String(item.message ?? JSON.stringify(item))}</Typography.Text>
                    ))}
                  </Space>
                }
              />
            ) : null}
            <Space>
              <Button
                type="primary"
                loading={actionLoading}
                onClick={async () => {
                  if (!draft) return;
                  setActionLoading(true);
                  try {
                    await accept(kbId, draft.draft_id);
                    message.success("草稿已采纳");
                    await pollTask();
                  } catch (error) {
                    message.error((error as Error).message);
                  } finally {
                    setActionLoading(false);
                  }
                }}
              >
                采纳草稿
              </Button>
              <Button
                danger
                loading={actionLoading}
                onClick={async () => {
                  if (!draft) return;
                  setActionLoading(true);
                  try {
                    await discard(kbId, draft.draft_id);
                    message.success("草稿已废弃");
                    await pollTask();
                  } catch (error) {
                    message.error((error as Error).message);
                  } finally {
                    setActionLoading(false);
                  }
                }}
              >
                废弃草稿
              </Button>
              <Button
                loading={actionLoading}
                onClick={async () => {
                  if (!draft) return;
                  setActionLoading(true);
                  try {
                    const taskData = await regenerate(kbId, draft.draft_id, {
                      variable_values: variableValues,
                      user_chapter_selections: userChapterSelections,
                    });
                    setCurrentTaskId(taskData.task_id);
                    setTask(taskData);
                    setDraft(null);
                    message.success("已触发重新生成");
                  } catch (error) {
                    message.error((error as Error).message);
                  } finally {
                    setActionLoading(false);
                  }
                }}
              >
                重新生成
              </Button>
            </Space>
          </Space>
        )}
      </Card>
      <SnapshotDetailDrawer
        open={snapshotOpen}
        kbId={kbId}
        snapshotId={activeSnapshotId}
        onClose={() => setSnapshotOpen(false)}
      />
    </Space>
  );
}
