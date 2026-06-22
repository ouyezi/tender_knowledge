import { Tag, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import type { ReactNode } from "react";
import type { SuggestOutlineNode } from "../../services/blueprints";
import { getImportanceLevelLabel } from "../../constants/blueprintMeta";

const { Text, Paragraph } = Typography;

interface BlueprintOutlineSuggestTreeProps {
  nodes: SuggestOutlineNode[];
}

function renderNodeMeta(node: SuggestOutlineNode) {
  const hasChildren = (node.children?.length ?? 0) > 0;
  const reason = hasChildren ? node.split_reason : node.no_split_reason;
  const reasonLabel = hasChildren ? "拆分理由" : "不拆分理由";

  return (
    <div style={{ marginTop: 4, marginBottom: 8 }}>
      <Paragraph style={{ marginBottom: 4 }} type="secondary">
        {node.content_suggestion}
      </Paragraph>
      {reason ? (
        <Text type="secondary">
          {reasonLabel}：{reason}
        </Text>
      ) : null}
    </div>
  );
}

function getNodeByPath(nodes: SuggestOutlineNode[], path: string): SuggestOutlineNode | undefined {
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
      title: (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span>{title}</span>
          <Tag>{getImportanceLevelLabel(node.importance)}</Tag>
        </span>
      ),
      children: toTreeData(node.children ?? [], path),
    };
  });
}

export default function BlueprintOutlineSuggestTree({ nodes }: BlueprintOutlineSuggestTreeProps) {
  const treeData = toTreeData(nodes);

  return (
    <Tree
      defaultExpandAll
      treeData={treeData}
      titleRender={(node) => {
        const item = getNodeByPath(nodes, String(node.key));
        if (!item) {
          return node.title as ReactNode;
        }
        return (
          <div>
            {node.title as ReactNode}
            {renderNodeMeta(item)}
          </div>
        );
      }}
    />
  );
}
