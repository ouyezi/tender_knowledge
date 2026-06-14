import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  patchCandidate,
  type CandidateDetail,
  type CandidatePatchPayload,
} from "../../services/candidates";

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  pending: { color: "warning", label: "待处理" },
  pending_confirm: { color: "processing", label: "待确认" },
  confirmed: { color: "success", label: "已确认" },
  rejected: { color: "default", label: "已拒绝" },
  published: { color: "success", label: "已发布" },
  merged: { color: "default", label: "已合并" },
};

const SOURCE_CHANNEL_LABEL: Record<string, string> = {
  document: "文档",
  template: "模板",
};

const CANDIDATE_TYPE_LABEL: Record<string, string> = {
  ku: "知识单元",
  wiki: "Wiki",
};

interface EditFormValues {
  title: string;
  summary?: string;
  content?: string;
}

export interface CandidateDetailDrawerProps {
  kbId: string;
  open: boolean;
  loading: boolean;
  detail?: CandidateDetail;
  onClose: () => void;
  onSaved?: (detail: CandidateDetail) => void;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function renderSourceTraceDetail(trace?: CandidateDetail["source_trace"]) {
  if (!trace || Object.keys(trace).length === 0) {
    return <Empty description="暂无来源追溯信息" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  const entries = Object.entries(trace).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );
  return (
    <Descriptions column={1} size="small" bordered>
      {entries.map(([key, value]) => (
        <Descriptions.Item key={key} label={key}>
          {String(value)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

export default function CandidateDetailDrawer({
  kbId,
  open,
  loading,
  detail,
  onClose,
  onSaved,
}: CandidateDetailDrawerProps) {
  const navigate = useNavigate();
  const [form] = Form.useForm<EditFormValues>();
  const [saving, setSaving] = useState(false);
  const editable = detail?.status === "pending";

  useEffect(() => {
    if (!open || loading || !detail || detail.status !== "pending") {
      return;
    }
    form.setFieldsValue({
      title: detail.title,
      summary: detail.summary,
      content: detail.content,
    });
  }, [open, loading, detail, form]);

  const handleSave = useCallback(async () => {
    if (!detail || !editable) {
      return;
    }
    const values = await form.validateFields();
    const payload: CandidatePatchPayload = {};
    if (values.title !== detail.title) {
      payload.title = values.title;
    }
    if (values.summary !== detail.summary) {
      payload.summary = values.summary;
    }
    if (values.content !== detail.content) {
      payload.content = values.content;
    }
    if (Object.keys(payload).length === 0) {
      message.info("没有需要保存的修改");
      return;
    }

    setSaving(true);
    try {
      await patchCandidate(kbId, detail.candidate_id, payload);
      const nextDetail: CandidateDetail = {
        ...detail,
        title: values.title,
        summary: values.summary,
        content: values.content,
      };
      message.success("保存成功");
      onSaved?.(nextDetail);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  }, [detail, editable, form, kbId, onSaved]);

  return (
    <Drawer
      title={detail?.title ?? "候选详情"}
      width={720}
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        detail ? (
          <Space>
            {editable ? (
              <Button type="primary" loading={saving} onClick={() => void handleSave()}>
                保存
              </Button>
            ) : null}
            <Button onClick={() => navigate(`/candidates/confirm/${detail.candidate_id}`)}>
              前往发布
            </Button>
          </Space>
        ) : null
      }
    >
      {loading ? (
        <Spin />
      ) : detail ? (
        <>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="候选 ID">{detail.candidate_id}</Descriptions.Item>
            <Descriptions.Item label="状态">
              {(() => {
                const meta = STATUS_TAG[detail.status] ?? {
                  color: "default",
                  label: detail.status,
                };
                return <Tag color={meta.color}>{meta.label}</Tag>;
              })()}
            </Descriptions.Item>
            <Descriptions.Item label="类型">
              {detail.candidate_type
                ? (CANDIDATE_TYPE_LABEL[detail.candidate_type] ?? detail.candidate_type)
                : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="来源">
              {SOURCE_CHANNEL_LABEL[detail.source_channel] ?? detail.source_channel}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间" span={2}>
              {formatDateTime(detail.created_at)}
            </Descriptions.Item>
          </Descriptions>

          {editable ? (
            <>
              <Typography.Title level={5}>编辑</Typography.Title>
              <Form form={form} layout="vertical" style={{ marginBottom: 16 }}>
                <Form.Item
                  name="title"
                  label="标题"
                  rules={[{ required: true, message: "请输入标题" }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item name="summary" label="摘要">
                  <Input.TextArea rows={3} />
                </Form.Item>
                <Form.Item name="content" label="内容">
                  <Input.TextArea rows={8} />
                </Form.Item>
              </Form>
            </>
          ) : detail.summary ? (
            <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="摘要">{detail.summary}</Descriptions.Item>
            </Descriptions>
          ) : null}

          <Typography.Title level={5}>来源追溯</Typography.Title>
          <div style={{ marginBottom: 16 }}>{renderSourceTraceDetail(detail.source_trace)}</div>

          {!editable ? (
            <>
              <Typography.Title level={5}>内容预览</Typography.Title>
              {detail.content ? (
                <Typography.Paragraph
                  style={{
                    whiteSpace: "pre-wrap",
                    maxHeight: 360,
                    overflow: "auto",
                    marginBottom: 0,
                    padding: 12,
                    background: "#fafafa",
                    borderRadius: 6,
                  }}
                >
                  {detail.content}
                </Typography.Paragraph>
              ) : (
                <Empty description="暂无内容预览" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </>
          ) : null}
        </>
      ) : (
        <Empty description="未找到候选详情" />
      )}
    </Drawer>
  );
}
