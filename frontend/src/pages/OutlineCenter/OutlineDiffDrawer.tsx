import { Button, Drawer, Empty, List, Space, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useState } from "react";
import {
  applyDiff,
  listDiffs,
  rejectDiff,
  type BidOutlineDiffItem,
} from "../../services/bidOutlines";

type OutlineDiffDrawerProps = {
  open: boolean;
  kbId?: string;
  bidOutlineId?: string;
  onClose: () => void;
  onApplied: () => Promise<void> | void;
};

function readDiffIds(items: Array<Record<string, unknown>> | undefined, key = "outline_node_id"): string[] {
  return (items ?? [])
    .map((item) => item[key])
    .filter((value): value is string => typeof value === "string");
}

function buildApplyPayload(diff: BidOutlineDiffItem) {
  const payload = diff.diff_payload ?? {};
  return {
    accept_added: true,
    accept_removed_ids: readDiffIds(payload.removed),
    accept_renamed_ids: readDiffIds(payload.renamed),
    accept_moved_ids: readDiffIds(payload.moved),
  };
}

export default function OutlineDiffDrawer({
  open,
  kbId,
  bidOutlineId,
  onClose,
  onApplied,
}: OutlineDiffDrawerProps) {
  const [items, setItems] = useState<BidOutlineDiffItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!kbId || !bidOutlineId) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const result = await listDiffs(kbId, bidOutlineId, { page_size: 100 });
      setItems(result.items ?? []);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [bidOutlineId, kbId]);

  useEffect(() => {
    if (open) {
      void reload();
    }
  }, [open, reload]);

  const handleApply = async (item: BidOutlineDiffItem) => {
    if (!kbId || !bidOutlineId) return;
    setSavingId(item.diff_id);
    try {
      await applyDiff(kbId, bidOutlineId, item.diff_id, buildApplyPayload(item));
      message.success("差异已应用");
      await reload();
      await onApplied();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSavingId(null);
    }
  };

  const handleReject = async (item: BidOutlineDiffItem) => {
    if (!kbId || !bidOutlineId) return;
    setSavingId(item.diff_id);
    try {
      await rejectDiff(kbId, bidOutlineId, item.diff_id);
      message.success("差异已拒绝");
      await reload();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSavingId(null);
    }
  };

  return (
    <Drawer
      title="重解析差异"
      width={680}
      open={open}
      onClose={onClose}
      extra={<Button onClick={() => void reload()}>刷新</Button>}
    >
      <List
        loading={loading}
        dataSource={items}
        locale={{ emptyText: <Empty description="暂无差异" /> }}
        renderItem={(item) => {
          const diffPayloadText = JSON.stringify(item.diff_payload ?? {}, null, 2);
          const pending = item.status === "pending";
          const busy = savingId === item.diff_id;
          return (
            <List.Item
              actions={[
                <Button
                  key="apply"
                  type="primary"
                  disabled={!pending}
                  loading={busy}
                  onClick={() => void handleApply(item)}
                >
                  应用
                </Button>,
                <Button
                  key="reject"
                  danger
                  disabled={!pending}
                  loading={busy}
                  onClick={() => void handleReject(item)}
                >
                  拒绝
                </Button>,
              ]}
            >
              <Space direction="vertical" size={4} style={{ width: "100%" }}>
                <Space>
                  <Typography.Text strong>{item.diff_id}</Typography.Text>
                  <Tag color={pending ? "warning" : "default"}>{item.status}</Tag>
                </Space>
                <Typography.Text type="secondary">解析任务：{item.parse_task_id}</Typography.Text>
                <Typography.Text type="secondary">
                  创建时间：{item.created_at ? new Date(item.created_at).toLocaleString() : "-"}
                </Typography.Text>
                <Typography.Paragraph
                  code
                  style={{ marginBottom: 0, whiteSpace: "pre-wrap", fontSize: 12, maxHeight: 220, overflow: "auto" }}
                >
                  {diffPayloadText}
                </Typography.Paragraph>
              </Space>
            </List.Item>
          );
        }}
      />
    </Drawer>
  );
}
