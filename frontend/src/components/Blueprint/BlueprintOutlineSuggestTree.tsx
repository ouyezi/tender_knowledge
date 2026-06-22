import { Card, Tag, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useMemo, useState } from "react";
import type { SuggestOutlineNode } from "../../services/blueprints";
import { getImportanceLevelLabel } from "../../constants/blueprintMeta";

const { Text, Paragraph } = Typography;

interface BlueprintOutlineSuggestTreeProps {
  nodes: SuggestOutlineNode[];
}

function getNodeByPath(nodes: SuggestOutlineNode[], path: string): SuggestOutlineNode | undefined {
  if (!path) {
    return undefined;
  }
  const parts = path.split("-").map((part) => Number(part));
  let current: SuggestOutlineNode[] = nodes;
  let found: SuggestOutlineNode | undefined;
  for (const index of parts) {
    found = current[index];
    if (!found) {
      return undefined;
    }
    current = found.children ?? [];
  }
  return found;
}

function toTreeData(nodes: SuggestOutlineNode[], parentPath = ""): DataNode[] {
  return nodes.map((node, index) => {
    const path = parentPath ? `${parentPath}-${index}` : String(index);
    const title = node.title?.trim() || "(未命名章节)";
    return {
      key: path,
      title,
      children: toTreeData(node.children ?? [], path),
    };
  });
}

function SuggestNodeDetailPanel({ node }: { node: SuggestOutlineNode }) {
  const hasChildren = (node.children?.length ?? 0) > 0;
  const reason = hasChildren ? node.split_reason : node.no_split_reason;
  const reasonLabel = hasChildren ? "拆分理由" : "不拆分理由";

  return (
    <Card size="small" title={node.title?.trim() || "(未命名章节)"}>
      <Paragraph style={{ marginBottom: 8 }}>
        <Text type="secondary">重要程度：</Text>
        <Tag style={{ marginLeft: 4 }}>{getImportanceLevelLabel(node.importance)}</Tag>
      </Paragraph>
      <Paragraph style={{ marginBottom: 8 }}>
        <Text strong>内容建议</Text>
        <br />
        <Text>{node.content_suggestion}</Text>
      </Paragraph>
      {reason ? (
        <Paragraph style={{ marginBottom: 0 }}>
          <Text strong>{reasonLabel}</Text>
          <br />
          <Text type="secondary">{reason}</Text>
        </Paragraph>
      ) : null}
    </Card>
  );
}

export default function BlueprintOutlineSuggestTree({ nodes }: BlueprintOutlineSuggestTreeProps) {
  const [selectedPath, setSelectedPath] = useState<string>();
  const treeData = useMemo(() => toTreeData(nodes), [nodes]);
  const selectedNode = useMemo(
    () => (selectedPath ? getNodeByPath(nodes, selectedPath) : undefined),
    [nodes, selectedPath],
  );

  useEffect(() => {
    setSelectedPath(undefined);
  }, [nodes]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Tree
        treeData={treeData}
        selectedKeys={selectedPath ? [selectedPath] : []}
        onSelect={(keys) => setSelectedPath(keys[0] as string | undefined)}
      />
      {selectedNode ? (
        <SuggestNodeDetailPanel node={selectedNode} />
      ) : (
        <Text type="secondary">点击章节查看内容建议与说明</Text>
      )}
    </div>
  );
}
