import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Tag,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ConfidenceBadge from "../../components/WritingTechnique/ConfidenceBadge";
import WritingTechniqueForm from "../../components/WritingTechnique/WritingTechniqueForm";
import { useKBContext } from "../../layout/KBContext";
import {
  bindWritingTechniqueSource,
  deleteWritingTechnique,
  getWritingTechnique,
  publishWritingTechnique,
  updateWritingTechnique,
  type WritingTechniqueItem,
  type WritingTechniquePayload,
} from "../../services/writingTechniques";

const USAGE_MODE_LABEL: Record<string, string> = {
  DIRECT: "直接套用",
  REFERENCE: "参考改写",
  EXTRACT: "要点提炼",
};

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function toPayload(item: WritingTechniqueItem): WritingTechniquePayload {
  return {
    title: item.title ?? "",
    applicable_scene: item.applicable_scene ?? null,
    writing_summary: item.writing_summary ?? null,
    applicable_sections: item.applicable_sections ?? [],
    tags: item.tags ?? [],
    usage_mode: item.usage_mode ?? "REFERENCE",
    recommended_outline: item.recommended_outline ?? null,
    writing_strategy: item.writing_strategy ?? null,
    must_include: item.must_include ?? null,
    notes: item.notes ?? null,
    output_requirement: item.output_requirement ?? null,
    checklist: item.checklist ?? null,
    confidence: item.confidence ?? 0,
    source_chunk_id: item.source_chunk_id ?? null,
  };
}

export default function WritingTechniqueDetailPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [bindForm] = Form.useForm<{ chunk_id: number }>();

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [binding, setBinding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [bindModalOpen, setBindModalOpen] = useState(false);
  const [item, setItem] = useState<WritingTechniqueItem>();
  const [draft, setDraft] = useState<WritingTechniquePayload>();

  const loadDetail = useCallback(async () => {
    if (!selectedKbId || !id) {
      setItem(undefined);
      setDraft(undefined);
      return;
    }
    setLoading(true);
    try {
      const result = await getWritingTechnique(selectedKbId, id);
      setItem(result);
      setDraft(toPayload(result));
      setEditing(false);
    } catch (error) {
      message.error((error as Error).message);
      setItem(undefined);
      setDraft(undefined);
    } finally {
      setLoading(false);
    }
  }, [id, selectedKbId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleSave = useCallback(async () => {
    if (!selectedKbId || !id || !draft) {
      return;
    }
    const title = draft.title?.trim();
    if (!title) {
      message.warning("请输入技巧标题");
      return;
    }
    setSaving(true);
    try {
      await updateWritingTechnique(selectedKbId, id, {
        ...draft,
        title,
      });
      message.success("撰写技巧已更新");
      await loadDetail();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  }, [draft, id, loadDetail, selectedKbId]);

  const handlePublish = useCallback(async () => {
    if (!selectedKbId || !id) {
      return;
    }
    setPublishing(true);
    try {
      await publishWritingTechnique(selectedKbId, id);
      message.success("撰写技巧已发布");
      await loadDetail();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setPublishing(false);
    }
  }, [id, loadDetail, selectedKbId]);

  const handleDelete = useCallback(async () => {
    if (!selectedKbId || !id) {
      return;
    }
    setDeleting(true);
    try {
      await deleteWritingTechnique(selectedKbId, id);
      message.success("撰写技巧已删除");
      navigate("/knowledge/writing-techniques");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setDeleting(false);
    }
  }, [id, navigate, selectedKbId]);

  const handleBindSource = useCallback(async () => {
    if (!selectedKbId || !id) {
      return;
    }
    let values: { chunk_id: number };
    try {
      values = await bindForm.validateFields();
    } catch {
      return;
    }
    setBinding(true);
    try {
      await bindWritingTechniqueSource(selectedKbId, id, { chunk_id: values.chunk_id });
      message.success("来源绑定成功");
      setBindModalOpen(false);
      bindForm.resetFields();
      await loadDetail();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setBinding(false);
    }
  }, [bindForm, id, loadDetail, selectedKbId]);

  const statusTag = useMemo(() => {
    if (!item) return null;
    return <Tag color={item.status === "published" ? "green" : "default"}>{item.status}</Tag>;
  }, [item]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  if (!id) {
    return <Alert message="缺少技巧 ID" type="error" showIcon />;
  }

  if (loading) {
    return (
      <Card>
        <Spin />
      </Card>
    );
  }

  if (!item || !draft) {
    return (
      <Card>
        <Empty description="未找到撰写技巧" />
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {item.source_invalid ? (
        <Alert
          type="warning"
          showIcon
          message="当前来源知识已失效"
          description="建议重新绑定来源 Chunk，避免技巧内容与知识库上下文不一致。"
        />
      ) : null}

      <Card
        title={`撰写技巧：${item.title || "-"}`}
        extra={
          <Space>
            <Button onClick={() => navigate("/knowledge/writing-techniques")}>返回列表</Button>
            <Button onClick={() => setBindModalOpen(true)} disabled={readOnly}>
              绑定来源
            </Button>
            <Button
              type="primary"
              onClick={() => void handlePublish()}
              loading={publishing}
              disabled={readOnly || item.status === "published"}
            >
              发布
            </Button>
            {editing ? (
              <Button onClick={() => setEditing(false)} disabled={saving}>
                退出编辑
              </Button>
            ) : (
              <Button onClick={() => setEditing(true)} disabled={readOnly}>
                编辑
              </Button>
            )}
            <Popconfirm
              title="确认删除该撰写技巧吗？"
              okText="删除"
              cancelText="取消"
              onConfirm={handleDelete}
              disabled={readOnly}
            >
              <Button danger loading={deleting} disabled={readOnly}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        }
      >
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="技巧 ID">{item.technique_id}</Descriptions.Item>
          <Descriptions.Item label="状态">{statusTag}</Descriptions.Item>
          <Descriptions.Item label="使用方式">{USAGE_MODE_LABEL[item.usage_mode] ?? item.usage_mode}</Descriptions.Item>
          <Descriptions.Item label="置信度">
            <ConfidenceBadge confidence={item.confidence} />
          </Descriptions.Item>
          <Descriptions.Item label="来源 Chunk ID">{item.source_chunk_id ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="来源失效">{item.source_invalid ? "是" : "否"}</Descriptions.Item>
          <Descriptions.Item label="版本">{item.version}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{formatDateTime(item.updated_at)}</Descriptions.Item>
        </Descriptions>
      </Card>

      <WritingTechniqueForm
        value={draft}
        loading={saving}
        readOnly={readOnly || !editing}
        showSave={editing}
        onChange={setDraft}
        onSave={() => void handleSave()}
      />

      <Modal
        title="绑定来源 Chunk"
        open={bindModalOpen}
        onOk={() => void handleBindSource()}
        okText="绑定"
        cancelText="取消"
        okButtonProps={{ loading: binding, disabled: readOnly }}
        onCancel={() => {
          setBindModalOpen(false);
          bindForm.resetFields();
        }}
      >
        <Form form={bindForm} layout="vertical" initialValues={{ chunk_id: item.source_chunk_id ?? undefined }}>
          <Form.Item name="chunk_id" label="Chunk ID" rules={[{ required: true, message: "请输入 Chunk ID" }]}>
            <InputNumber min={1} precision={0} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
