import { Col, Form, Input, Row } from "antd";

interface WritingTechniqueGuidanceSectionProps {
  readOnly?: boolean;
}

export default function WritingTechniqueGuidanceSection({ readOnly }: WritingTechniqueGuidanceSectionProps) {
  return (
    <Row gutter={12}>
      <Col xs={24}>
        <Form.Item name="recommended_outline" label="推荐结构">
          <Input.TextArea rows={4} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="writing_strategy" label="写作策略">
          <Input.TextArea rows={4} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="must_include" label="必写要点">
          <Input.TextArea rows={4} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="output_requirement" label="输出要求">
          <Input.TextArea rows={3} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="checklist" label="自检清单">
          <Input.TextArea rows={3} disabled={readOnly} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Form.Item name="notes" label="备注">
          <Input.TextArea rows={3} disabled={readOnly} />
        </Form.Item>
      </Col>
    </Row>
  );
}
