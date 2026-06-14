import { Button, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createRetrievalFeedback,
  listRetrievalEvalSets,
  listRetrievalFeedback,
  promoteFeedbackToEvalCase,
  type RetrievalFeedbackItem,
  type RetrievalFeedbackType,
} from "../../services/retrievalEval";

const FEEDBACK_TYPE_OPTIONS: Array<{ value: RetrievalFeedbackType; label: string }> = [
  { value: "useful", label: "有用" },
  { value: "not_useful", label: "无用" },
  { value: "false_positive", label: "误召回" },
  { value: "false_negative", label: "漏召回" },
  { value: "adopt", label: "采纳" },
  { value: "click", label: "点击" },
  { value: "copy", label: "复制" },
  { value: "add_to_draft", label: "加入草稿" },
];

interface Props {
  kbId: string;
  readOnly: boolean;
}

function splitIds(raw: string): string[] {
  return raw
    .split(/[\n,]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function FeedbackPanel({ kbId, readOnly }: Props) {
  const [form] = Form.useForm<{
    trace_id: string;
    feedback_type: RetrievalFeedbackType;
    object_type?: string;
    object_id?: string;
    rank_position?: number;
    expected_object_ids?: string;
    comment?: string;
  }>();
  const [list, setList] = useState<RetrievalFeedbackItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedbackTypeFilter, setFeedbackTypeFilter] = useState<RetrievalFeedbackType | undefined>();
  const [traceFilter, setTraceFilter] = useState("");
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [activeFeedback, setActiveFeedback] = useState<RetrievalFeedbackItem | null>(null);
  const [evalSetOptions, setEvalSetOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [evalSetId, setEvalSetId] = useState<string>();
  const [expectedText, setExpectedText] = useState("");
  const [negativeText, setNegativeText] = useState("");

  const loadData = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    try {
      const [feedbackResult, evalSetResult] = await Promise.all([
        listRetrievalFeedback(kbId, {
          feedback_type: feedbackTypeFilter,
          trace_id: traceFilter.trim() || undefined,
          page_size: 50,
        }),
        listRetrievalEvalSets(kbId, { page_size: 100 }),
      ]);
      setList(feedbackResult.items ?? []);
      setEvalSetOptions((evalSetResult.items ?? []).map((item) => ({ label: item.name, value: item.eval_set_id })));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [feedbackTypeFilter, kbId, traceFilter]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleSubmit = useCallback(async () => {
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      await createRetrievalFeedback(kbId, {
        trace_id: values.trace_id,
        feedback_type: values.feedback_type,
        object_type: values.object_type || undefined,
        object_id: values.object_id || undefined,
        rank_position: values.rank_position,
        expected_object_ids: values.expected_object_ids ? splitIds(values.expected_object_ids) : [],
        comment: values.comment || undefined,
      });
      message.success("反馈已提交");
      form.resetFields(["object_type", "object_id", "rank_position", "expected_object_ids", "comment"]);
      await loadData();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  }, [form, kbId, loadData]);

  const columns: ColumnsType<RetrievalFeedbackItem> = useMemo(
    () => [
      {
        title: "类型",
        dataIndex: "feedback_type",
        key: "feedback_type",
        width: 120,
        render: (value: string) => {
          const found = FEEDBACK_TYPE_OPTIONS.find((item) => item.value === value);
          return <Tag>{found?.label ?? value}</Tag>;
        },
      },
      {
        title: "trace_id",
        dataIndex: "trace_id",
        key: "trace_id",
        ellipsis: true,
      },
      {
        title: "对象",
        key: "object",
        render: (_value, record) => `${record.object_type || "-"} / ${record.object_id || "-"}`,
      },
      {
        title: "备注",
        dataIndex: "comment",
        key: "comment",
        ellipsis: true,
        render: (value: string | null) => value || "-",
      },
      {
        title: "时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        render: (value: string) => (value ? new Date(value).toLocaleString() : "-"),
      },
      {
        title: "操作",
        key: "actions",
        width: 140,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            disabled={readOnly}
            onClick={() => {
              setActiveFeedback(record);
              setPromoteOpen(true);
              setEvalSetId(undefined);
              setExpectedText((record.expected_object_ids || []).join("\n"));
              setNegativeText("");
            }}
          >
            晋升评测用例
          </Button>
        ),
      },
    ],
    [readOnly],
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Form form={form} layout="inline" initialValues={{ feedback_type: "useful" }} onFinish={() => void handleSubmit()}>
        <Form.Item name="trace_id" label="trace_id" rules={[{ required: true, message: "请输入 trace_id" }]}>
          <Input placeholder="请输入 trace_id" style={{ width: 300 }} />
        </Form.Item>
        <Form.Item name="feedback_type" label="反馈类型" rules={[{ required: true }]}>
          <Select style={{ width: 160 }} options={FEEDBACK_TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item name="object_type" label="对象类型">
          <Input placeholder="ku/wiki..." style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="object_id" label="对象ID">
          <Input placeholder="可选" style={{ width: 220 }} />
        </Form.Item>
        <Form.Item name="rank_position" label="排序位次">
          <InputNumber placeholder="可选" style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="expected_object_ids" label="期望对象ID">
          <Input placeholder="逗号或换行分隔" style={{ width: 220 }} />
        </Form.Item>
        <Form.Item name="comment" label="备注">
          <Input placeholder="可选" style={{ width: 220 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting} disabled={readOnly}>
            提交反馈
          </Button>
        </Form.Item>
      </Form>

      <Space>
        <Select
          allowClear
          placeholder="过滤反馈类型"
          style={{ width: 180 }}
          value={feedbackTypeFilter}
          options={FEEDBACK_TYPE_OPTIONS}
          onChange={(value) => setFeedbackTypeFilter(value)}
        />
        <Input
          placeholder="按 trace_id 过滤"
          style={{ width: 280 }}
          value={traceFilter}
          onChange={(event) => setTraceFilter(event.target.value)}
        />
        <Button onClick={() => void loadData()}>刷新</Button>
      </Space>

      <Table
        rowKey="feedback_id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={list}
        pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
      />

      <Modal
        title="晋升为评测用例"
        open={promoteOpen}
        onCancel={() => setPromoteOpen(false)}
        okText="确认晋升"
        confirmLoading={promoting}
        onOk={() => {
          if (!activeFeedback || !evalSetId) {
            message.warning("请选择评测集");
            return;
          }
          setPromoting(true);
          void promoteFeedbackToEvalCase(kbId, activeFeedback.feedback_id, {
            eval_set_id: evalSetId,
            expected_object_ids: splitIds(expectedText),
            negative_object_ids: splitIds(negativeText),
          })
            .then(() => {
              message.success("已晋升为评测用例");
              setPromoteOpen(false);
            })
            .catch((error: Error) => message.error(error.message))
            .finally(() => setPromoting(false));
        }}
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Select
            placeholder="选择评测集"
            options={evalSetOptions}
            value={evalSetId}
            onChange={setEvalSetId}
          />
          <Input.TextArea
            rows={3}
            placeholder="期望对象ID（逗号或换行分隔）"
            value={expectedText}
            onChange={(event) => setExpectedText(event.target.value)}
          />
          <Input.TextArea
            rows={3}
            placeholder="负例对象ID（逗号或换行分隔）"
            value={negativeText}
            onChange={(event) => setNegativeText(event.target.value)}
          />
        </Space>
      </Modal>
    </Space>
  );
}
