import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Typography,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  confirmCandidate,
  getCandidate,
  patchCandidate,
  retryPublishCandidate,
  type CandidateDetail,
  type CandidatePatchPayload,
  type ConfirmAs,
  type ConfirmRequest,
} from "../../services/candidates";

interface EditFormValues {
  title: string;
  summary?: string;
  content?: string;
}

interface PublishFormValues {
  confirm_as: ConfirmAs;
  knowledge_type?: string;
  wiki_type?: string;
  product_category_ids_text?: string;
  chapter_taxonomy_id?: string;
  searchable?: boolean;
  review_comment?: string;
  template_id?: string;
  parent_chapter_id?: string;
  asset_type?: string;
  category_code?: string;
}

const CONFIRM_AS_OPTIONS: Array<{ value: ConfirmAs; label: string }> = [
  { value: "ku", label: "知识单元 (KU)" },
  { value: "wiki", label: "Wiki" },
  { value: "template_chapter", label: "模板章节" },
  { value: "manual_asset", label: "手册资产" },
  { value: "chapter_pattern", label: "章节模式" },
  { value: "product_category", label: "产品分类" },
  { value: "ignore", label: "忽略" },
];

function parseCommaIds(value?: string): string[] | undefined {
  if (!value) {
    return undefined;
  }
  const ids = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return ids.length > 0 ? ids : undefined;
}

