import { Button, Card, Tree } from "antd";
import type { DataNode } from "antd/es/tree";
import { useMemo } from "react";
import type { ChapterTaxonomyNode } from "../services/chapterTaxonomyApi";

interface TaxonomyTreePanelProps {
  nodes: ChapterTaxonomyNode[];
  selectedId?: string;
  readOnly?: boolean;
  loading?: boolean;
  onSelect: (taxonomyId: string) => void;
  onCreateRoot: () => void;
  onCreateChild: (parentId: string) => void;
}

function toTreeData(nodes: ChapterTaxonomyNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.taxonomy_id,
    title: node.standard_name,
    children: toTreeData(node.children),
  }));
}

export default function TaxonomyTreePanel({
  nodes,
  selectedId,
  readOnly = false,
  loading = false,
  onSelect,
  onCreateRoot,
  onCreateChild,
}: TaxonomyTreePanelProps) {
  const treeData = useMemo(() => toTreeData(nodes), [nodes]);

  return (
    <Card
      title="章节类型树"
      loading={loading}
      extra={
        <Button type="primary" disabled={readOnly} onClick={onCreateRoot}>
          新建章节类型
        </Button>
      }
      styles={{ body: { minHeight: 480 } }}
    >
      <Tree
        showLine
        blockNode
        selectedKeys={selectedId ? [selectedId] : []}
        treeData={treeData}
        onSelect={(keys) => {
          const key = keys[0];
          if (typeof key === "string") {
            onSelect(key);
          }
        }}
        titleRender={(node) => (
          <span
            onDoubleClick={(event) => {
              event.stopPropagation();
              if (!readOnly && typeof node.key === "string") {
                onCreateChild(node.key);
              }
            }}
          >
            {node.title as string}
          </span>
        )}
      />
    </Card>
  );
}
