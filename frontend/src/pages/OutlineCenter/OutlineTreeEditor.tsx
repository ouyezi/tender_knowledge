import { Button, Card, Tag, Tree } from "antd";
import type { DataNode, TreeProps } from "antd/es/tree";
import { useState } from "react";
import type { BidOutlineNode } from "../../services/bidOutlines";

export type OutlineTreeNode = BidOutlineNode & { children: OutlineTreeNode[] };

type OutlineTreeEditorProps = {
  roots: OutlineTreeNode[];
  selectedId: string | null;
  onSelect: (outlineNodeId: string) => void;
  onDropNode: (dragId: string, dropId: string, dropToGap: boolean) => void;
  onViewContent?: (outlineNodeId: string) => void;
};

function toTreeData(
  nodes: OutlineTreeNode[],
  hoveredId: string | null,
  setHoveredId: (id: string | null) => void,
  onViewContent?: (outlineNodeId: string) => void,
): DataNode[] {
  return nodes.map((node) => ({
    key: node.outline_node_id,
    title: (
      <span
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
        onMouseEnter={() => setHoveredId(node.outline_node_id)}
        onMouseLeave={() => setHoveredId(null)}
      >
        <span>
          {node.title} <Tag style={{ marginInlineStart: 8 }}>L{node.level}</Tag>
        </span>
        {onViewContent && hoveredId === node.outline_node_id ? (
          <Button
            type="link"
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              onViewContent(node.outline_node_id);
            }}
          >
            查看内容
          </Button>
        ) : null}
      </span>
    ),
    children: toTreeData(node.children ?? [], hoveredId, setHoveredId, onViewContent),
  }));
}

export default function OutlineTreeEditor({
  roots,
  selectedId,
  onSelect,
  onDropNode,
  onViewContent,
}: OutlineTreeEditorProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const handleDrop: TreeProps["onDrop"] = (info) => {
    const dragId = String(info.dragNode.key);
    const dropId = String(info.node.key);
    onDropNode(dragId, dropId, Boolean(info.dropToGap));
  };

  return (
    <Card size="small" title="目录树（可拖拽）">
      <Tree
        draggable
        blockNode
        defaultExpandAll
        treeData={toTreeData(roots, hoveredId, setHoveredId, onViewContent)}
        selectedKeys={selectedId ? [selectedId] : []}
        onSelect={(keys) => {
          const key = keys[0];
          if (key) onSelect(String(key));
        }}
        onDrop={handleDrop}
      />
    </Card>
  );
}