function renderSourceTrace(trace?: CandidateDetail["source_trace"]) {
  if (!trace || Object.keys(trace).length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无来源追溯信息" />;
  }
  const entries = Object.entries(trace).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );
  return (
    <Descriptions column={1} size="small" bordered>
      {entries.map(([key, value]) => (
        <Descriptions.Item key={key} label={key}>
          {String(value)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

export default function CandidateConfirmPage() {
  const navigate = useNavigate();
  const { candidateId } = useParams<{ candidateId: string }>();
  const { selectedKbId } = useKBContext();
  const [editForm] = Form.useForm<EditFormValues>();
  const [publishForm] = Form.useForm<PublishFormValues>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [candidate, setCandidate] = useState<CandidateDetail>();
  const [publishError, setPublishError] = useState<string>();
  const [lastPayload, setLastPayload] = useState<ConfirmRequest>();

  const loadCandidate = useCallback(async () => {
    if (!selectedKbId || !candidateId) {
      return;
    }
    setLoading(true);
    try {
      const detail = await getCandidate(selectedKbId, candidateId);
      setCandidate(detail);
      setPublishError(undefined);
      setLastPayload(undefined);
    } catch (error) {
      message.error((error as Error).message);
      setCandidate(undefined);
    } finally {
      setLoading(false);
    }
  }, [candidateId, selectedKbId]);

  useEffect(() => {
    void loadCandidate();
  }, [loadCandidate]);

  useEffect(() => {
    if (!candidate) {
      return;
    }
    editForm.setFieldsValue({
      title: candidate.title,
      summary: candidate.summary,
      content: candidate.content,
    });
    publishForm.setFieldsValue({
      confirm_as: "ku",
      searchable: true,
    });
  }, [candidate, editForm, publishForm]);

  const confirmAs = Form.useWatch("confirm_as", publishForm) ?? "ku";

  const handleSave = useCallback(async () => {
    if (!selectedKbId || !candidateId || !candidate) {
      return;
    }
    const values = await editForm.validateFields();
    const payload: CandidatePatchPayload = {};
    if (values.title !== candidate.title) {
      payload.title = values.title;
    }
    if (values.summary !== candidate.summary) {
      payload.summary = values.summary;
    }
    if (values.content !== candidate.content) {
      payload.content = values.content;
    }
    if (Object.keys(payload).length === 0) {
      message.info("没有需要保存的修改");
      return;
    }

    setSaving(true);
    try {
      await patchCandidate(selectedKbId, candidateId, payload);
      setCandidate((prev) =>
        prev
          ? {
              ...prev,
              title: values.title,
              summary: values.summary,
              content: values.content,
            }
          : prev,
      );
      message.success("保存成功");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  }, [candidate, candidateId, editForm, selectedKbId]);

  const buildConfirmPayload = useCallback(
    (values: PublishFormValues): ConfirmRequest => {
      const draft = editForm.getFieldsValue();
      const payload: ConfirmRequest = {
        confirm_as: values.confirm_as,
        title: draft.title,
        summary: draft.summary,
        content: draft.content,
        review_comment: values.review_comment,
      };

      if (values.confirm_as === "ku") {
        payload.knowledge_type = values.knowledge_type ?? null;
        payload.product_category_ids = parseCommaIds(values.product_category_ids_text);
        payload.chapter_taxonomy_id = values.chapter_taxonomy_id ?? null;
        payload.searchable = Boolean(values.searchable);
      } else if (values.confirm_as === "wiki") {
        payload.wiki_type = values.wiki_type ?? null;
        payload.product_category_ids = parseCommaIds(values.product_category_ids_text);
        payload.chapter_taxonomy_id = values.chapter_taxonomy_id ?? null;
        payload.searchable = Boolean(values.searchable);
      } else if (values.confirm_as === "template_chapter") {
        payload.template_id = values.template_id ?? null;
        payload.parent_chapter_id = values.parent_chapter_id ?? null;
        payload.chapter_taxonomy_id = values.chapter_taxonomy_id ?? null;
      } else if (values.confirm_as === "manual_asset") {
        payload.asset_type = values.asset_type ?? null;
      } else if (values.confirm_as === "product_category") {
        payload.category_code = values.category_code ?? null;
      }

      return payload;
    },
    [editForm],
  );

  const submitPublish = useCallback(
    async (isRetry: boolean) => {
      if (!selectedKbId || !candidateId) {
        return;
      }

      let payload = lastPayload;
      if (!isRetry || !payload) {
        const values = await publishForm.validateFields();
        payload = buildConfirmPayload(values);
      }

      setPublishing(true);
      setPublishError(undefined);
      setLastPayload(payload);
      try {
        if (isRetry) {
          await retryPublishCandidate(selectedKbId, candidateId, payload);
        } else {
          await confirmCandidate(selectedKbId, candidateId, payload);
        }
        message.success("发布成功");
        navigate("/candidates");
      } catch (error) {
        const text = (error as Error).message;
        setPublishError(text);
        message.error(text);
      } finally {
        setPublishing(false);
      }
    },
    [buildConfirmPayload, candidateId, lastPayload, navigate, publishForm, selectedKbId],
  );

  const publishFields = useMemo(() => {
    if (confirmAs === "ku") {
      return (
        <>
          <Form.Item
            name="knowledge_type"
            label="knowledge_type"
            rules={[{ required: true, message: "请输入 knowledge_type" }]}
          >
            <Input placeholder="例如：solution" />
          </Form.Item>
          <Form.Item name="product_category_ids_text" label="product_category_ids">
            <Input placeholder="多个 UUID 用英文逗号分隔，可留空" />
          </Form.Item>
          <Form.Item
            name="chapter_taxonomy_id"
            label="chapter_taxonomy_id"
            rules={[{ required: true, message: "请输入 chapter_taxonomy_id" }]}
          >
            <Input placeholder="章节类型 UUID" />
          </Form.Item>
          <Form.Item name="searchable" label="searchable" valuePropName="checked">
            <Switch />
          </Form.Item>
        </>
      );
    }
    if (confirmAs === "wiki") {
      return (
        <>
          <Form.Item name="wiki_type" label="wiki_type">
            <Input placeholder="可选，例如：faq" />
          </Form.Item>
          <Form.Item name="product_category_ids_text" label="product_category_ids">
            <Input placeholder="多个 UUID 用英文逗号分隔，可留空" />
          </Form.Item>
          <Form.Item
            name="chapter_taxonomy_id"
            label="chapter_taxonomy_id"
            rules={[{ required: true, message: "请输入 chapter_taxonomy_id" }]}
          >
            <Input placeholder="章节类型 UUID" />
          </Form.Item>
          <Form.Item name="searchable" label="searchable" valuePropName="checked">
            <Switch />
          </Form.Item>
        </>
      );
    }
    if (confirmAs === "template_chapter") {
      return (
        <>
          <Form.Item
            name="template_id"
            label="template_id"
            rules={[{ required: true, message: "请输入 template_id" }]}
          >
            <Input placeholder="模板 UUID" />
          </Form.Item>
          <Form.Item name="parent_chapter_id" label="parent_chapter_id">
            <Input placeholder="可选，父章节 UUID" />
          </Form.Item>
          <Form.Item
            name="chapter_taxonomy_id"
            label="chapter_taxonomy_id"
            rules={[{ required: true, message: "请输入 chapter_taxonomy_id" }]}
          >
            <Input placeholder="章节类型 UUID" />
          </Form.Item>
        </>
      );
    }
    if (confirmAs === "manual_asset") {
      return (
        <Form.Item
          name="asset_type"
          label="asset_type"
          rules={[{ required: true, message: "请输入 asset_type" }]}
        >
          <Input placeholder="例如：document" />
        </Form.Item>
      );
    }
    if (confirmAs === "product_category") {
      return (
        <Form.Item name="category_code" label="category_code">
          <Input placeholder="可选，分类编码" />
        </Form.Item>
      );
    }
    return null;
  }, [confirmAs]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }
  if (!candidateId) {
    return <Alert message="缺少 candidateId" type="error" showIcon />;
  }
  if (loading) {
    return (
      <div style={{ minHeight: 360, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Spin />
      </div>
    );
  }
  if (!candidate) {
    return <Alert message="候选详情加载失败" type="error" showIcon />;
  }

  return (
    <Row gutter={16} style={{ width: "100%", minHeight: "calc(100vh - 220px)" }}>
      <Col xs={24} lg={11}>
        <Card title="来源追溯" style={{ marginBottom: 16 }}>
          {renderSourceTrace(candidate.source_trace)}
        </Card>
        <Card title="内容预览">
          {candidate.content ? (
            <Typography.Paragraph
              style={{ whiteSpace: "pre-wrap", maxHeight: 520, overflow: "auto", marginBottom: 0 }}
            >
              {candidate.content}
            </Typography.Paragraph>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容预览" />
          )}
        </Card>
      </Col>

      <Col xs={24} lg={13}>
        <Card>
          <Tabs
            items={[
              {
                key: "edit",
                label: "编辑",
                children: (
                  <Form form={editForm} layout="vertical">
                    <Form.Item name="title" label="标题" rules={[{ required: true, message: "请输入标题" }]}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="summary" label="摘要">
                      <Input.TextArea rows={3} />
                    </Form.Item>
                    <Form.Item name="content" label="内容">
                      <Input.TextArea rows={12} />
                    </Form.Item>
                    <Button type="primary" loading={saving} onClick={() => void handleSave()}>
                      保存
                    </Button>
                  </Form>
                ),
              },
              {
                key: "publish",
                label: "发布",
                children: (
                  <>
                    {publishError ? (
                      <Alert
                        type="error"
                        showIcon
                        message="发布失败"
                        description={publishError}
                        action={
                          <Button size="small" loading={publishing} onClick={() => void submitPublish(true)}>
                            重试
                          </Button>
                        }
                        style={{ marginBottom: 16 }}
                      />
                    ) : null}
                    <Form form={publishForm} layout="vertical" initialValues={{ confirm_as: "ku", searchable: true }}>
                      <Form.Item
                        name="confirm_as"
                        label="confirm_as"
                        rules={[{ required: true, message: "请选择确认类型" }]}
                      >
                        <Select options={CONFIRM_AS_OPTIONS} />
                      </Form.Item>
                      {publishFields}
                      <Form.Item name="review_comment" label="review_comment">
                        <Input.TextArea rows={3} placeholder="可选，记录审核备注" />
                      </Form.Item>
                      <Space>
                        <Button type="primary" loading={publishing} onClick={() => void submitPublish(false)}>
                          确认发布
                        </Button>
                        <Button onClick={() => navigate("/candidates")}>返回列表</Button>
                      </Space>
                    </Form>
                  </>
                ),
              },
            ]}
          />
        </Card>
      </Col>
    </Row>
  );
}
