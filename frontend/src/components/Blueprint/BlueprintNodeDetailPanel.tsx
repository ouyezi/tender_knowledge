import { Form, Input, Radio, Typography } from "antd";
import { IMPORTANCE_LEVEL_OPTIONS } from "../../constants/blueprintMeta";
import type { BlueprintNode } from "../../services/blueprints";

const { Text } = Typography;

interface BlueprintNodeDetailPanelProps {
  node?: BlueprintNode;
  readOnly?: boolean;
  onChange: (next: BlueprintNode) => void;
}

export default function BlueprintNodeDetailPanel({
  node,
  readOnly,
  onChange,
}: BlueprintNodeDetailPanelProps) {
  if (!node) {
    return <Text type="secondary">请选择左侧章节节点查看详情</Text>;
  }

  const patch = (partial: Partial<BlueprintNode>) => onChange({ ...node, ...partial });

  return (
    <Form layout="vertical">
      <Form.Item label="章节标题">
        <Input value={node.node_title} readOnly />
      </Form.Item>

      <Form.Item label="节点编码">
        <Input
          value={node.node_code ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ node_code: event.target.value || null || undefined })}
          placeholder="例如：1.2.3"
        />
      </Form.Item>

      <Form.Item label="重要程度">
        <Radio.Group
          options={IMPORTANCE_LEVEL_OPTIONS}
          optionType="button"
          buttonStyle="solid"
          value={node.importance_level}
          disabled={readOnly}
          onChange={(event) => patch({ importance_level: event.target.value })}
        />
      </Form.Item>

      <Form.Item label="内容描述">
        <Input.TextArea
          rows={2}
          value={node.content_description ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ content_description: event.target.value || null })}
          placeholder="本章应写什么（1-2 句）"
        />
      </Form.Item>

      <Form.Item label="应标/得分/应答提示">
        <Input.TextArea
          rows={2}
          value={node.tender_response_hint ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ tender_response_hint: event.target.value || null })}
          placeholder="从历史章节推断，遇则填写，可留空"
        />
      </Form.Item>
    </Form>
  );
}
