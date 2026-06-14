import { Form, Input, Modal, Select, message } from "antd";
import { useEffect } from "react";
import { mergeCandidates, type CandidateListItem } from "../../services/candidates";

interface MergeFormValues {
  target_candidate_id: string;
  title: string;
  summary?: string;
  content?: string;
  review_comment?: string;
}

export interface CandidateMergeModalProps {
  kbId: string;
  open: boolean;
  selected: CandidateListItem[];
  onClose: () => void;
  onSuccess: () => void;
}

export default function CandidateMergeModal({
  kbId,
  open,
  selected,
  onClose,
  onSuccess,
}: CandidateMergeModalProps) {
  const [form] = Form.useForm<MergeFormValues>();

  useEffect(() => {
    if (!open || selected.length < 2) {
      return;
    }
    const target = selected[0];
    form.setFieldsValue({
      target_candidate_id: target.candidate_id,
      title: target.title,
      summary: target.summary,
    });
  }, [form, open, selected]);

  const handleOk = async () => {
    if (selected.length < 2) {
      message.warning("请至少选择 2 条候选进行合并");
      return;
    }
    const values = await form.validateFields();
    const sourceIds = selected
      .map((item) => item.candidate_id)
      .filter((id) => id !== values.target_candidate_id);
    if (sourceIds.length === 0) {
      message.warning("合并目标不能与唯一来源相同");
      return;
    }
    try {
      await mergeCandidates(kbId, {
        target_candidate_id: values.target_candidate_id,
        source_candidate_ids: sourceIds,
        title: values.title,
        summary: values.summary,
        content: values.content,
        review_comment: values.review_comment,
      });
      message.success("合并成功");
      onSuccess();
      onClose();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  return (
    <Modal
      title="合并候选"
      open={open}
      onCancel={onClose}
      onOk={() => void handleOk()}
      okText="确认合并"
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="target_candidate_id"
          label="合并目标"
          rules={[{ required: true, message: "请选择合并目标" }]}
        >
          <Select
            options={selected.map((item) => ({
              value: item.candidate_id,
              label: item.title || item.candidate_id,
            }))}
          />
        </Form.Item>
        <Form.Item name="title" label="合并后标题" rules={[{ required: true, message: "请输入标题" }]}>
          <Input />
        </Form.Item>
        <Form.Item name="summary" label="摘要">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="content" label="内容">
          <Input.TextArea rows={6} />
        </Form.Item>
        <Form.Item name="review_comment" label="备注">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
