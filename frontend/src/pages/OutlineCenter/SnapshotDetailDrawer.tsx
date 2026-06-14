import { Descriptions, Drawer, Space, Spin, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { getSnapshot, type GenerationSnapshot } from "../../services/generation";

interface Props {
  open: boolean;
  kbId: string;
  snapshotId?: string | null;
  onClose: () => void;
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <Space direction="vertical" size={6} style={{ width: "100%" }}>
      <Typography.Text strong>{title}</Typography.Text>
      <Typography.Paragraph copyable style={{ marginBottom: 0 }}>
        <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(value ?? {}, null, 2)}</pre>
      </Typography.Paragraph>
    </Space>
  );
}

export default function SnapshotDetailDrawer({ open, kbId, snapshotId, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<GenerationSnapshot | null>(null);

  useEffect(() => {
    if (!open || !snapshotId) return;
    setLoading(true);
    void getSnapshot(kbId, snapshotId)
      .then((data) => setSnapshot(data))
      .catch((error) => message.error((error as Error).message))
      .finally(() => setLoading(false));
  }, [kbId, open, snapshotId]);

  return (
    <Drawer title="Snapshot 审计详情" open={open} width={760} onClose={onClose}>
      <Spin spinning={loading}>
        {!snapshot ? (
          <Typography.Text type="secondary">暂无快照数据</Typography.Text>
        ) : (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="snapshot_id">{snapshot.snapshot_id}</Descriptions.Item>
              <Descriptions.Item label="task_id">{snapshot.task_id}</Descriptions.Item>
              <Descriptions.Item label="requirement_context_id">{snapshot.requirement_context_id}</Descriptions.Item>
              <Descriptions.Item label="suggestion_id">{snapshot.suggestion_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="prompt_version">{snapshot.prompt_version}</Descriptions.Item>
              <Descriptions.Item label="result_version">{snapshot.result_version}</Descriptions.Item>
              <Descriptions.Item label="created_at" span={2}>
                {snapshot.created_at ? new Date(snapshot.created_at).toLocaleString() : "-"}
              </Descriptions.Item>
            </Descriptions>
            <JsonBlock title="target_outline_node" value={snapshot.target_outline_node} />
            <JsonBlock title="variable_inputs" value={snapshot.variable_inputs} />
            <JsonBlock title="retrieval_trace_summary" value={snapshot.retrieval_trace_summary} />
            <JsonBlock title="input_priority_layers" value={snapshot.input_priority_layers} />
            <JsonBlock title="requirement_context_snapshot" value={snapshot.requirement_context_snapshot} />
            <JsonBlock title="suggestion_snapshot" value={snapshot.suggestion_snapshot} />
            <JsonBlock title="conflict_hints" value={snapshot.conflict_hints} />
            <JsonBlock title="missing_material_hints" value={snapshot.missing_material_hints} />
          </Space>
        )}
      </Spin>
    </Drawer>
  );
}
