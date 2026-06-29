import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tag,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getEnumLabel, getEnumOptions, getFieldLabel } from "../../constants/knowledgeChunkMeta";
import { useKnowledgeTaxonomy } from "../../hooks/useKnowledgeTaxonomy";
import { useKBContext } from "../../layout/KBContext";
import {
  deleteDynamicKnowledge,
  getDynamicKnowledge,
  updateDynamicKnowledge,
  type DynamicKnowledgePayload,
  type DynamicKnowledgeRecord,
} from "../../services/dynamicKnowledge";

interface DetailFormValues extends DynamicKnowledgePayload {
  structured_data_json?: string;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function toFormValues(record: DynamicKnowledgeRecord): DetailFormValues {
  return {
    dynamic_type_code: record.dynamic_type_code,
    title: record.title,
    content: record.content,
    business_line_codes: record.business_line_codes,
    source_type: record.source_type,
    source_doc_id: record.source_doc_id,
    source_chunk_id: record.source_chunk_id,
    issue_date: record.issue_date,
    expire_date: record.expire_date,
    status: record.status,
    sync_status: record.sync_status,
    structured_data_json: JSON.stringify(record.structured_data ?? {}, null, 2),
  };
}

export default function DynamicKnowledgeDetailPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [form] = Form.useForm<DetailFormValues>();

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [record, setRecord] = useState<DynamicKnowledgeRecord>();
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

  const loadDetail = useCallback(async () => {
    if (!selectedKbId || !id) {
      setRecord(undefined);
      return;
    }
    setLoading(true);
    try {
      const detail = await getDynamicKnowledge(selectedKbId, Number(id));
      setRecord(detail);
      form.setFieldsValue(toFormValues(detail));
    } catch (error) {
      message.error((error as Error).message);
      setRecord(undefined);
    } finally {
      setLoading(false);
    }
  }, [form, id, selectedKbId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleSave = useCallback(async () => {
    if (!selectedKbId || !id) return;
    let values: DetailFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    let structuredData: Record<string, unknown> | undefined;
    try {
      structuredData = values.structured_data_json?.trim()
        ? (JSON.parse(values.structured_data_json) as Record<string, unknown>)
        : {};
    } catch {
      message.warning("structured_data 需为合法 JSON 对象");
      return;
    }
    setSaving(true);
    try {
      await updateDynamicKnowledge(selectedKbId, Number(id), {
        dynamic_type_code: values.dynamic_type_code,
        title: values.title?.trim(),
        content: values.content ?? "",
        business_line_codes: values.business_line_codes ?? [],
        source_type: values.source_type,
        source_doc_id: values.source_doc_id ?? null,
        source_chunk_id: values.source_chunk_id ?? null,
        issue_date: values.issue_date ?? null,
        expire_date: values.expire_date ?? null,
        status: values.status,
        sync_status: values.sync_status,
        structured_data: structuredData,
      });
      message.success("动态知识已更新");
      await loadDetail();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  }, [form, id, loadDetail, selectedKbId]);

  const handleDelete = useCallback(async () => {
    if (!selectedKbId || !id) return;
    setDeleting(true);
    try {
      await deleteDynamicKnowledge(selectedKbId, Number(id));
      message.success("动态知识已删除");
      navigate("/knowledge/dynamic-knowledge");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setDeleting(false);
    }
  }, [id, navigate, selectedKbId]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }
  if (!id) {
    return <Alert message="缺少动态知识 ID" type="error" showIcon />;
  }
  if (loading) {
    return (
      <Card>
        <Spin />
      </Card>
    );
  }
  if (!record) {
    return (
      <Card>
        <Empty description="未找到动态知识" />
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {record.is_expired ? (
        <Alert
          type="warning"
          showIcon
          message="该动态知识已过期"
          description="建议尽快核验并更新内容，避免输出过时信息。"
        />
      ) : null}

      <Card
        title={`动态知识：${record.title || "-"}`}
        extra={
          <Space>
            <Button onClick={() => navigate("/knowledge/dynamic-knowledge")}>返回列表</Button>
            <Button type="primary" onClick={() => void handleSave()} loading={saving} disabled={readOnly}>
              保存
            </Button>
            <Popconfirm
              title="确认删除该动态知识吗？"
              okText="删除"
              cancelText="取消"
              onConfirm={() => void handleDelete()}
              disabled={readOnly}
            >
              <Button danger loading={deleting} disabled={readOnly}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        }
      >
        <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
          <Descriptions.Item label={getFieldLabel("id")}>{record.id}</Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("kb_id")}>{record.kb_id}</Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("dynamic_type_label")}>
            {record.dynamic_type_label}
          </Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("status")}>
            <Tag>{getEnumLabel("status", record.status)}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("sync_status")}>
            <Tag>{getEnumLabel("sync_status", record.sync_status)}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("is_expired")}>{record.is_expired ? "是" : "否"}</Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("create_time")}>{formatDateTime(record.create_time)}</Descriptions.Item>
          <Descriptions.Item label={getFieldLabel("update_time")}>{formatDateTime(record.update_time)}</Descriptions.Item>
        </Descriptions>

        <Form form={form} layout="vertical">
          <Form.Item
            name="dynamic_type_code"
            label={getFieldLabel("dynamic_type_label")}
            rules={[{ required: true, message: "请选择动态知识类型" }]}
          >
            <Select options={dynamicTypeOptions} disabled={readOnly} />
          </Form.Item>
          <Form.Item name="title" label={getFieldLabel("title")} rules={[{ required: true, message: "请输入标题" }]}>
            <Input disabled={readOnly} />
          </Form.Item>
          <Form.Item name="business_line_codes" label={getFieldLabel("business_line_labels")}>
            <Select mode="multiple" options={businessLineOptions} disabled={readOnly} />
          </Form.Item>
          <Form.Item name="status" label={getFieldLabel("status")}>
            <Select options={getEnumOptions("status")} disabled={readOnly} />
          </Form.Item>
          <Form.Item name="sync_status" label={getFieldLabel("sync_status")}>
            <Select options={getEnumOptions("sync_status")} disabled={readOnly} />
          </Form.Item>
          <Form.Item name="issue_date" label={getFieldLabel("issue_date")}>
            <Input placeholder="YYYY-MM-DD" disabled={readOnly} />
          </Form.Item>
          <Form.Item name="expire_date" label={getFieldLabel("expire_date")}>
            <Input placeholder="YYYY-MM-DD" disabled={readOnly} />
          </Form.Item>
          <Form.Item name="content" label={getFieldLabel("content")}>
            <Input.TextArea rows={8} disabled={readOnly} />
          </Form.Item>
          <Form.Item name="structured_data_json" label={`${getFieldLabel("structured_data")} (JSON)`}>
            <Input.TextArea rows={8} disabled={readOnly} />
          </Form.Item>
        </Form>
      </Card>
    </Space>
  );
}
