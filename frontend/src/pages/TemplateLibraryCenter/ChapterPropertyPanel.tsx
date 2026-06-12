import { Card, Checkbox, Form, Input, InputNumber } from "antd";
import { useEffect } from "react";
import type { ChapterTreeNode } from "../../services/templates";

type ChapterEditableNode = Omit<ChapterTreeNode, "children">;

type ChapterPropertyPanelProps = {
  selected: ChapterEditableNode | null;
  onChange: (patch: Partial<ChapterEditableNode>) => void;
};

export default function ChapterPropertyPanel({ selected, onChange }: ChapterPropertyPanelProps) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!selected) {
      form.resetFields();
      return;
    }
    form.setFieldsValue({
      title: selected.title,
      level: selected.level,
      sort_order: selected.sort_order,
      required: selected.required,
      is_fixed_section: selected.is_fixed_section,
      ignored: selected.ignored,
    });
  }, [form, selected]);

  return (
    <Card size="small" title="章节属性">
      <Form
        form={form}
        layout="vertical"
        disabled={!selected}
        onValuesChange={(changedValues) => onChange(changedValues)}
      >
        <Form.Item name="title" label="标题">
          <Input placeholder="请输入章节标题" />
        </Form.Item>
        <Form.Item name="level" label="层级">
          <InputNumber min={1} max={9} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="sort_order" label="排序">
          <InputNumber min={0} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="required" valuePropName="checked">
          <Checkbox>必填章节</Checkbox>
        </Form.Item>
        <Form.Item name="is_fixed_section" valuePropName="checked">
          <Checkbox>固定章节</Checkbox>
        </Form.Item>
        <Form.Item name="ignored" valuePropName="checked">
          <Checkbox>忽略</Checkbox>
        </Form.Item>
      </Form>
    </Card>
  );
}
