import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Tree,
  Typography,
  message,
} from "antd";
import type { DataNode } from "antd/es/tree";
import { useCallback, useEffect, useMemo, useState } from "react";
import KnowledgeContentViewer from "../../components/Knowledge/KnowledgeContentViewer";
import ResizableWorkspace from "../../components/Knowledge/ResizableWorkspace";
import { getEnumOptions, getFieldLabel } from "../../constants/knowledgeChunkMeta";
import { useKBContext } from "../../layout/KBContext";
import { ApiError } from "../../services/apiClient";
import {
  createKnowledgeChunk,
  getDocumentTree,
  getNodePreview,
  listEntryDocuments,
  prefillKnowledgeChunk,
  type CatalogPathItem,
  type CreateKnowledgeChunkRequest,
  type EntryDocument,
  type NodePreview,
  type PrefillResult,
  type TreeNode,
} from "../../services/knowledgeChunks";

const { Text } = Typography;

interface EntryFormValues {
  title: string;
  content: string;
  summary?: string;
  knowledge_type?: string;
  content_type?: string;
  source_type?: string;
  file_name?: string;
  project_name?: string;
  page_start?: number;
  page_end?: number;
  char_start?: number;
  char_end?: number;
  parent_id?: number;
  quote_mode?: string;
  category?: string;
  tags?: string[];
  products?: string[];
  industries?: string[];
  customer_types?: string[];
  regions?: string[];
  issue_date?: string;
  expire_date?: string;
  status?: string;
  template_type?: string;
  retrieval_weight?: number;
  security_level?: string;
  owner?: string;
  review_status?: string;
  edit_distance_avg?: number;
  catalog_path_json?: string;
  variables_json?: string;
  exclusion_rules_json?: string;
  need_parent_context?: boolean;
  is_template?: boolean;
  is_immutable?: boolean;
  winning_flag?: boolean;
}

function toTreeData(nodes: TreeNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.node_id,
    title: (
      <Space size={8}>
        <span>{node.title || "(未命名节点)"}</span>
        {node.ingested ? <Tag color="green">已入库</Tag> : null}
      </Space>
    ),
    children: toTreeData(node.children ?? []),
  }));
}

function markNodeIngested(nodes: TreeNode[], nodeId: string): TreeNode[] {
  return nodes.map((node) => {
    const current = node.node_id === nodeId ? { ...node, ingested: true } : node;
    if (!current.children?.length) {
      return current;
    }
    return { ...current, children: markNodeIngested(current.children, nodeId) };
  });
}

function parseJsonArray<T>(raw?: string): T[] | undefined {
  if (!raw?.trim()) {
    return undefined;
  }
  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("JSON 必须是数组");
  }
  return parsed as T[];
}

