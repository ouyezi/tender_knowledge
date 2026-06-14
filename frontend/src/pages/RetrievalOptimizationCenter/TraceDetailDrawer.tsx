import { Descriptions, Drawer, Empty, Space, Spin, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { getRetrievalTrace, type RetrievalTraceDetail } from "../../services/retrieval";

interface Props {
  open: boolean;
  kbId: string;
  traceId?: string;
  onClose: () => void;
}

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return "{}";
  }
}

export default function TraceDetailDrawer({ open, kbId, traceId, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<RetrievalTraceDetail | null>(null);

  useEffect(() => {
    if (!open || !kbId || !traceId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    void getRetrievalTrace(kbId, traceId)
      .then((data) => setDetail(data))
      .catch((error: Error) => {
        message.error(error.message);
        setDetail(null);
      })
      .finally(() => setLoading(false));
  }, [open, kbId, traceId]);

  return (
    <Drawer title="Trace 详情" open={open} width={760} onClose={onClose}>
      {loading ? (
        <Spin />
      ) : !detail ? (
        <Empty description="暂无 Trace 详情" />
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="trace_id">
              <Typography.Text code>{detail.trace_id}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={detail.status === "success" ? "green" : detail.status === "failed" ? "red" : "gold"}>
                {detail.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="意图">{detail.intent}</Descriptions.Item>
            <Descriptions.Item label="耗时">{detail.latency_ms} ms</Descriptions.Item>
            <Descriptions.Item label="策略版本">
              {detail.strategy_version_id ? (
                <Typography.Text code>{detail.strategy_version_id}</Typography.Text>
              ) : (
                "-"
              )}
            </Descriptions.Item>
            <Descriptions.Item label="操作人">{detail.operator_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="时间">
              {detail.created_at ? new Date(detail.created_at).toLocaleString() : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="错误信息">{detail.error_message || "-"}</Descriptions.Item>
          </Descriptions>

          <div>
            <Typography.Text strong>请求快照</Typography.Text>
            <Typography.Paragraph>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{prettyJson(detail.request_snapshot)}</pre>
            </Typography.Paragraph>
          </div>
          <div>
            <Typography.Text strong>阶段信息</Typography.Text>
            <Typography.Paragraph>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{prettyJson(detail.stages)}</pre>
            </Typography.Paragraph>
          </div>
          <div>
            <Typography.Text strong>响应摘要</Typography.Text>
            <Typography.Paragraph>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{prettyJson(detail.response_summary)}</pre>
            </Typography.Paragraph>
          </div>
        </Space>
      )}
    </Drawer>
  );
}
