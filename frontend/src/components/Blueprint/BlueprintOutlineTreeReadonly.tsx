import { Tree, message } from "antd";
import type { DataNode } from "antd/es/tree";
import type { BlueprintNode } from "../../services/blueprints";
import { getImportanceLevelLabel } from "../../constants/blueprintMeta";

interface BlueprintOutlineTreeReadonlyProps {
  nodes: BlueprintNode[];
  selectedPath?: string;
  onSelectNode?: (path?: string) => void;
}

function toTreeData(nodes: BlueprintNode[], parentPath = ""): DataNode[] {
  return nodes.map((node, index) => {
    const path = parentPath ? `${parentPath}-${index}` : String(index);
    const title = node.node_title?.trim() || "(未命名章节)";
    return {
      key: path,
      title: (
        <span
          role="button"
          tabIndex={0}
          style={{ cursor: "pointer" }}
          onClick={(event) => {
            event.stopPropagation();
            void navigator.clipboard
              .writeText(title)
              .then(() => message.success("章节标题已复制"))
              .catch(() => message.error("复制失败，请手动复制"));
          }}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") {
              return;
            }
            event.preventDefault();
            event.stopPropagation();
            void navigator.clipboard
              .writeText(title)
              .then(() => message.success("章节标题已复制"))
              .catch(() => message.error("复制失败，请手动复制"));
          }}
        >
          {title}（{getImportanceLevelLabel(node.importance_level)}）
        </span>
      ),
      children: toTreeData(node.children ?? [], path),
    };
  });
}

export default function BlueprintOutlineTreeReadonly({
  nodes,
  selectedPath,
  onSelectNode,
}: BlueprintOutlineTreeReadonlyProps) {
  return (
    <Tree
      defaultExpandAll
      treeData={toTreeData(nodes)}
      selectedKeys={selectedPath ? [selectedPath] : []}
      onSelect={(keys) => onSelectNode?.(keys[0] as string | undefined)}
    />
  );
}
