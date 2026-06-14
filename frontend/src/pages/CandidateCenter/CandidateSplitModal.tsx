import { Button, Form, Input, Modal, Select, Space, message } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { splitCandidate, type CandidateListItem } from "../../services/candidates";

interface SplitFormValues {
  review_comment?: string;
  splits: Array<{
    title: string;
    summary?: string;
    content?: string;
    candidate_type?: string;
  }>;
}

export interface CandidateSplitModalProps {
  kbId: string;
  open: boolean;
  candidate?: CandidateListItem;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CandidateSplitModal({
  kbId,
  open,
  candidate,
  onClose,
  onSuccess,
}: CandidateSplitModalProps) {
  const [form] = Form.useForm<SplitFormValues>();

  useEffect(() => {
    if (!open || !candidate) {
      return;
    }
    form.setFieldsValue({
      splits: [
        { title: `${candidate.title}（片段 A）`, candidate_type: candidate.candidate_type },
        { title: `${candidate.title}（片段 B）`, candidate_type: candidate.candidate_type },
      ],
    });
  }, [candidate, form, open]);

  const handleOk = async () => {
    if (!candidate) {
      return;
    }
    if (candidate.source_channel !== "document") {
      message.error("当前仅支持文档通道候选拆分");
      return;
    }
    const values = await form.validateFields();
    try {
      await splitCandidate(kbId, candidate.candidate_id, {
        splits: values.splits,
        review_comment: values.review_comment,
      });
      message.success("拆分成功");
      onSuccess();
      onClose();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  return (
    <Modal
      title={`拆分候选：${candidate?.title ?? ""}`}
      open={open}
      onCancel={onClose}
      onOk={() => void handleOk()}
      okText="确认拆分"
      width={640}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.List name="splits">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field, index) => (
                <Space
                  key={field.key}
                  direction="vertical"
                  style={{ display: "flex", marginBottom: 16, width: "100%" }}
                >
                  <Space align="baseline">
                    <strong>片段 {index + 1}</strong>
                    {fields.length > 2 ? (
                      <MinusCircleOutlined onClick={() => remove(field.name)} />
                    ) : null}
                  </Space>
                  <Form.Item
                    {...field}
                    name={[field.name, "title"]}
                    label="标题"
                    rules={[{ required: true, message: "请输入标题" }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item {...field} name={[field.name, "summary"]} label="摘要">
                    <Input.TextArea rows={2} />
                  </Form.Item>
                  <Form.Item {...field} name={[field.name, "content"]} label="内容">
                    <Input.TextArea rows={4} />
                  </Form.Item>
                  <Form.Item {...field} name={[field.name, "candidate_type"]} label="类型">
                    <Select
                      options={[
                        { value: "ku", label: "知识单元" },
                        { value: "wiki", label: "Wiki" },
                      ]}
                    />
                  </Form.Item>
                </Space>
              ))}
              <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                添加片段
              </Button>
            </>
          )}
        </Form.List>
        <Form.Item name="review_comment" label="备注">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
