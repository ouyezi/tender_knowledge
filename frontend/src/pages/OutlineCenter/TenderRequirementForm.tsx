import { Button, Form, Input, Space } from "antd";
import { useMemo } from "react";
import type { OutlineNodePayload } from "../../services/retrieval";
import type { TenderRequirementCreatePayload, TenderScorePoint } from "../../services/tenderRequirements";

const { TextArea } = Input;

interface FormValues {
  title: string;
  outline_nodes_text: string;
  score_points_text: string;
  rejection_clauses_text: string;
}

interface Props {
  loading?: boolean;
  defaultOutlineNodes?: OutlineNodePayload[];
  onSubmit: (payload: TenderRequirementCreatePayload) => Promise<void> | void;
}

function parseOutlineNodes(input: string): OutlineNodePayload[] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const levelMatch = line.match(/^L(\d+)\s*[:：\-\s]\s*(.+)$/i);
      if (levelMatch) {
        return {
          title: levelMatch[2].trim(),
          level: Number(levelMatch[1]) || 1,
          sort_order: index,
        };
      }
      return {
        title: line,
        level: 1,
        sort_order: index,
      };
    });
}

function parseScorePoints(input: string): TenderScorePoint[] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const chunks = line.split("|");
      if (chunks.length >= 2) {
        return { node_ref: chunks[0].trim(), text: chunks.slice(1).join("|").trim() };
      }
      return { text: line };
    });
}

function parseLines(input: string): string[] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function TenderRequirementForm({ loading, defaultOutlineNodes = [], onSubmit }: Props) {
  const [form] = Form.useForm<FormValues>();
  const defaultOutlineText = useMemo(
    () => defaultOutlineNodes.map((node) => `L${node.level ?? 1}: ${node.title}`).join("\n"),
    [defaultOutlineNodes],
  );

  return (
    <Form<FormValues>
      layout="vertical"
      form={form}
      initialValues={{
        title: "",
        outline_nodes_text: defaultOutlineText,
        score_points_text: "",
        rejection_clauses_text: "",
      }}
      onFinish={async (values) => {
        await onSubmit({
          title: values.title.trim(),
          outline_nodes: parseOutlineNodes(values.outline_nodes_text),
          score_points: parseScorePoints(values.score_points_text),
          rejection_clauses: parseLines(values.rejection_clauses_text),
        });
      }}
    >
      <Form.Item label="约束标题" name="title" rules={[{ required: true, message: "请输入约束标题" }]}>
        <Input placeholder="例如：XX 项目投标约束" />
      </Form.Item>
      <Form.Item
        label="目录节点"
        name="outline_nodes_text"
        tooltip="每行一个；可用 L2: 标题 形式指定层级"
        rules={[{ required: true, message: "请至少输入一个目录节点" }]}
      >
        <TextArea rows={6} placeholder="L1: 技术方案&#10;L2: 总体架构" />
      </Form.Item>
      <Form.Item label="评分点" name="score_points_text" tooltip="每行一个；可选 node_ref|text 格式">
        <TextArea rows={4} placeholder="总体架构|架构清晰且可扩展" />
      </Form.Item>
      <Form.Item label="废标条款" name="rejection_clauses_text">
        <TextArea rows={4} placeholder="每行一个废标/冲突约束" />
      </Form.Item>
      <Space>
        <Button type="primary" htmlType="submit" loading={loading}>
          保存约束并继续
        </Button>
      </Space>
    </Form>
  );
}
