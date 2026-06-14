import { Card, Tag, Tree } from "antd";
import type { DataNode, TreeProps } from "antd/es/tree";
import type { BidOutlineNode } from "../../services/bidOutlines";

export type OutlineTreeNode = BidOutlineNode & { children: OutlineTreeNode[] };

type OutlineTreeEditorProps = {
  roots: OutlineTreeNode[];
  selectedId: string | null;
  onSelect: (outlineNodeId: string) => void;
  onDropNode: (dragId: string, dropId: string, dropToGap: boolean) => void;
};

function toTreeData(nodes: OutlineTreeNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.outline_node_id,
    title: (
      <span>
        {node.title} <Tag style={{ marginInlineStart: 8 }}>L{node.level}</Tag>
      </span>
    ),
    children: toTreeData(node.children ?? []),
  }));
}

export default function OutlineTreeEditor({
  roots,
  selectedId,
  onSelect,
  onDropNode,
}: OutlineTreeEditorProps) {
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
        treeData={toTreeData(roots)}
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
