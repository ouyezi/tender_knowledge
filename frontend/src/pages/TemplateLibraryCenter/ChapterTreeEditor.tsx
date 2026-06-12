import { Card, Tree } from "antd";
import type { DataNode, TreeProps } from "antd/es/tree";
import type { ChapterTreeNode } from "../../services/templates";

type ChapterTreeEditorProps = {
  roots: ChapterTreeNode[];
  selectedId: string | null;
  onSelect: (chapterId: string) => void;
  onDropNode: (dragId: string, dropId: string | null, dropToGap: boolean) => void;
};

function toTreeData(nodes: ChapterTreeNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.template_chapter_id,
    title: `${node.title} (L${node.level})`,
    children: toTreeData(node.children ?? []),
  }));
}

export default function ChapterTreeEditor({
  roots,
  selectedId,
  onSelect,
  onDropNode,
}: ChapterTreeEditorProps) {
  const handleDrop: TreeProps["onDrop"] = (info) => {
    const dragId = String(info.dragNode.key);
    const dropId = info.dropToGap ? String(info.node.key) : String(info.node.key);
    onDropNode(dragId, dropId, Boolean(info.dropToGap));
  };

  return (
    <Card size="small" title="章节树（可拖拽）">
      <Tree
        draggable
        blockNode
        defaultExpandAll
        treeData={toTreeData(roots)}
        selectedKeys={selectedId ? [selectedId] : []}
        onSelect={(keys) => {
          const key = keys[0];
          if (key) {
            onSelect(String(key));
          }
        }}
        onDrop={handleDrop}
      />
    </Card>
  );
}
