import { Alert, Button, Card, Col, Divider, Row, Skeleton, Space, Typography } from "antd";
import { useMemo, useState } from "react";
import BlueprintMetaForm from "./BlueprintMetaForm";
import BlueprintNodeDetailPanel from "./BlueprintNodeDetailPanel";
import BlueprintSuggestedStructure from "./BlueprintSuggestedStructure";
import BlueprintOutlineTree from "./BlueprintOutlineTree";
import BlueprintOutlineTreeReadonly from "./BlueprintOutlineTreeReadonly";
import type { BlueprintDraft, BlueprintNode } from "../../services/blueprints";

const BLUEPRINT_PANEL_CARD_BODY_STYLE = {
  minHeight: 420,
  maxHeight: "calc(100vh - 360px)",
  overflow: "auto",
} as const;

const { Text } = Typography;

export interface BlueprintEditorProps {
  mode: "draft" | "edit";
  value: BlueprintDraft;
  loading?: boolean;
  readOnly?: boolean;
  onChange: (next: BlueprintDraft) => void;
  onRegenerate?: () => void;
  onSave: () => void;
  sourceInfo?: { chapterTitle?: string; documentName?: string };
}

function getNodeByPath(nodes: BlueprintNode[], path?: string): BlueprintNode | undefined {
  if (!path) return undefined;
  const parts = path.split("-").map((part) => Number(part));
  let current = nodes;
  let node: BlueprintNode | undefined;
  for (const index of parts) {
    node = current[index];
    if (!node) {
      return undefined;
    }
    current = node.children ?? [];
  }
  return node;
}

function updateNodeByPath(
  nodes: BlueprintNode[],
  path: string,
  updater: (node: BlueprintNode) => BlueprintNode,
): BlueprintNode[] {
  const parts = path.split("-").map((part) => Number(part));
  const update = (source: BlueprintNode[], depth: number): BlueprintNode[] =>
    source.map((node, index) => {
      if (index !== parts[depth]) return node;
      if (depth === parts.length - 1) {
        return updater(node);
      }
      return {
        ...node,
        children: update(node.children ?? [], depth + 1),
      };
    });
  return update(nodes, 0);
}

export default function BlueprintEditor({
  mode,
  value,
  loading,
  readOnly,
  onChange,
  onRegenerate,
  onSave,
  sourceInfo,
}: BlueprintEditorProps) {
  const [selectedPath, setSelectedPath] = useState<string>();

  const selectedNode = useMemo(() => getNodeByPath(value.nodes ?? [], selectedPath), [selectedPath, value.nodes]);

  const handleMetaChange = (next: BlueprintDraft) => {
    onChange(next);
  };

  const handleOutlineChange = (nextNodes: BlueprintNode[]) => {
    onChange({ ...value, nodes: nextNodes });
  };

  const handleNodeChange = (nextNode: BlueprintNode) => {
    if (!selectedPath) {
      return;
    }
    onChange({
      ...value,
      nodes: updateNodeByPath(value.nodes ?? [], selectedPath, () => nextNode),
    });
  };

  if (loading) {
    return (
      <Card>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Text type="secondary">正在分析目录结构，请稍候…</Text>
          <Skeleton active paragraph={{ rows: 8 }} />
        </Space>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {sourceInfo?.chapterTitle || sourceInfo?.documentName ? (
        <Alert
          type="info"
          showIcon
          message={`来源章节：${sourceInfo.chapterTitle || "-"} / 来源文档：${sourceInfo.documentName || "-"}`}
        />
      ) : null}

      <Card title={mode === "draft" ? "目录蓝图草稿" : "目录蓝图编辑"}>
        <BlueprintMetaForm value={value} readOnly={readOnly} onChange={handleMetaChange} />
      </Card>

      <BlueprintSuggestedStructure value={value} readOnly={readOnly} onChange={onChange} />

      <Row gutter={12}>
        <Col xs={24} lg={11}>
          <Card title="目录大纲" styles={{ body: BLUEPRINT_PANEL_CARD_BODY_STYLE }}>
            {readOnly ? (
              <BlueprintOutlineTreeReadonly
                nodes={value.nodes ?? []}
                selectedPath={selectedPath}
                onSelectNode={setSelectedPath}
              />
            ) : (
              <BlueprintOutlineTree
                nodes={value.nodes ?? []}
                selectedPath={selectedPath}
                onSelectNode={setSelectedPath}
                onChange={handleOutlineChange}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={13}>
          <Card title="节点详情" styles={{ body: BLUEPRINT_PANEL_CARD_BODY_STYLE }}>
            <BlueprintNodeDetailPanel node={selectedNode} readOnly={readOnly} onChange={handleNodeChange} />
          </Card>
        </Col>
      </Row>

      <Divider style={{ margin: "4px 0 0 0" }} />
      <Space>
        <Button onClick={onRegenerate} disabled={readOnly || !onRegenerate}>
          重新生成
        </Button>
        <Button type="primary" onClick={onSave} disabled={readOnly || !value.name?.trim() || !value.nodes?.length}>
          保存为蓝图
        </Button>
      </Space>
    </Space>
  );
}
