import { Button, Popconfirm, Space, Tooltip } from "antd";

interface ClassificationLifecycleActionsProps {
  readOnly?: boolean;
  status?: string;
  onImpact: () => void;
  onMerge: () => void;
  onDeactivate: () => void;
  onArchive: () => void;
}

export default function ClassificationLifecycleActions({
  readOnly = false,
  status,
  onImpact,
  onMerge,
  onDeactivate,
  onArchive,
}: ClassificationLifecycleActionsProps) {
  const isMerged = status === "merged";
  const disabled = readOnly || isMerged || !status;

  return (
    <Space wrap>
      <Button onClick={onImpact} disabled={!status}>
        影响分析
      </Button>
      <Button onClick={onMerge} disabled={disabled}>
        合并
      </Button>
      <Popconfirm
        title="停用后该分类不可被新对象选用，已有引用保留。确认停用？"
        onConfirm={onDeactivate}
        disabled={disabled || status !== "active"}
      >
        <Button danger disabled={disabled || status !== "active"}>
          停用
        </Button>
      </Popconfirm>
      <Popconfirm
        title="归档不会删除数据，仅标记为历史分类，默认列表中隐藏。确认归档？"
        onConfirm={onArchive}
        disabled={disabled || status === "archived"}
      >
        <Tooltip title="归档 ≠ 删除，数据仍保留">
          <span>
            <Button disabled={disabled || status === "archived"}>
              归档
            </Button>
          </span>
        </Tooltip>
      </Popconfirm>
    </Space>
  );
}
