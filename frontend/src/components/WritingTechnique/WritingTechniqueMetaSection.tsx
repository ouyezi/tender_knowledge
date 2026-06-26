import { Col, Form, Input, InputNumber, Row, Select } from "antd";
import type { WritingTechniqueUsageMode } from "../../services/writingTechniques";

const USAGE_MODE_OPTIONS: Array<{ label: string; value: WritingTechniqueUsageMode }> = [
  { label: "直接套用", value: "DIRECT" },
  { label: "参考改写", value: "REFERENCE" },
  { label: "要点提炼", value: "EXTRACT" },
];

interface WritingTechniqueMetaSectionProps {
  readOnly?: boolean;
}

export default function WritingTechniqueMetaSection({ readOnly }: WritingTechniqueMetaSectionProps) {
  return (
    <Row gutter={12}>
      <Col xs={24} lg={12}>
        <Form.Item
          name="title"
          label="技巧标题"
          rules={[{ required: true, message: "请输入技巧标题" }, { max: 100, message: "标题不能超过 100 字" }]}
        >
          <Input maxLength={100} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24} lg={12}>
        <Form.Item name="usage_mode" label="使用方式">
          <Select options={USAGE_MODE_OPTIONS} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="applicable_scene" label="适用场景">
          <Input.TextArea rows={2} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="writing_summary" label="技巧摘要">
          <Input.TextArea rows={2} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24} lg={12}>
        <Form.Item name="applicable_sections" label="适用章节">
          <Select mode="tags" allowClear disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24} lg={12}>
        <Form.Item name="tags" label="标签">
          <Select mode="tags" allowClear disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24} lg={8}>
        <Form.Item name="confidence" label="置信度">
          <InputNumber min={0} max={100} precision={0} style={{ width: "100%" }} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24} lg={8}>
        <Form.Item name="source_chunk_id" label="来源 Chunk ID">
          <InputNumber min={1} precision={0} style={{ width: "100%" }} disabled={readOnly} />
        </Form.Item>
      </Col>
    </Row>
  );
}
