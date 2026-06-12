import { Button, Input, message, Space, Switch, Table } from "antd";
import { useMemo, useState } from "react";
import {
  createTemplateMaterial,
  type TemplateMaterialItem,
  updateTemplateMaterial,
} from "../../services/templates";

type MaterialPanelProps = {
  kbId: string;
  templateId: string;
  items: TemplateMaterialItem[];
  onReload: () => Promise<void>;
};

export default function MaterialPanel({ kbId, templateId, items, onReload }: MaterialPanelProps) {
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  const columns = useMemo(
    () => [
      { title: "标题", dataIndex: "title", key: "title" },
      { title: "类型", dataIndex: "material_type", key: "material_type" },
      { title: "状态", dataIndex: "status", key: "status" },
      {
        title: "候选提取",
        dataIndex: "extract_as_candidate",
        key: "extract_as_candidate",
        render: (value: boolean, record: TemplateMaterialItem) => (
          <Switch
            size="small"
            checked={value}
            onChange={async (checked) => {
              await updateTemplateMaterial(kbId, templateId, record.material_id, {
                extract_as_candidate: checked,
              });
              await onReload();
            }}
          />
        ),
      },
      {
        title: "操作",
        key: "actions",
        render: (_: unknown, record: TemplateMaterialItem) => (
          <Button
            danger
            type="link"
            onClick={async () => {
              await updateTemplateMaterial(kbId, templateId, record.material_id, { status: "deprecated" });
              await onReload();
            }}
          >
            废弃
          </Button>
        ),
      },
    ],
    [kbId, onReload, templateId],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Space>
        <Input
          style={{ width: 260 }}
          value={newTitle}
          placeholder="新增素材标题"
          onChange={(event) => setNewTitle(event.target.value)}
        />
        <Button
          type="primary"
          loading={creating}
          onClick={async () => {
            if (!newTitle.trim()) {
              message.warning("请输入素材标题");
              return;
            }
            setCreating(true);
            try {
              await createTemplateMaterial(kbId, templateId, {
                material_type: "fixed_paragraph",
                title: newTitle.trim(),
                extract_as_candidate: false,
              });
              setNewTitle("");
              await onReload();
            } finally {
              setCreating(false);
            }
          }}
        >
          新增素材
        </Button>
      </Space>
      <Table rowKey="material_id" size="small" pagination={false} columns={columns} dataSource={items} />
    </Space>
  );
}
