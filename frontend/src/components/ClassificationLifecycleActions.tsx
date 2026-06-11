import { Button, Popconfirm, Space } from "antd";

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
        title="确认停用该分类？"
        onConfirm={onDeactivate}
        disabled={disabled || status !== "active"}
      >
        <Button danger disabled={disabled || status !== "active"}>
          停用
        </Button>
      </Popconfirm>
      <Popconfirm
        title="确认归档该分类？"
        onConfirm={onArchive}
        disabled={disabled || status === "archived"}
      >
        <Button disabled={disabled || status === "archived"}>
          归档
        </Button>
      </Popconfirm>
    </Space>
  );
}
