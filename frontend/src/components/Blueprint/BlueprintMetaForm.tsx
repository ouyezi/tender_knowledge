import { Col, Form, Input, InputNumber, Row, Select } from "antd";
import { TEMPLATE_STYLE_OPTIONS } from "../../constants/blueprintMeta";
import type { BlueprintDraft } from "../../services/blueprints";

interface BlueprintMetaFormProps {
  value: BlueprintDraft;
  readOnly?: boolean;
  onChange: (next: BlueprintDraft) => void;
}

function nextArrayValue(value?: string[]) {
  return value?.length ? value : [];
}

export default function BlueprintMetaForm({ value, readOnly, onChange }: BlueprintMetaFormProps) {
  const patch = (partial: Partial<BlueprintDraft>) => onChange({ ...value, ...partial });

  return (
    <Form layout="vertical">
      <Row gutter={12}>
        <Col xs={24} md={12}>
          <Form.Item label="蓝图名称" required>
            <Input
              value={value.name}
              placeholder="请输入蓝图名称"
              readOnly={readOnly}
              onChange={(event) => patch({ name: event.target.value })}
            />
          </Form.Item>
        </Col>
        <Col xs={24} md={12}>
          <Form.Item label="版本">
            <InputNumber
              style={{ width: "100%" }}
              min={1}
              value={value.version}
              disabled={readOnly}
              onChange={(next) => patch({ version: next ?? undefined })}
            />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item label="蓝图描述">
        <Input.TextArea
          rows={2}
          value={value.description ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ description: event.target.value || null })}
        />
      </Form.Item>

      <Row gutter={12}>
        <Col xs={24} md={12}>
          <Form.Item label="产品标签">
            <Select
              mode="tags"
              value={nextArrayValue(value.product_tags)}
              disabled={readOnly}
              onChange={(next) => patch({ product_tags: next })}
            />
          </Form.Item>
        </Col>
        <Col xs={24} md={12}>
          <Form.Item label="行业标签">
            <Select
              mode="tags"
              value={nextArrayValue(value.industry_tags)}
              disabled={readOnly}
              onChange={(next) => patch({ industry_tags: next })}
            />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={12}>
        <Col xs={24} md={12}>
          <Form.Item label="场景标签">
            <Select
              mode="tags"
              value={nextArrayValue(value.scenario_tags)}
              disabled={readOnly}
              onChange={(next) => patch({ scenario_tags: next })}
            />
          </Form.Item>
        </Col>
        <Col xs={24} md={12}>
          <Form.Item label="适用项目类型">
            <Select
              mode="tags"
              value={nextArrayValue(value.applicable_project_type)}
              disabled={readOnly}
              onChange={(next) => patch({ applicable_project_type: next })}
            />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={12}>
        <Col xs={24} md={12}>
          <Form.Item label="模板风格">
            <Select
              allowClear
              placeholder="请选择模板风格"
              options={TEMPLATE_STYLE_OPTIONS}
              value={value.template_style ?? undefined}
              disabled={readOnly}
              onChange={(next) => patch({ template_style: next ?? null })}
            />
          </Form.Item>
        </Col>
        <Col xs={24} md={12}>
          <Form.Item label="常见篇幅范围">
            <Input
              value={value.usual_page_range ?? ""}
              placeholder="例如：30-50页"
              readOnly={readOnly}
              onChange={(event) => patch({ usual_page_range: event.target.value || null })}
            />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item label="整体编写策略">
        <Input.TextArea
          rows={3}
          value={value.overall_strategy ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ overall_strategy: event.target.value || null })}
        />
      </Form.Item>

      <Form.Item label="相关法规/标准">
        <Select
          mode="tags"
          value={nextArrayValue(value.related_regulations)}
          disabled={readOnly}
          onChange={(next) => patch({ related_regulations: next })}
        />
      </Form.Item>

      <Form.Item label="常见问题/错误">
        <Input.TextArea
          rows={3}
          value={value.common_mistakes ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ common_mistakes: event.target.value || null })}
        />
      </Form.Item>
    </Form>
  );
}
