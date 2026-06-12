import { PlusOutlined } from "@ant-design/icons";
import { Button, Card, Space, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import { useMemo } from "react";
import type { ProductCategoryNode } from "../services/productCategoryApi";

interface CategoryTreePanelProps {
  nodes: ProductCategoryNode[];
  selectedId?: string;
  readOnly?: boolean;
  loading?: boolean;
  onSelect: (categoryId: string) => void;
  onCreateRoot: () => void;
  onCreateChild: (parentId: string) => void;
}

function toTreeData(nodes: ProductCategoryNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.category_id,
    title: node.category_name,
    children: toTreeData(node.children),
  }));
}

export default function CategoryTreePanel({
  nodes,
  selectedId,
  readOnly = false,
  loading = false,
  onSelect,
  onCreateRoot,
  onCreateChild,
}: CategoryTreePanelProps) {
  const treeData = useMemo(() => toTreeData(nodes), [nodes]);

  return (
    <Card
      title="分类树"
      loading={loading}
      extra={
        <Space>
          {selectedId && !readOnly ? (
            <Button onClick={() => onCreateChild(selectedId)}>添加子分类</Button>
          ) : null}
          <Button type="primary" disabled={readOnly} onClick={onCreateRoot}>
            新建分类
          </Button>
        </Space>
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
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
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
            {!readOnly && typeof node.key === "string" ? (
              <Button
                type="text"
                size="small"
                icon={<PlusOutlined />}
                aria-label="添加子分类"
                onClick={(event) => {
                  event.stopPropagation();
                  onCreateChild(node.key as string);
                }}
              />
            ) : null}
          </div>
        )}
      />
      <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
        选中节点后点击 + 或双击节点，可添加子分类
      </Typography.Text>
    </Card>
  );
}
