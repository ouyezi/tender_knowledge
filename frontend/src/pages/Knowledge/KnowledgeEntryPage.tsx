import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Tree,
  Typography,
  message,
} from "antd";
import type { DataNode } from "antd/es/tree";
import { useCallback, useEffect, useMemo, useState, type Key } from "react";
import { buildAutoCreatePayload, buildPrefillMetadata, collectIngestibleNodeIds, withRetry } from "./batchIngestUtils";
import { isPrefaceNodeId } from "./prefaceNode";
import BlueprintEditor from "../../components/Blueprint/BlueprintEditor";
import KnowledgeContentViewer from "../../components/Knowledge/KnowledgeContentViewer";
import ResizableWorkspace from "../../components/Knowledge/ResizableWorkspace";
import TaxonomyCascader from "../../components/Knowledge/TaxonomyCascader";
import { getEnumOptions, getFieldLabel } from "../../constants/knowledgeChunkMeta";
import { useKnowledgeTaxonomy } from "../../hooks/useKnowledgeTaxonomy";
import { useKBContext } from "../../layout/KBContext";
import { ApiError } from "../../services/apiClient";
import {
  createBlueprint,
  generateBlueprint,
  getBlueprintBySource,
  updateBlueprint,
  type BlueprintDraft,
} from "../../services/blueprints";
import {
  createKnowledgeChunk,
  getDocumentTree,
  getNodePreview,
  listEntryDocuments,
  prefillKnowledgeChunk,
  refineDocumentTree,
  type CatalogPathItem,
  type CreateKnowledgeChunkRequest,
  type EntryDocument,
  type NodePreview,
  type PrefillResult,
  type TreeNode,
} from "../../services/knowledgeChunks";

const { Text } = Typography;

const WORKSPACE_CARD_STYLE = { height: "100%", display: "flex", flexDirection: "column" } as const;
const WORKSPACE_CARD_BODY_STYLE = { flex: 1, overflow: "auto", minHeight: 0 };

interface EntryFormValues {
  title: string;
  content: string;
  summary?: string;
  knowledge_type?: string;
  content_type?: string;
  file_name?: string;
  block_type_code?: string;
  application_type_code?: string;
  business_line_codes?: string[];
  tags?: string[];
  regions?: string[];
  qualification_info?: string;
  expire_date?: string;
  status?: string;
  template_type?: string;
  security_level?: string;
  owner?: string;
  review_status?: string;
  catalog_path_json?: string;
  is_template?: boolean;
}

type EntryTabKey = "entry" | "blueprint";

type BatchIngestState = {
  active: boolean;
  total: number;
  completed: number;
  currentNodeId?: string;
  cancelRequested: boolean;
  failedItems: Array<{ nodeId: string; title: string; error: string }>;
};

