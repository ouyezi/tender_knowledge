import { Form, Input, Modal, Radio } from "antd";
import { useEffect } from "react";

type PublishTargetType = "template" | "library";

interface PublishModalValues {
  target_type: PublishTargetType;
  version_note?: string;
  cascade_templates?: boolean;
}

interface PublishModalProps {
  open: boolean;
  targetName: string;
  defaultTargetType: PublishTargetType;
  onCancel: () => void;
  onSubmit: (values: PublishModalValues) => Promise<void>;
  confirmLoading?: boolean;
}

export default function PublishModal({
  open,
  targetName,
  defaultTargetType,
  onCancel,
  onSubmit,
  confirmLoading,
}: PublishModalProps) {
  const [form] = Form.useForm<PublishModalValues>();
  const targetType = Form.useWatch("target_type", form);

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        target_type: defaultTargetType,
        cascade_templates: true,
        version_note: "",
      });
    }
  }, [defaultTargetType, form, open]);

  return (
    <Modal
      title={`发布：${targetName}`}
      open={open}
      onCancel={onCancel}
      confirmLoading={confirmLoading}
      onOk={() => {
        void form.validateFields().then((values) => onSubmit(values));
      }}
      okText="发布"
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item name="target_type" label="发布对象">
          <Radio.Group
            options={[
              { label: "模板", value: "template" },
              { label: "模板库", value: "library" },
            ]}
          />
        </Form.Item>
        {targetType === "library" ? (
          <Form.Item name="cascade_templates" label="级联发布模板">
            <Radio.Group
              options={[
                { label: "是", value: true },
                { label: "否", value: false },
              ]}
            />
          </Form.Item>
        ) : null}
        <Form.Item name="version_note" label="版本备注（可选）">
          <Input.TextArea rows={3} placeholder="例如：首次发布 / 修复规则校验" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
