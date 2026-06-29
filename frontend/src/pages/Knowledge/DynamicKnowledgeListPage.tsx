import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BOOLEAN_OPTIONS, getEnumLabel, getEnumOptions, getFieldLabel } from "../../constants/knowledgeChunkMeta";
import { useKnowledgeTaxonomy } from "../../hooks/useKnowledgeTaxonomy";
import { useKBContext } from "../../layout/KBContext";
import {
  createDynamicKnowledge,
  deleteDynamicKnowledge,
  listDynamicKnowledge,
  type DynamicKnowledgePayload,
  type DynamicKnowledgeRecord,
  type ListDynamicKnowledgeParams,
} from "../../services/dynamicKnowledge";

interface FilterFormValues {
  dynamic_type_code?: string;
  status?: string;
  business_line_codes?: string[];
  expired_only?: "true" | "false";
}

function toListParams(values: FilterFormValues): ListDynamicKnowledgeParams {
  return {
    dynamic_type_code: values.dynamic_type_code,
    status: values.status,
    business_line_codes: values.business_line_codes?.length ? values.business_line_codes : undefined,
    expired_only: values.expired_only === undefined ? undefined : values.expired_only === "true",
  };
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function DynamicKnowledgeListPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [form] = Form.useForm<FilterFormValues>();
  const [createForm] = Form.useForm<DynamicKnowledgePayload>();
  const navigate = useNavigate();

  const [filters, setFilters] = useState<ListDynamicKnowledgeParams>({});
  const [items, setItems] = useState<DynamicKnowledgeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<number>();
  const [createOpen, setCreateOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const { items: dynamicTypeItems } = useKnowledgeTaxonomy("dynamic_type");
  const { items: businessLineItems } = useKnowledgeTaxonomy("business_line");

  const dynamicTypeOptions = useMemo(
    () => dynamicTypeItems.map((item) => ({ value: item.code, label: item.label })),
    [dynamicTypeItems],
  );
  const businessLineOptions = useMemo(
    () => businessLineItems.map((item) => ({ value: item.code, label: item.label })),
    [businessLineItems],
  );

  const refreshList = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listDynamicKnowledge(selectedKbId, {
        ...filters,
        page,
        page_size: pageSize,
      });
      setItems(result.items ?? []);
      setTotal(result.total ?? 0);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, selectedKbId]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  const applyFilters = useCallback(() => {
    const values = form.getFieldsValue();
    setFilters(toListParams(values));
    setPage(1);
  }, [form]);

  const resetFilters = useCallback(() => {
    form.resetFields();
    setFilters({});
    setPage(1);
  }, [form]);

  const handleCreate = useCallback(async () => {
    if (!selectedKbId) return;
    let values: DynamicKnowledgePayload;
    try {
      values = await createForm.validateFields();
    } catch {
      return;
    }
    setCreating(true);
    try {
      const created = await createDynamicKnowledge(selectedKbId, {
        ...values,
        content: values.content ?? "",
        source_type: values.source_type ?? "extracted",
        business_line_codes: values.business_line_codes?.length ? values.business_line_codes : ["general"],
      });
      message.success("动态知识已创建");
      setCreateOpen(false);
      createForm.resetFields();
      navigate(`/knowledge/dynamic-knowledge/${created.id}`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setCreating(false);
    }
  }, [createForm, navigate, selectedKbId]);

  const handleDelete = useCallback(
    async (recordId: number) => {
      if (!selectedKbId) return;
      setDeletingId(recordId);
      try {
        await deleteDynamicKnowledge(selectedKbId, recordId);
        message.success("动态知识已删除");
        await refreshList();
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setDeletingId(undefined);
      }
    },
    [refreshList, selectedKbId],
  );

  const columns: ColumnsType<DynamicKnowledgeRecord> = useMemo(
    () => [
      {
        title: getFieldLabel("title"),
        dataIndex: "title",
        key: "title",
        width: 260,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => navigate(`/knowledge/dynamic-knowledge/${record.id}`)}
          >
            {record.title || "-"}
          </Button>
        ),
      },
      {
        title: getFieldLabel("dynamic_type_label"),
        dataIndex: "dynamic_type_label",
        key: "dynamic_type_label",
        width: 160,
      },
      {
        title: getFieldLabel("business_line_labels"),
        dataIndex: "business_line_labels",
        key: "business_line_labels",
        width: 180,
        render: (values: string[]) => (values?.length ? values.join(" / ") : "-"),
      },
      {
        title: getFieldLabel("status"),
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value: string, record) => (
          <Space size={4}>
            <Tag>{getEnumLabel("status", value)}</Tag>
            {record.is_expired ? <Tag color="red">已过期</Tag> : null}
          </Space>
        ),
      },
      {
        title: getFieldLabel("sync_status"),
        dataIndex: "sync_status",
        key: "sync_status",
        width: 120,
        render: (value: string) => <Tag>{getEnumLabel("sync_status", value)}</Tag>,
      },
      {
        title: getFieldLabel("update_time"),
        dataIndex: "update_time",
        key: "update_time",
        width: 170,
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 90,
        render: (_value, record) => (
          <Popconfirm
            title="确认删除该动态知识吗？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => void handleDelete(record.id)}
            disabled={readOnly}
          >
            <Button danger size="small" loading={deletingId === record.id} disabled={readOnly}>
              删除
            </Button>
          </Popconfirm>
        ),
      },
    ],
    [deletingId, handleDelete, navigate, readOnly],
  );

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card
        title="动态知识"
        extra={
          <Button type="primary" disabled={readOnly} onClick={() => setCreateOpen(true)}>
            新建动态知识
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Space style={{ width: "100%" }} align="end" wrap>
            <Form.Item
              name="dynamic_type_code"
              label={getFieldLabel("dynamic_type_label")}
              style={{ minWidth: 220, marginBottom: 12 }}
            >
              <Select allowClear options={dynamicTypeOptions} />
            </Form.Item>
            <Form.Item
              name="business_line_codes"
              label={getFieldLabel("business_line_labels")}
              style={{ minWidth: 260, marginBottom: 12 }}
            >
              <Select mode="multiple" allowClear options={businessLineOptions} />
            </Form.Item>
            <Form.Item name="status" label={getFieldLabel("status")} style={{ minWidth: 140, marginBottom: 12 }}>
              <Select allowClear options={getEnumOptions("status")} />
            </Form.Item>
            <Form.Item name="expired_only" label={getFieldLabel("is_expired")} style={{ minWidth: 120, marginBottom: 12 }}>
              <Select allowClear options={[...BOOLEAN_OPTIONS]} />
            </Form.Item>
            <Space style={{ marginBottom: 12 }}>
              <Button type="primary" onClick={applyFilters}>
                查询
              </Button>
              <Button onClick={resetFilters}>重置</Button>
            </Space>
          </Space>
        </Form>

        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (count) => `共 ${count} 条`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>

      <Modal
        title="新建动态知识"
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => {
          setCreateOpen(false);
          createForm.resetFields();
        }}
        okText="创建"
        cancelText="取消"
        okButtonProps={{ loading: creating, disabled: readOnly }}
      >
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{
            source_type: "extracted",
            status: "draft",
            sync_status: "pending",
            business_line_codes: ["general"],
          }}
        >
          <Form.Item
            name="dynamic_type_code"
            label={getFieldLabel("dynamic_type_label")}
            rules={[{ required: true, message: "请选择动态知识类型" }]}
          >
            <Select options={dynamicTypeOptions} />
          </Form.Item>
          <Form.Item name="title" label={getFieldLabel("title")} rules={[{ required: true, message: "请输入标题" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="business_line_codes" label={getFieldLabel("business_line_labels")}>
            <Select mode="multiple" options={businessLineOptions} />
          </Form.Item>
          <Form.Item name="content" label={getFieldLabel("content")}>
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
