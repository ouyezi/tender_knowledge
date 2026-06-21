import { Button, Input, Modal, Select, Space, Tag, Tree, Typography, message } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import type { DataNode } from "antd/es/tree";
import { useMemo, useState } from "react";
import {
  IMPORTANCE_LEVEL_OPTIONS,
  getImportanceLevelLabel,
} from "../../constants/blueprintMeta";
import type { BlueprintNode, ImportanceLevel } from "../../services/blueprints";

const { Text } = Typography;

interface BlueprintOutlineTreeProps {
  nodes: BlueprintNode[];
  selectedPath?: string;
  onChange: (nextNodes: BlueprintNode[]) => void;
  onSelectNode: (path?: string) => void;
}

function parsePath(path: string): number[] {
  return path.split("-").map((part) => Number(part));
}

function updateByPath(
  nodes: BlueprintNode[],
  path: number[],
  updater: (target: BlueprintNode) => BlueprintNode,
): BlueprintNode[] {
  if (!path.length) {
    return nodes;
  }
  const [index, ...rest] = path;
  return nodes.map((node, currentIndex) => {
    if (currentIndex !== index) {
      return node;
    }
    if (!rest.length) {
      return updater(node);
    }
    return {
      ...node,
      children: updateByPath(node.children ?? [], rest, updater),
    };
  });
}

function removeByPath(nodes: BlueprintNode[], path: number[]): BlueprintNode[] {
  if (!path.length) {
    return nodes;
  }
  const [index, ...rest] = path;
  if (!rest.length) {
    return nodes.filter((_, currentIndex) => currentIndex !== index);
  }
  return nodes.map((node, currentIndex) => {
    if (currentIndex !== index) {
      return node;
    }
    return {
      ...node,
      children: removeByPath(node.children ?? [], rest),
    };
  });
}

function nodeDepth(path: string): number {
  return parsePath(path).length;
}

function createNode(level: number): BlueprintNode {
  return {
    node_title: "新章节",
    node_level: level,
    importance_level: "optional",
    children: [],
  };
}

export default function BlueprintOutlineTree({
  nodes,
  selectedPath,
  onChange,
  onSelectNode,
}: BlueprintOutlineTreeProps) {
  const [editingPath, setEditingPath] = useState<string>();
  const [editingTitle, setEditingTitle] = useState("");

  const commitTitle = () => {
    if (!editingPath) {
      return;
    }
    const title = editingTitle.trim() || "未命名章节";
    onChange(updateByPath(nodes, parsePath(editingPath), (target) => ({ ...target, node_title: title })));
    setEditingPath(undefined);
  };

  const updateImportance = (path: string, level: ImportanceLevel) => {
    onChange(updateByPath(nodes, parsePath(path), (target) => ({ ...target, importance_level: level })));
  };

  const addRootNode = () => {
    onChange([...nodes, createNode(1)]);
  };

  const addChildNode = () => {
    if (!selectedPath) {
      message.warning("请先选择父节点");
      return;
    }
    const childLevel = nodeDepth(selectedPath) + 1;
    onChange(
      updateByPath(nodes, parsePath(selectedPath), (target) => ({
        ...target,
        children: [...(target.children ?? []), createNode(childLevel)],
      })),
    );
  };

  const deleteNode = (path: string) => {
    Modal.confirm({
      title: "确认删除该章节？",
      content: "删除后该章节及其子节点将不可恢复。",
      okText: "删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: () => {
        const nextNodes = removeByPath(nodes, parsePath(path));
        onChange(nextNodes);
        if (selectedPath === path || selectedPath?.startsWith(`${path}-`)) {
          onSelectNode(undefined);
        }
      },
    });
  };

  const treeData = useMemo<DataNode[]>(() => {
    const toData = (source: BlueprintNode[], parentPath = ""): DataNode[] =>
      source.map((node, index) => {
        const path = parentPath ? `${parentPath}-${index}` : String(index);
        const isEditing = editingPath === path;
        return {
          key: path,
          title: (
            <Space size={8} wrap onClick={(event) => event.stopPropagation()}>
              {isEditing ? (
                <Input
                  autoFocus
                  size="small"
                  value={editingTitle}
                  style={{ width: 220 }}
                  onChange={(event) => setEditingTitle(event.target.value)}
                  onPressEnter={commitTitle}
                  onBlur={commitTitle}
                />
              ) : (
                <Text
                  style={{ cursor: "pointer" }}
                  onClick={() => onSelectNode(path)}
                  ellipsis={{ tooltip: node.node_title || "(未命名章节)" }}
                >
                  {node.node_title || "(未命名章节)"}
                </Text>
              )}
              <Tag color={node.importance_level === "required" ? "red" : "blue"}>
                {getImportanceLevelLabel(node.importance_level)}
              </Tag>
              <Select
                size="small"
                style={{ width: 90 }}
                options={IMPORTANCE_LEVEL_OPTIONS}
                value={node.importance_level}
                onChange={(next) => updateImportance(path, next)}
              />
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => {
                  setEditingPath(path);
                  setEditingTitle(node.node_title || "");
                }}
              />
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => deleteNode(path)}
              />
            </Space>
          ),
          children: toData(node.children ?? [], path),
        };
      });
    return toData(nodes);
  }, [commitTitle, deleteNode, editingPath, editingTitle, nodes, onSelectNode]);

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Tree
        blockNode
        treeData={treeData}
        selectedKeys={selectedPath ? [selectedPath] : []}
        onSelect={(keys) => onSelectNode(keys[0] as string | undefined)}
      />
      <Space wrap>
        <Button icon={<PlusOutlined />} onClick={addRootNode}>
          添加一级章节
        </Button>
        <Button icon={<PlusOutlined />} onClick={addChildNode}>
          添加子节点
        </Button>
      </Space>
    </Space>
  );
}
