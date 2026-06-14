import { Form, Input, Modal, Radio, message } from "antd";
import { useState } from "react";
import {
  batchConfirmCandidates,
  batchRejectCandidates,
  type BatchConfirmItem,
  type BatchOperationResult,
  type CandidateListItem,
} from "../../services/candidates";

export type BatchStrategy = "ku_uniform" | "ignore_all" | "suggested_type";

interface BatchFormValues {
  strategy: BatchStrategy;
  knowledge_type?: string;
  chapter_taxonomy_id?: string;
  batch_comment?: string;
}

export interface BatchConfirmModalProps {
  kbId: string;
  open: boolean;
  selected: CandidateListItem[];
  onClose: () => void;
  onComplete: (result: BatchOperationResult) => void;
}

function mapCandidateTypeToConfirmAs(candidateType: string): BatchConfirmItem["confirm_as"] {
  const mapping: Record<string, BatchConfirmItem["confirm_as"]> = {
    ku: "ku",
    wiki: "wiki",
    template_chapter: "template_chapter",
    manual_asset: "manual_asset",
    chapter_pattern: "chapter_pattern",
    product_category: "product_category",
    ignore: "ignore",
  };
  return mapping[candidateType] ?? "ku";
}

function buildItems(
  selected: CandidateListItem[],
  strategy: BatchStrategy,
  values: BatchFormValues,
): BatchConfirmItem[] {
  if (strategy === "ignore_all") {
    return selected.map((item) => ({
      candidate_id: item.candidate_id,
      confirm_as: "ignore",
      review_comment: values.batch_comment,
    }));
  }

  if (strategy === "ku_uniform") {
    return selected.map((item) => ({
      candidate_id: item.candidate_id,
      confirm_as: "ku",
      knowledge_type: values.knowledge_type,
      chapter_taxonomy_id: values.chapter_taxonomy_id ?? item.suggested_chapter_taxonomy_id ?? undefined,
      product_category_ids: item.suggested_product_category_ids,
      searchable: true,
      review_comment: values.batch_comment,
    }));
  }

  return selected.map((item) => {
    const confirmAs = mapCandidateTypeToConfirmAs(item.candidate_type);
    return {
      candidate_id: item.candidate_id,
      confirm_as: confirmAs,
      knowledge_type: item.suggested_knowledge_type ?? undefined,
      chapter_taxonomy_id: item.suggested_chapter_taxonomy_id ?? undefined,
      product_category_ids: item.suggested_product_category_ids,
      searchable: true,
      review_comment: values.batch_comment,
    };
  });
}

export default function BatchConfirmModal({
  kbId,
  open,
  selected,
  onClose,
  onComplete,
}: BatchConfirmModalProps) {
  const [form] = Form.useForm<BatchFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const strategy = Form.useWatch("strategy", form) ?? "ku_uniform";

  const handleOk = async () => {
    if (selected.length === 0) {
      message.warning("请先选择候选");
      return;
    }
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      let result: BatchOperationResult;
      if (values.strategy === "ignore_all") {
        result = await batchRejectCandidates(kbId, {
          candidate_ids: selected.map((item) => item.candidate_id),
          review_comment: values.batch_comment,
        });
      } else {
        result = await batchConfirmCandidates(kbId, {
          items: buildItems(selected, values.strategy, values),
          batch_comment: values.batch_comment,
        });
      }
      message.success(`批量操作完成：成功 ${result.succeeded}，失败 ${result.failed}`);
      onComplete(result);
      onClose();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={`批量确认（已选 ${selected.length} 条）`}
      open={open}
      onCancel={onClose}
      onOk={() => void handleOk()}
      okText="提交"
      confirmLoading={submitting}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ strategy: "ku_uniform" as BatchStrategy }}
      >
        <Form.Item name="strategy" label="批量策略">
          <Radio.Group>
            <Radio value="ku_uniform">统一发布为 KU</Radio>
            <Radio value="suggested_type">逐条沿用建议类型</Radio>
            <Radio value="ignore_all">全部忽略</Radio>
          </Radio.Group>
        </Form.Item>
        {strategy === "ku_uniform" ? (
          <>
            <Form.Item
              name="knowledge_type"
              label="knowledge_type"
              rules={[{ required: true, message: "请输入 knowledge_type" }]}
            >
              <Input placeholder="例如：solution" />
            </Form.Item>
            <Form.Item name="chapter_taxonomy_id" label="chapter_taxonomy_id">
              <Input placeholder="章节类型 UUID（可留空，沿用各条建议值）" />
            </Form.Item>
          </>
        ) : null}
        <Form.Item name="batch_comment" label="批次备注">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
