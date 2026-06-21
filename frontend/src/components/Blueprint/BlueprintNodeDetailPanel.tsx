import { Form, Input, Radio, Select, Space, Typography } from "antd";
import { CONTENT_TYPE_OPTIONS, IMPORTANCE_LEVEL_OPTIONS } from "../../constants/blueprintMeta";
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

      <Form.Item label="内容类型">
        <Select
          allowClear
          placeholder="请选择内容类型"
          options={CONTENT_TYPE_OPTIONS}
          value={node.content_type ?? undefined}
          disabled={readOnly}
          onChange={(next) => patch({ content_type: next ?? null })}
        />
      </Form.Item>

      <Form.Item label="编写目的">
        <Input.TextArea
          rows={3}
          value={node.purpose ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ purpose: event.target.value || null })}
        />
      </Form.Item>

      <Form.Item label="写作目标">
        <Input.TextArea
          rows={3}
          value={node.writing_goal ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ writing_goal: event.target.value || null })}
        />
      </Form.Item>

      <Form.Item label="写作提示">
        <Input.TextArea
          rows={4}
          value={node.writing_hint ?? ""}
          readOnly={readOnly}
          onChange={(event) => patch({ writing_hint: event.target.value || null })}
        />
      </Form.Item>

      <Form.Item label="关键词提示">
        <Select
          mode="tags"
          value={node.keyword_hint ?? []}
          disabled={readOnly}
          onChange={(next) => patch({ keyword_hint: next })}
        />
      </Form.Item>

      {!readOnly ? (
        <Space>
          <Text type="secondary">提示：左侧可编辑章节标题与层级，右侧编辑节点细节。</Text>
        </Space>
      ) : null}
    </Form>
  );
}