function toTreeData(nodes: TreeNode[], options?: { currentNodeId?: string }): DataNode[] {
  return nodes.map((node) => ({
    key: node.node_id,
    title: (
      <Space size={8}>
        <span
          style={
            options?.currentNodeId === node.node_id ? { fontWeight: 600, color: "#1677ff" } : undefined
          }
        >
          {node.title || "(未命名节点)"}
        </span>
        {node.ingested ? <Tag color="green">已入库</Tag> : null}
        {node.has_blueprint ? <Tag color="blue">已生成蓝图</Tag> : null}
      </Space>
    ),
    children: toTreeData(node.children ?? [], options),
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

function findTreeNodeById(nodes: TreeNode[], nodeId?: string): TreeNode | undefined {
  if (!nodeId) return undefined;
  for (const node of nodes) {
    if (node.node_id === nodeId) {
      return node;
    }
    const child = findTreeNodeById(node.children ?? [], nodeId);
    if (child) {
      return child;
    }
  }
  return undefined;
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
  const [refiningTree, setRefiningTree] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [rightExpanded, setRightExpanded] = useState(false);
  const [prefilling, setPrefilling] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activeTab, setActiveTab] = useState<EntryTabKey>("entry");
  const [blueprintDraft, setBlueprintDraft] = useState<BlueprintDraft>();
  const [blueprintLoading, setBlueprintLoading] = useState(false);
  const [existingBlueprintId, setExistingBlueprintId] = useState<string>();
  const [selectionMode, setSelectionMode] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<Key[]>([]);
  const [batchIngest, setBatchIngest] = useState<BatchIngestState | null>(null);
  const [showProgressBar, setShowProgressBar] = useState(false);
  const blockTypeCodeValue = Form.useWatch("block_type_code", form);
  const { items: applicationTypeItems } = useKnowledgeTaxonomy("application_type");
  const { items: businessLineItems } = useKnowledgeTaxonomy("business_line");

  const batchRunning = Boolean(batchIngest?.active);
  const checkedCount = checkedKeys.length;
  const progressPercent =
    batchIngest && batchIngest.total > 0
      ? Math.round((batchIngest.completed / batchIngest.total) * 100)
      : 0;

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.doc_id === selectedDocId),
    [documents, selectedDocId],
  );
  const selectedTreeNode = useMemo(
    () => findTreeNodeById(treeNodes, selectedNodeId),
    [selectedNodeId, treeNodes],
  );
  const selectedNodeIsLeaf = Boolean(selectedTreeNode && !(selectedTreeNode.children?.length));
  const selectedNodeIsPreface = isPrefaceNodeId(selectedNodeId);
  // entry/documents 仅返回 parse_status=ready 且已有目录树的文档
  const canShowExtractBlueprint = Boolean(selectedDocument);
  const extractBlueprintDisabled = readOnly || blueprintLoading || !selectedNodeId || selectedNodeIsLeaf;
  const showExpireDateHint =
    selectedDocument?.source_type === "qualification" ||
    Boolean(
      blockTypeCodeValue?.startsWith("qualification_") ||
        blockTypeCodeValue?.startsWith("financial_") ||
        blockTypeCodeValue?.startsWith("ip_"),
    );
  const applicationTypeOptions = useMemo(
    () => applicationTypeItems.map((item) => ({ value: item.code, label: item.label })),
    [applicationTypeItems],
  );
  const businessLineOptions = useMemo(
    () => businessLineItems.map((item) => ({ value: item.code, label: item.label })),
    [businessLineItems],
  );
  const emptyBlueprintDraft = useMemo<BlueprintDraft>(
    () => ({
      name: "",
      description: null,
      source_doc_id: selectedDocId ?? "",
      source_node_id: selectedNodeId ?? "",
      source_chapter_title:
        preview?.catalog_path?.[preview.catalog_path.length - 1]?.title ?? selectedTreeNode?.title ?? "",
      nodes: [],
    }),
    [preview?.catalog_path, selectedDocId, selectedNodeId, selectedTreeNode?.title],
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
      const items = result.items ?? [];
      setTreeNodes(items);
      const defaultNodeId = items[0]?.node_id;
      setSelectedNodeId(defaultNodeId);
      setPreview(undefined);
    } catch (error) {
      message.error((error as Error).message);
      setTreeNodes([]);
      setSelectedNodeId(undefined);
      setPreview(undefined);
    } finally {
      setLoadingTree(false);
    }
  }, [selectedDocId, selectedKbId]);

  const loadPreview = useCallback(async (signal?: AbortSignal) => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId) {
      setPreview(undefined);
      return;
    }
    setLoadingPreview(true);
    try {
      const result = await getNodePreview(selectedKbId, selectedDocId, selectedNodeId, { signal });
      setPreview(result);
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        return;
      }
      message.error((error as Error).message);
      setPreview(undefined);
    } finally {
      if (!signal?.aborted) {
        setLoadingPreview(false);
      }
    }
  }, [selectedDocId, selectedKbId, selectedNodeId]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  const handleRefineTree = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || readOnly) {
      return;
    }
    setRefiningTree(true);
    try {
      const result = await refineDocumentTree(selectedKbId, selectedDocId);
      message.success(result.change_summary || "目录已刷新");
      await loadTree();
      if (selectedNodeId) {
        await loadPreview();
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setRefiningTree(false);
    }
  }, [loadPreview, loadTree, readOnly, selectedDocId, selectedKbId, selectedNodeId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadPreview(controller.signal);
    return () => controller.abort();
  }, [loadPreview]);

  useEffect(() => {
    form.resetFields();
    setRightExpanded(false);
    setBlueprintDraft(undefined);
    setExistingBlueprintId(undefined);
    setActiveTab("entry");
  }, [form, selectedDocId, selectedNodeId]);

  const applyPrefillToForm = useCallback(
    (result: PrefillResult) => {
      form.setFieldsValue({
        title: result.title || preview?.title || "",
        content: preview?.content_md || "",
        summary: result.summary ?? undefined,
        knowledge_type: result.knowledge_type,
        content_type: result.content_type || preview?.content_type,
        file_name: result.file_name || selectedDocument?.document_name,
        block_type_code: result.block_type_code,
        application_type_code: result.application_type_code,
        business_line_codes: result.business_line_codes ?? [],
        tags: result.tags ?? [],
        regions: result.regions ?? [],
        qualification_info: result.qualification_info ?? undefined,
        expire_date: result.expire_date ?? undefined,
        status: result.status,
        template_type: result.template_type ?? undefined,
        security_level: result.security_level,
        review_status: result.review_status,
        owner: undefined,
        catalog_path_json: JSON.stringify(preview?.catalog_path ?? [], null, 2),
        is_template: result.is_template ?? false,
      });
    },
    [form, preview, selectedDocument?.document_name],
  );

  const handlePrefill = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId || !preview) {
      message.warning("请先选择文档节点并加载预览");
      return;
    }
    setActiveTab("entry");
    setRightExpanded(true);
    setPrefilling(true);
    try {
      const result = await prefillKnowledgeChunk(selectedKbId, {
        doc_id: selectedDocId,
        primary_node_id: selectedNodeId,
        content: preview.content_md,
        metadata: buildPrefillMetadata({
          preview,
          documentName: selectedDocument?.document_name,
          sourceType: selectedDocument?.source_type,
        }),
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

      return {
        doc_id: selectedDocId,
        primary_node_id: selectedNodeId,
        title: values.title,
        content: preview.content_md,
        summary: values.summary || null,
        knowledge_type: values.knowledge_type,
        content_type: values.content_type,
        file_name: values.file_name || null,
        catalog_path: catalogPath,
        block_type_code: values.block_type_code,
        application_type_code: values.application_type_code,
        business_line_codes: values.business_line_codes ?? [],
        tags: values.tags ?? [],
        regions: values.regions ?? [],
        qualification_info: values.qualification_info?.trim() || null,
        expire_date: values.expire_date || null,
        status: values.status,
        is_template: Boolean(values.is_template),
        template_type: values.template_type ?? null,
        security_level: values.security_level,
        owner: values.owner || null,
        review_status: values.review_status,
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

  const handleExtractBlueprint = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId) {
      message.warning("请先选择目录节点");
      return;
    }
    if (selectedNodeIsLeaf) {
      message.warning("叶子节点不支持提取目录蓝图");
      return;
    }
    setBlueprintLoading(true);
    try {
      const matched = await getBlueprintBySource(selectedKbId, {
        doc_id: selectedDocId,
        node_id: selectedNodeId,
      });
      const hasExisting = Boolean(selectedTreeNode?.has_blueprint || matched);
      if (hasExisting) {
        const confirmed = await new Promise<boolean>((resolve) => {
          Modal.confirm({
            title: "该节点已存在目录蓝图",
            content: "继续提取将覆盖当前草稿，是否继续？",
            okText: "继续提取",
            cancelText: "取消",
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
          });
        });
        if (!confirmed) {
          return;
        }
      }
      const draft = await generateBlueprint(selectedKbId, {
        doc_id: selectedDocId,
        node_id: selectedNodeId,
      });
      setBlueprintDraft(draft);
      setExistingBlueprintId(matched?.blueprint_id);
      setActiveTab("blueprint");
      message.success("目录蓝图提取完成");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setBlueprintLoading(false);
    }
  }, [selectedDocId, selectedKbId, selectedNodeId, selectedNodeIsLeaf, selectedTreeNode?.has_blueprint]);

  const handleSaveBlueprint = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId) {
      message.warning("请先选择目录节点");
      return;
    }
    const draft = blueprintDraft ?? emptyBlueprintDraft;
    const name = draft.name?.trim();
    if (!name) {
      message.warning("请输入蓝图名称");
      return;
    }
    const hasLevelOneNodes = (draft.nodes ?? []).some((node) => node.node_level === 1);
    if (!hasLevelOneNodes) {
      message.warning("请至少保留一个一级目录节点");
      return;
    }
    const payload: BlueprintDraft = {
      ...draft,
      name,
      source_doc_id: selectedDocId,
      source_node_id: selectedNodeId,
      source_chapter_title:
        preview?.catalog_path?.[preview.catalog_path.length - 1]?.title ?? selectedTreeNode?.title ?? "",
    };
    setBlueprintLoading(true);
    try {
      const created = await createBlueprint(selectedKbId, payload);
      setExistingBlueprintId(created.blueprint_id);
      await loadTree();
      message.success("目录蓝图保存成功");
    } catch (error) {
      if (error instanceof ApiError && error.code === "blueprint_source_exists") {
        setBlueprintLoading(false);
        Modal.confirm({
          title: "检测到同源蓝图已存在",
          content: "是否覆盖更新已存在的目录蓝图？",
          okText: "覆盖更新",
          cancelText: "取消",
          onOk: async () => {
            try {
              setBlueprintLoading(true);
              const matched =
                existingBlueprintId
                  ? { blueprint_id: existingBlueprintId }
                  : await getBlueprintBySource(selectedKbId, {
                      doc_id: selectedDocId,
                      node_id: selectedNodeId,
                    });
              if (!matched?.blueprint_id) {
                message.error("未找到可更新的目录蓝图，请刷新后重试");
                return;
              }
              await updateBlueprint(selectedKbId, matched.blueprint_id, payload);
              setExistingBlueprintId(matched.blueprint_id);
              await loadTree();
              message.success("目录蓝图已覆盖更新");
            } catch (updateError) {
              message.error((updateError as Error).message);
            } finally {
              setBlueprintLoading(false);
            }
          },
        });
        return;
      }
      message.error((error as Error).message);
    } finally {
      setBlueprintLoading(false);
    }
  }, [
    blueprintDraft,
    emptyBlueprintDraft,
    existingBlueprintId,
    loadTree,
    preview?.catalog_path,
    selectedDocId,
    selectedKbId,
    selectedNodeId,
    selectedTreeNode?.title,
  ]);

  const handleRegenerateBlueprint = useCallback(() => {
    if (!selectedKbId || !selectedDocId || !selectedNodeId) {
      message.warning("请先选择目录节点");
      return;
    }
    if (selectedNodeIsLeaf) {
      message.warning("叶子节点不支持提取目录蓝图");
      return;
    }
    Modal.confirm({
      title: "确认重新生成目录蓝图？",
      content: "重新生成会覆盖当前草稿内容。",
      okText: "重新生成",
      cancelText: "取消",
      onOk: async () => {
        try {
          setBlueprintLoading(true);
          const draft = await generateBlueprint(selectedKbId, {
            doc_id: selectedDocId,
            node_id: selectedNodeId,
          });
          setBlueprintDraft(draft);
          setActiveTab("blueprint");
          message.success("目录蓝图已重新生成");
        } catch (error) {
          message.error((error as Error).message);
        } finally {
          setBlueprintLoading(false);
        }
      },
    });
  }, [selectedDocId, selectedKbId, selectedNodeId, selectedNodeIsLeaf]);

  const handleBatchIngest = useCallback(async () => {
    if (!selectedKbId || !selectedDocId || readOnly) return;

    const nodeIds = collectIngestibleNodeIds(treeNodes, checkedKeys);
    if (nodeIds.length === 0) {
      message.warning("请先勾选可入库的目录节点（前言不支持入库）");
      return;
    }

    setShowProgressBar(true);
    setBatchIngest({
      active: true,
      total: nodeIds.length,
      completed: 0,
      cancelRequested: false,
      failedItems: [],
    });

    let successCount = 0;
    const failedItems: BatchIngestState["failedItems"] = [];
    let stopped = false;
    let cancelRequested = false;

    for (const nodeId of nodeIds) {
      if (cancelRequested) {
        stopped = true;
        break;
      }

      setBatchIngest((prev) => (prev ? { ...prev, currentNodeId: nodeId } : prev));

      const nodeTitle = findTreeNodeById(treeNodes, nodeId)?.title ?? nodeId;

      try {
        await withRetry(async () => {
          const nodePreview = await getNodePreview(selectedKbId, selectedDocId, nodeId);
          const prefill = await prefillKnowledgeChunk(selectedKbId, {
            doc_id: selectedDocId,
            primary_node_id: nodeId,
            content: nodePreview.content_md,
            metadata: buildPrefillMetadata({
              preview: nodePreview,
              documentName: selectedDocument?.document_name,
              sourceType: selectedDocument?.source_type,
            }),
          });
          const payload = buildAutoCreatePayload({
            docId: selectedDocId,
            nodeId,
            preview: nodePreview,
            prefill,
            documentName: selectedDocument?.document_name,
            sourceType: selectedDocument?.source_type,
          });
          await createKnowledgeChunk(selectedKbId, payload, true);
        });
        successCount += 1;
        setTreeNodes((prev) => markNodeIngested(prev, nodeId));
      } catch (error) {
        failedItems.push({
          nodeId,
          title: nodeTitle,
          error: (error as Error).message,
        });
      }

      setBatchIngest((prev) => {
        if (prev?.cancelRequested) cancelRequested = true;
        return prev
          ? { ...prev, completed: prev.completed + 1, failedItems: [...failedItems] }
          : prev;
      });

      if (cancelRequested) {
        stopped = true;
        break;
      }
    }

    setBatchIngest((prev) => (prev ? { ...prev, active: false, currentNodeId: undefined } : prev));

    if (stopped) {
      const remaining = nodeIds.length - successCount - failedItems.length;
      message.info(`已停止，剩余 ${remaining} 项未处理（成功 ${successCount} 条）`);
    } else if (failedItems.length === 0) {
      message.success(`已成功添加 ${successCount} 条知识`);
    } else {
      message.warning(`成功 ${successCount} 条，失败 ${failedItems.length} 条`);
      Modal.info({
        title: "批量入库失败明细",
        width: 560,
        content: (
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {failedItems.map((item) => (
              <li key={item.nodeId}>
                {item.title}: {item.error}
              </li>
            ))}
          </ul>
        ),
      });
    }

    window.setTimeout(() => setShowProgressBar(false), 2000);
    setSelectionMode(false);
    setCheckedKeys([]);
  }, [checkedKeys, readOnly, selectedDocId, selectedDocument, selectedKbId, treeNodes]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        width: "100%",
        height: readOnly ? "calc(100vh - 200px)" : "calc(100vh - 160px)",
        minHeight: 480,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span>来源文档：</span>
          <Select
            style={{ width: 420, maxWidth: "100%", flex: 1 }}
            loading={loadingDocuments}
            placeholder="请选择文档"
            value={selectedDocId}
            disabled={selectionMode || batchRunning}
            options={documents.map((doc) => ({
              label: doc.source_type === "template" ? `${doc.document_name}（模板）` : doc.document_name,
              value: doc.doc_id,
            }))}
            onChange={(value) => setSelectedDocId(value)}
          />
        </div>
        {showProgressBar && batchIngest ? (
          <div style={{ width: "100%" }}>
            <Progress
              percent={progressPercent}
              format={() => `${batchIngest.completed} / ${batchIngest.total}`}
              status={batchRunning ? "active" : batchIngest.failedItems.length ? "exception" : "success"}
            />
          </div>
        ) : null}
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ResizableWorkspace
          treePanel={
            <Card
              title="目录树"
              style={WORKSPACE_CARD_STYLE}
              styles={{ body: { ...WORKSPACE_CARD_BODY_STYLE, display: "flex", flexDirection: "column", padding: 0 } }}
              extra={
                !readOnly ? (
                  <Space size={8}>
                    <Button
                      size="small"
                      loading={refiningTree}
                      disabled={loadingTree || !selectedDocId || batchRunning || selectionMode}
                      onClick={() => void handleRefineTree()}
                    >
                      刷新
                    </Button>
                    <Button
                      size="small"
                      disabled={loadingTree || treeNodes.length === 0 || batchRunning}
                      onClick={() => {
                        setSelectionMode(true);
                        setCheckedKeys([]);
                      }}
                    >
                      选择
                    </Button>
                  </Space>
                ) : null
              }
            >
              <div style={{ flex: 1, overflow: "auto", padding: "0 24px", minHeight: 0 }}>
                {loadingTree ? (
                  <Spin />
                ) : treeNodes.length === 0 ? (
                  <Text type="secondary">当前文档暂无目录结构</Text>
                ) : (
                  <Tree
                    checkable={selectionMode}
                    checkStrictly={selectionMode}
                    checkedKeys={
                      selectionMode ? { checked: checkedKeys, halfChecked: [] } : checkedKeys
                    }
                    onCheck={(keys) => {
                      const next = Array.isArray(keys) ? keys : keys.checked;
                      setCheckedKeys(next);
                    }}
                    disabled={batchRunning}
                    treeData={toTreeData(treeNodes, { currentNodeId: batchIngest?.currentNodeId })}
                    selectedKeys={selectedNodeId ? [selectedNodeId] : []}
                    onSelect={(keys) => {
                      if (batchRunning) return;
                      setSelectedNodeId(keys[0] as string | undefined);
                    }}
                  />
                )}
              </div>
              {selectionMode ? (
                <div
                  style={{
                    borderTop: "1px solid #f0f0f0",
                    padding: "12px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    flexShrink: 0,
                  }}
                >
                  <Text>已选 {checkedCount} 项</Text>
                  <Button
                    type="primary"
                    size="small"
                    disabled={checkedCount === 0 || batchRunning}
                    onClick={() => void handleBatchIngest()}
                  >
                    添加到知识库
                  </Button>
                  <Button
                    size="small"
                    disabled={batchRunning}
                    onClick={() => {
                      setSelectionMode(false);
                      setCheckedKeys([]);
                    }}
                  >
                    取消选择
                  </Button>
                  {batchRunning ? (
                    <Button
                      size="small"
                      danger
                      onClick={() =>
                        setBatchIngest((prev) => (prev ? { ...prev, cancelRequested: true } : prev))
                      }
                    >
                      停止
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </Card>
          }
          previewPanel={
            <Card
              title="章节预览"
              style={WORKSPACE_CARD_STYLE}
              styles={{ body: WORKSPACE_CARD_BODY_STYLE }}
              extra={
                <Space>
                  {canShowExtractBlueprint ? (
                    <Button
                      disabled={extractBlueprintDisabled}
                      loading={blueprintLoading}
                      onClick={() => {
                        if (readOnly) return;
                        if (!selectedNodeId) {
                          message.warning("请先选择目录节点");
                          return;
                        }
                        if (selectedNodeIsLeaf) {
                          message.warning("当前章节无子结构，无法提取蓝图");
                          return;
                        }
                        void handleExtractBlueprint();
                      }}
                    >
                      提取目录蓝图
                    </Button>
                  ) : null}
                  <Button
                    disabled={!preview || readOnly || selectionMode || batchRunning || selectedNodeIsPreface}
                    onClick={() => void handlePrefill()}
                  >
                    添加到知识库
                  </Button>
                </Space>
              }
            >
              {loadingPreview ? <Spin /> : null}
              {!loadingPreview && !preview ? <Text type="secondary">请选择目录节点查看内容</Text> : null}
              {preview ? (
                <KnowledgeContentViewer
                  contentMd={preview.content_md}
                  assets={preview.assets}
                  sectionCharStart={preview.char_start}
                  sectionCharEnd={preview.char_end}
                  kbId={selectedKbId}
                  imageRefMap={preview.image_ref_map}
                />
              ) : null}
            </Card>
          }
          entryPanel={
            <Card style={WORKSPACE_CARD_STYLE} styles={{ body: WORKSPACE_CARD_BODY_STYLE }}>
              <Tabs
                activeKey={activeTab}
                onChange={(key) => setActiveTab(key as EntryTabKey)}
                items={[
                  {
                    key: "entry",
                    label: "知识录入",
                    children: (
                      <Form<EntryFormValues> form={form} layout="vertical">
                        {!rightExpanded ? (
                          <Space direction="vertical">
                            <Text type="secondary">点击“添加到知识库”后，右侧将展开预填表单。</Text>
                          </Space>
                        ) : null}
                        {rightExpanded && prefilling ? (
                          <div
                            style={{ minHeight: 180, display: "flex", alignItems: "center", justifyContent: "center" }}
                          >
                            <Space direction="vertical" align="center">
                              <Spin />
                              <Text>AI 预填中...</Text>
                            </Space>
                          </div>
                        ) : null}
                        {rightExpanded && !prefilling ? (
                          <>
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
                          <Form.Item name="file_name" label={getFieldLabel("file_name")}>
                            <Input />
                          </Form.Item>
                          <Form.Item name="block_type_code" label={getFieldLabel("block_type_label")}>
                            <TaxonomyCascader />
                          </Form.Item>
                          <Form.Item name="application_type_code" label={getFieldLabel("application_type_label")}>
                            <Select allowClear options={applicationTypeOptions} />
                          </Form.Item>
                          <Form.Item name="business_line_codes" label={getFieldLabel("business_line_labels")}>
                            <Select mode="multiple" allowClear options={businessLineOptions} />
                          </Form.Item>
                          <Form.Item name="status" label={getFieldLabel("status")}>
                            <Select allowClear options={getEnumOptions("status")} />
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
                          {showExpireDateHint ? (
                            <Alert
                              type="info"
                              showIcon
                              message="建议填写资质信息与失效日期"
                              style={{ marginBottom: 16 }}
                            />
                          ) : null}
                          <Form.Item
                            name="qualification_info"
                            label={getFieldLabel("qualification_info")}
                            extra="格式：简称|编号|发证日期|有效期；多条用分号分隔"
                          >
                            <Input.TextArea
                              rows={3}
                              placeholder="ISO9001|A001|2024-01-01|2026-12-31"
                            />
                          </Form.Item>
                          <Form.Item
                            name="expire_date"
                            label={getFieldLabel("expire_date")}
                            extra={showExpireDateHint ? "资质类内容建议填写失效日期，系统将自动提示过期。" : undefined}
                          >
                            <Input type="date" />
                          </Form.Item>
                          <Form.Item name="tags" label={getFieldLabel("tags")}>
                            <Select mode="tags" />
                          </Form.Item>
                          <Form.Item name="regions" label={getFieldLabel("regions")}>
                            <Select mode="tags" />
                          </Form.Item>
                          <Form.Item name="catalog_path_json" label={`${getFieldLabel("catalog_path")}(JSON 数组)`}>
                            <Input.TextArea rows={4} />
                          </Form.Item>
                          <Form.Item name="is_template" label={getFieldLabel("is_template")} valuePropName="checked">
                            <Switch />
                          </Form.Item>
                          <Button
                            type="primary"
                            disabled={readOnly}
                            loading={creating}
                            onClick={() => void handleCreate()}
                          >
                            确认添加
                          </Button>
                          </>
                        ) : null}
                      </Form>
                    ),
                },
                {
                  key: "blueprint",
                  label: "目录蓝图",
                  children: (
                    <BlueprintEditor
                      mode={existingBlueprintId ? "edit" : "draft"}
                      value={blueprintDraft ?? emptyBlueprintDraft}
                      loading={blueprintLoading}
                      readOnly={readOnly}
                      onChange={setBlueprintDraft}
                      onRegenerate={handleRegenerateBlueprint}
                      onSave={() => void handleSaveBlueprint()}
                      sourceInfo={{
                        chapterTitle: preview?.catalog_path?.[preview.catalog_path.length - 1]?.title ?? "",
                        documentName: selectedDocument?.document_name ?? "",
                      }}
                    />
                  ),
                },
              ]}
            />
          </Card>
        }
        />
      </div>
    </div>
  );
}