export default function KnowledgeEntryPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [form] = Form.useForm<EntryFormValues>();
  const [documents, setDocuments] = useState<EntryDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>();
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [preview, setPreview] = useState<NodePreview>();
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [rightExpanded, setRightExpanded] = useState(false);
  const [prefilling, setPrefilling] = useState(false);
  const [creating, setCreating] = useState(false);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.doc_id === selectedDocId),
    [documents, selectedDocId],
  );

  const loadDocuments = useCallback(async () => {
    if (!selectedKbId) {
      setDocuments([]);
      setSelectedDocId(undefined);
      return;
    }
    setLoadingDocuments(true);
    try {
      const result = await listEntryDocuments(selectedKbId);
      setDocuments(result.items ?? []);
      const nextDocId = result.items?.[0]?.doc_id;
      setSelectedDocId((prev) => prev ?? nextDocId);
    } catch (error) {
      message.error((error as Error).message);
      setDocuments([]);
      setSelectedDocId(undefined);
    } finally {
      setLoadingDocuments(false);
    }
  }, [selectedKbId]);

  const loadTree = useCallback(async () => {
    if (!selectedKbId || !selectedDocId) {
      setTreeNodes([]);
      setSelectedNodeId(undefined);
      setPreview(undefined);
      return;
    }
    setLoadingTree(true);
    try {
      const result = await getDocumentTree(selectedKbId, selectedDocId);
      setTreeNodes(result.items ?? []);
      setSelectedNodeId(undefined);
      setPreview(undefined);
      setRightExpanded(false);
      form.resetFields();
    } catch (error) {
      message.error((error as Error).message);
      setTreeNodes([]);
      setSelectedNodeId(undefined);
      setPreview(undefined);
    } finally {
      setLoadingTree(false);
    }
  }, [form, selectedDocId, selectedKbId]);

  const loadPreview = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId) {
      setPreview(undefined);
      return;
    }
    setLoadingPreview(true);
    try {
      const result = await getNodePreview(selectedKbId, selectedDocId, selectedNodeId);
      setPreview(result);
      setRightExpanded(false);
      form.resetFields();
    } catch (error) {
      message.error((error as Error).message);
      setPreview(undefined);
    } finally {
      setLoadingPreview(false);
    }
  }, [form, selectedDocId, selectedKbId, selectedNodeId]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview]);

  const applyPrefillToForm = useCallback(
    (result: PrefillResult) => {
      form.setFieldsValue({
        title: result.title || preview?.title || "",
        content: preview?.content_md || "",
        summary: result.summary ?? undefined,
        knowledge_type: result.knowledge_type,
        content_type: result.content_type || preview?.content_type,
        source_type: result.source_type,
        file_name: result.file_name || selectedDocument?.document_name,
        project_name: result.project_name,
        page_start: preview?.page_start ?? undefined,
        page_end: preview?.page_end ?? undefined,
        char_start: preview?.char_start ?? undefined,
        char_end: preview?.char_end ?? undefined,
        quote_mode: result.quote_mode,
        category: result.category,
        tags: result.tags ?? [],
        products: result.products ?? [],
        industries: result.industries ?? [],
        customer_types: result.customer_types ?? [],
        regions: result.regions ?? [],
        issue_date: result.issue_date ?? undefined,
        expire_date: result.expire_date ?? undefined,
        status: result.status,
        template_type: result.template_type ?? undefined,
        retrieval_weight: 1,
        security_level: result.security_level,
        review_status: result.review_status,
        owner: undefined,
        catalog_path_json: JSON.stringify(preview?.catalog_path ?? [], null, 2),
        variables_json: "[]",
        exclusion_rules_json: "[]",
        need_parent_context: false,
        is_template: result.is_template ?? false,
        is_immutable: false,
        winning_flag: result.winning_flag ?? false,
      });
    },
    [form, preview, selectedDocument?.document_name],
  );

  const handlePrefill = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId || !preview) {
      message.warning("请先选择文档节点并加载预览");
      return;
    }
    setRightExpanded(true);
    setPrefilling(true);
    try {
      const result = await prefillKnowledgeChunk(selectedKbId, {
        doc_id: selectedDocId,
        primary_node_id: selectedNodeId,
        content: preview.content_md,
        metadata: {
          source_type: selectedDocument?.source_type ?? "bid",
          file_name: selectedDocument?.document_name,
        },
      });
      applyPrefillToForm(result);
      if (result.warnings?.length) {
        message.warning(`预填完成，但有提示：${result.warnings.join(", ")}`);
      } else {
        message.success("AI 预填完成");
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setPrefilling(false);
    }
  }, [
    applyPrefillToForm,
    preview,
    selectedDocId,
    selectedDocument?.document_name,
    selectedKbId,
    selectedNodeId,
  ]);

  const buildCreatePayload = useCallback(
    (values: EntryFormValues): CreateKnowledgeChunkRequest => {
      if (!selectedDocId || !selectedNodeId || !preview) {
        throw new Error("节点预览未准备完成");
      }
      const catalogPath =
        parseJsonArray<CatalogPathItem>(values.catalog_path_json) ?? (preview.catalog_path as CatalogPathItem[]);
      const variables = parseJsonArray<Record<string, unknown>>(values.variables_json);
      const exclusionRules = parseJsonArray<Record<string, unknown>>(values.exclusion_rules_json);

      return {
        doc_id: selectedDocId,
        primary_node_id: selectedNodeId,
        title: values.title,
        content: preview.content_md,
        summary: values.summary || null,
        knowledge_type: values.knowledge_type,
        content_type: values.content_type,
        source_type: values.source_type,
        file_name: values.file_name || null,
        project_name: values.project_name || null,
        page_start: values.page_start ?? null,
        page_end: values.page_end ?? null,
        char_start: values.char_start ?? null,
        char_end: values.char_end ?? null,
        catalog_path: catalogPath,
        parent_id: values.parent_id ?? null,
        need_parent_context: Boolean(values.need_parent_context),
        quote_mode: values.quote_mode,
        category: values.category,
        tags: values.tags ?? [],
        products: values.products ?? [],
        industries: values.industries ?? [],
        customer_types: values.customer_types ?? [],
        regions: values.regions ?? [],
        issue_date: values.issue_date || null,
        expire_date: values.expire_date || null,
        status: values.status,
        is_template: Boolean(values.is_template),
        template_type: values.template_type ?? null,
        variables,
        is_immutable: Boolean(values.is_immutable),
        exclusion_rules: exclusionRules,
        retrieval_weight: values.retrieval_weight ?? 1,
        security_level: values.security_level,
        owner: values.owner || null,
        review_status: values.review_status,
        winning_flag: Boolean(values.winning_flag),
        edit_distance_avg: values.edit_distance_avg ?? null,
      };
    },
    [preview, selectedDocId, selectedNodeId],
  );

  const submitCreate = useCallback(
    async (force = false) => {
      if (!selectedKbId) return;
      const values = await form.validateFields();
      const payload = buildCreatePayload(values);
      setCreating(true);
      try {
        await createKnowledgeChunk(selectedKbId, payload, force);
        message.success("已添加到知识库");
        if (selectedNodeId) {
          setTreeNodes((prev) => markNodeIngested(prev, selectedNodeId));
        }
      } finally {
        setCreating(false);
      }
    },
    [buildCreatePayload, form, selectedKbId, selectedNodeId],
  );

  const handleCreate = useCallback(async () => {
    try {
      await submitCreate(false);
    } catch (error) {
      if (error instanceof ApiError && error.code === "CHUNK_EXISTS") {
        Modal.confirm({
          title: "检测到已存在最新版本",
          content: "是否覆盖创建新版本？",
          okText: "覆盖创建",
          cancelText: "取消",
          onOk: async () => {
            try {
              await submitCreate(true);
            } catch (retryError) {
              message.error((retryError as Error).message);
            }
          },
        });
        return;
      }
      message.error((error as Error).message);
    }
  }, [submitCreate]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span>来源文档：</span>
        <Select
          style={{ width: 420, maxWidth: "100%", flex: 1 }}
          loading={loadingDocuments}
          placeholder="请选择文档"
          value={selectedDocId}
          options={documents.map((doc) => ({
            label: doc.source_type === "template" ? `${doc.document_name}（模板）` : doc.document_name,
            value: doc.doc_id,
          }))}
          onChange={(value) => setSelectedDocId(value)}
        />
      </div>

      <ResizableWorkspace
        treePanel={
          <Card title="目录树" bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
            {loadingTree ? (
              <Spin />
            ) : (
              <Tree
                treeData={toTreeData(treeNodes)}
                selectedKeys={selectedNodeId ? [selectedNodeId] : []}
                onSelect={(keys) => setSelectedNodeId(keys[0] as string | undefined)}
              />
            )}
          </Card>
        }
        previewPanel={
          <Card
            title="章节预览"
            extra={
              <Button disabled={!preview || readOnly} onClick={() => void handlePrefill()}>
                添加到知识库
              </Button>
            }
            bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}
          >
            {loadingPreview ? <Spin /> : null}
            {!loadingPreview && !preview ? <Text type="secondary">请选择目录节点查看内容</Text> : null}
            {preview ? (
              <KnowledgeContentViewer
                contentMd={preview.content_md}
                assets={preview.assets}
                sectionCharStart={preview.char_start}
                kbId={selectedKbId}
                imageRefMap={preview.image_ref_map}
              />
            ) : null}
          </Card>
        }
        entryPanel={
          <Card title="知识录入" bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
            {!rightExpanded ? (
              <Space direction="vertical">
                <Text type="secondary">点击“添加到知识库”后，右侧将展开预填表单。</Text>
              </Space>
            ) : null}
            {rightExpanded && prefilling ? (
              <div style={{ minHeight: 180, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Space direction="vertical" align="center">
                  <Spin />
                  <Text>AI 预填中...</Text>
                </Space>
              </div>
            ) : null}
            {rightExpanded && !prefilling ? (
              <Form<EntryFormValues> form={form} layout="vertical" initialValues={{ content: preview?.content_md }}>
                <Form.Item
                  name="title"
                  label={getFieldLabel("title")}
                  rules={[{ required: true, message: "请输入标题" }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item name="content" label={`${getFieldLabel("content")}（只读）`}>
                  <Input.TextArea rows={6} readOnly />
                </Form.Item>
                <Form.Item name="summary" label={getFieldLabel("summary")}>
                  <Input.TextArea rows={3} />
                </Form.Item>
                <Form.Item name="knowledge_type" label={getFieldLabel("knowledge_type")}>
                  <Select allowClear options={getEnumOptions("knowledge_type")} />
                </Form.Item>
                <Form.Item name="content_type" label={getFieldLabel("content_type")}>
                  <Select allowClear options={getEnumOptions("content_type")} />
                </Form.Item>
                <Form.Item name="source_type" label={getFieldLabel("source_type")}>
                  <Select allowClear options={getEnumOptions("source_type")} />
                </Form.Item>
                <Form.Item name="file_name" label={getFieldLabel("file_name")}>
                  <Input />
                </Form.Item>
                <Form.Item name="project_name" label={getFieldLabel("project_name")}>
                  <Input />
                </Form.Item>
                <Form.Item name="category" label={getFieldLabel("category")}>
                  <Select allowClear options={getEnumOptions("category")} />
                </Form.Item>
                <Form.Item name="status" label={getFieldLabel("status")}>
                  <Select allowClear options={getEnumOptions("status")} />
                </Form.Item>
                <Form.Item name="quote_mode" label={getFieldLabel("quote_mode")}>
                  <Select allowClear options={getEnumOptions("quote_mode")} />
                </Form.Item>
                <Form.Item name="template_type" label={getFieldLabel("template_type")}>
                  <Select allowClear options={getEnumOptions("template_type")} />
                </Form.Item>
                <Form.Item name="security_level" label={getFieldLabel("security_level")}>
                  <Select allowClear options={getEnumOptions("security_level")} />
                </Form.Item>
                <Form.Item name="review_status" label={getFieldLabel("review_status")}>
                  <Select allowClear options={getEnumOptions("review_status")} />
                </Form.Item>
                <Form.Item name="owner" label={getFieldLabel("owner")}>
                  <Input />
                </Form.Item>
                <Form.Item name="issue_date" label={getFieldLabel("issue_date")}>
                  <Input placeholder="YYYY-MM-DD" />
                </Form.Item>
                <Form.Item name="expire_date" label={getFieldLabel("expire_date")}>
                  <Input placeholder="YYYY-MM-DD" />
                </Form.Item>
                <Form.Item name="tags" label={getFieldLabel("tags")}>
                  <Select mode="tags" />
                </Form.Item>
                <Form.Item name="products" label={getFieldLabel("products")}>
                  <Select mode="tags" />
                </Form.Item>
                <Form.Item name="industries" label={getFieldLabel("industries")}>
                  <Select mode="tags" />
                </Form.Item>
                <Form.Item name="customer_types" label={getFieldLabel("customer_types")}>
                  <Select mode="tags" />
                </Form.Item>
                <Form.Item name="regions" label={getFieldLabel("regions")}>
                  <Select mode="tags" />
                </Form.Item>
                <Form.Item name="page_start" label={getFieldLabel("page_start")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="page_end" label={getFieldLabel("page_end")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="char_start" label={getFieldLabel("char_start")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="char_end" label={getFieldLabel("char_end")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="parent_id" label={getFieldLabel("parent_id")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="retrieval_weight" label={getFieldLabel("retrieval_weight")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="edit_distance_avg" label={getFieldLabel("edit_distance_avg")}>
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="catalog_path_json" label={`${getFieldLabel("catalog_path")}(JSON 数组)`}>
                  <Input.TextArea rows={4} />
                </Form.Item>
                <Form.Item name="variables_json" label={`${getFieldLabel("variables")}(JSON 数组)`}>
                  <Input.TextArea rows={4} />
                </Form.Item>
                <Form.Item name="exclusion_rules_json" label={`${getFieldLabel("exclusion_rules")}(JSON 数组)`}>
                  <Input.TextArea rows={4} />
                </Form.Item>
                <Form.Item
                  name="need_parent_context"
                  label={getFieldLabel("need_parent_context")}
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
                <Form.Item name="is_template" label={getFieldLabel("is_template")} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item name="is_immutable" label={getFieldLabel("is_immutable")} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item name="winning_flag" label={getFieldLabel("winning_flag")} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Button type="primary" disabled={readOnly} loading={creating} onClick={() => void handleCreate()}>
                  确认添加
                </Button>
              </Form>
            ) : null}
          </Card>
        }
      />
    </Space>
  );
}
