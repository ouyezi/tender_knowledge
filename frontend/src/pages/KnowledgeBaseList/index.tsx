import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  createKnowledgeBase,
  deactivateKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBase,
} from "../../services/kbApi";
import { useKBContext } from "../../layout/KBContext";

type ListStatus = "active" | "inactive";

interface CreateFormValues {
  name: string;
  clone_from_kb_id?: string;
}

const STATUS_OPTIONS: Array<{ label: string; value: ListStatus }> = [
  { label: "启用中", value: "active" },
  { label: "已停用", value: "inactive" },
];

export default function KnowledgeBaseListPage() {
  const [form] = Form.useForm<CreateFormValues>();
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [status, setStatus] = useState<ListStatus>("active");
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const { activeKbs, refreshActiveKbs, selectedKbId, setSelectedKbId, readOnly } =
    useKBContext();

  const loadData = async () => {
    setLoading(true);
    try {
      const list = await listKnowledgeBases(status);
      setKbs(list);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [status]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const created = await createKnowledgeBase(values);
      message.success("知识库创建成功");
      setCreateOpen(false);
      form.resetFields();
      await Promise.all([loadData(), refreshActiveKbs()]);
      if (!selectedKbId) {
        setSelectedKbId(created.id);
      }
    } catch (error) {
      if ((error as { errorFields?: unknown[] }).errorFields) {
        return;
      }
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (id: string) => {
    try {
      await deactivateKnowledgeBase(id);
      message.success("知识库已停用");
      await Promise.all([loadData(), refreshActiveKbs()]);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const columns = useMemo<ColumnsType<KnowledgeBase>>(
    () => [
      {
        title: "ID",
        dataIndex: "id",
        key: "id",
      },
      {
        title: "名称",
        dataIndex: "name",
        key: "name",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (value: string) =>
          value === "active" ? <Tag color="green">active</Tag> : <Tag color="default">inactive</Tag>,
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        render: (value?: string) => (value ? new Date(value).toLocaleString() : "-"),
      },
      {
        title: "操作",
        key: "actions",
        render: (_, record) => (
          <Space>
            <Popconfirm
              title="确认停用该知识库吗？"
              onConfirm={() => handleDeactivate(record.id)}
              disabled={readOnly || record.status !== "active"}
            >
              <Button
                danger
                size="small"
                disabled={readOnly || record.status !== "active"}
              >
                停用
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [readOnly],
  );

  return (
    <Card
      title="知识库列表"
      extra={
        <Space>
          <Select<ListStatus>
            value={status}
            options={STATUS_OPTIONS}
            style={{ width: 140 }}
            onChange={setStatus}
          />
          <Button type="primary" onClick={() => setCreateOpen(true)} disabled={readOnly}>
            新建知识库
          </Button>
        </Space>
      }
    >
      <Typography.Paragraph type="secondary">
        可以创建新知识库，也可从已有知识库克隆初始化内容。
      </Typography.Paragraph>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={kbs}
        columns={columns}
        pagination={false}
      />

      <Modal
        title="新建知识库"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        okButtonProps={{ loading: saving, disabled: readOnly }}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            label="知识库名称"
            name="name"
            rules={[{ required: true, message: "请输入知识库名称" }]}
          >
            <Input placeholder="例如：制造业投标知识库" maxLength={64} />
          </Form.Item>
          <Form.Item label="克隆来源（可选）" name="clone_from_kb_id">
            <Select
              allowClear
              placeholder="选择一个知识库作为克隆来源"
              options={activeKbs.map((kb) => ({ label: kb.name, value: kb.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
