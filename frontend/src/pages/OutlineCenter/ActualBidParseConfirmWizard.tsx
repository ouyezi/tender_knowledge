import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Spin,
  Steps,
  Switch,
  Table,
  Tag,
  TreeSelect,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import { getChapterTaxonomyTree, type ChapterTaxonomyNode } from "../../services/chapterTaxonomyApi";
import {
  confirmActualBidParseTask,
  getActualBidDocument,
  getActualBidDocumentTree,
  getActualBidParseTask,
  listActualBidCandidates,
  type ActualBidParseTaskDetail,
  type CandidateListItem,
  type DocumentTreeNode,
} from "../../services/actualBidParse";
import { getProductCategoryTree } from "../../services/productCategoryApi";

type ProductCategoryOption = { label: string; value: string };

function mapChapterTaxonomyTree(nodes: ChapterTaxonomyNode[]): Array<Record<string, unknown>> {
  return nodes.map((node) => ({
    title: node.standard_name,
    value: node.taxonomy_id,
    key: node.taxonomy_id,
    children: mapChapterTaxonomyTree(node.children),
  }));
}

function flattenCategoryTree(
  nodes: Array<{ category_id: string; category_name: string; children?: any[] }>,
): ProductCategoryOption[] {
  const result: ProductCategoryOption[] = [];
  const visit = (items: Array<{ category_id: string; category_name: string; children?: any[] }>) => {
    for (const item of items) {
      result.push({ label: item.category_name, value: item.category_id });
      if (item.children?.length) {
        visit(item.children);
      }
    }
  };
  visit(nodes);
  return result;
}

export default function ActualBidParseConfirmWizard() {
  const { parseTaskId } = useParams<{ parseTaskId: string }>();
  const { selectedKbId } = useKBContext();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [taskDetail, setTaskDetail] = useState<ActualBidParseTaskDetail | null>(null);
  const [documentTreeNodes, setDocumentTreeNodes] = useState<DocumentTreeNode[]>([]);
  const [candidateRows, setCandidateRows] = useState<CandidateListItem[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<ProductCategoryOption[]>([]);
  const [taxonomyNodes, setTaxonomyNodes] = useState<ChapterTaxonomyNode[]>([]);

  const taxonomyTreeData = useMemo(() => mapChapterTaxonomyTree(taxonomyNodes), [taxonomyNodes]);

  const loadData = useCallback(async () => {
    if (!selectedKbId || !parseTaskId) {
      return;
    }
    setLoading(true);
    try {
      const [task, categoryTree, chapterTaxonomies] = await Promise.all([
        getActualBidParseTask(selectedKbId, parseTaskId),
        getProductCategoryTree(selectedKbId),
        getChapterTaxonomyTree(selectedKbId),
      ]);
      setTaskDetail(task);
      setCategoryOptions(flattenCategoryTree(categoryTree ?? []));
      setTaxonomyNodes(chapterTaxonomies ?? []);
      if (!task.document_id) {
        message.error("任务缺少 document_id，无法进入确认向导");
        return;
      }

      const [document, tree, candidates] = await Promise.all([
        getActualBidDocument(selectedKbId, task.document_id),
        getActualBidDocumentTree(selectedKbId, task.document_id),
        listActualBidCandidates(selectedKbId, {
          page_size: 200,
          import_id: task.import_id,
          source_doc_id: task.document_id,
        }),
      ]);

      form.setFieldsValue({
        bid_project_name: document.bid_project_name ?? "",
        bid_customer_name: document.bid_customer_name ?? "",
        product_category_ids: document.product_category_ids ?? [],
      });
      setDocumentTreeNodes(
        (tree.nodes ?? []).map((node) => ({
          ...node,
          product_category_ids: node.product_category_ids ?? [],
        })),
      );
      setCandidateRows(candidates.items ?? []);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [form, parseTaskId, selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const updateTreeNode = (nodeId: string, patch: Partial<DocumentTreeNode>) => {
    setDocumentTreeNodes((prev) =>
      prev.map((item) => (item.node_id === nodeId ? { ...item, ...patch } : item)),
    );
  };

  const parentOptions = useMemo(
    () => documentTreeNodes.map((item) => ({ label: item.title, value: item.node_id })),
    [documentTreeNodes],
  );

  const treeColumns: ColumnsType<DocumentTreeNode> = [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      render: (value: string, record) => (
        <Input value={value} onChange={(event) => updateTreeNode(record.node_id, { title: event.target.value })} />
      ),
    },
    {
      title: "层级",
      dataIndex: "level",
      key: "level",
      width: 110,
      render: (value: number, record) => (
        <InputNumber
          min={1}
          max={9}
          value={value}
          onChange={(next) => updateTreeNode(record.node_id, { level: Number(next ?? 1) })}
        />
      ),
    },
    {
      title: "父节点",
      dataIndex: "parent_id",
      key: "parent_id",
      width: 220,
      render: (value: string | null, record) => (
        <Select
          allowClear
          style={{ width: 200 }}
          value={value ?? undefined}
          options={parentOptions.filter((item) => item.value !== record.node_id)}
          onChange={(next) => updateTreeNode(record.node_id, { parent_id: (next as string) ?? null })}
        />
      ),
    },
    {
      title: "章节类型",
      dataIndex: "chapter_taxonomy_id",
      key: "chapter_taxonomy_id",
      width: 220,
      render: (value: string | null, record) => (
        <TreeSelect
          allowClear
          style={{ width: 200 }}
          treeData={taxonomyTreeData}
          value={value ?? undefined}
          onChange={(next) =>
            updateTreeNode(record.node_id, { chapter_taxonomy_id: (next as string) ?? null })
          }
        />
      ),
    },
    {
      title: "产品分类",
      dataIndex: "product_category_ids",
      key: "product_category_ids",
      width: 220,
      render: (value: string[], record) => (
        <Select
          mode="multiple"
          allowClear
          style={{ width: 200 }}
          options={categoryOptions}
          value={value ?? []}
          onChange={(next) => updateTreeNode(record.node_id, { product_category_ids: next })}
        />
      ),
    },
    {
      title: "纳入目录",
      dataIndex: "is_outline_node",
      key: "is_outline_node",
      width: 120,
      render: (value: boolean, record) => (
        <Switch
          size="small"
          checked={Boolean(value)}
          onChange={(next) => updateTreeNode(record.node_id, { is_outline_node: next })}
        />
      ),
    },
    {
      title: "人工复核",
      dataIndex: "needs_manual_review",
      key: "needs_manual_review",
      width: 100,
      render: (value: boolean) => (value ? <Tag color="warning">是</Tag> : "否"),
    },
  ];

  const candidateColumns: ColumnsType<CandidateListItem> = [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      render: (value: string | undefined, record) => value || record.summary || "未命名候选",
    },
    {
      title: "类型",
      dataIndex: "candidate_type",
      key: "candidate_type",
      width: 120,
      render: (value: string | undefined) => value || "—",
    },
    {
      title: "建议知识类型",
      dataIndex: "suggested_knowledge_type",
      key: "suggested_knowledge_type",
      width: 150,
      render: (value: string | null | undefined) => value || "—",
    },
    {
      title: "来源",
      key: "source",
      render: (_, record) => record.source_trace?.node_title || record.source_trace?.document_name || "—",
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string | undefined) => value || "pending",
    },
  ];

  const handleConfirm = async () => {
    if (!selectedKbId || !parseTaskId) {
      return;
    }
    try {
      await form.validateFields();
    } catch {
      return;
    }
    const values = form.getFieldsValue();
    setSubmitting(true);
    try {
      const result = await confirmActualBidParseTask(selectedKbId, parseTaskId, {
        document: {
          bid_project_name: values.bid_project_name ?? "",
          bid_customer_name: values.bid_customer_name ?? "",
          product_category_ids: values.product_category_ids ?? [],
        },
        outline_nodes: documentTreeNodes.map((node) => ({
          outline_node_id: node.node_id,
          node_id: node.node_id,
          parent_id: node.parent_id ?? null,
          title: node.title,
          level: node.level,
          sort_order: node.sort_order,
          chapter_taxonomy_id: node.chapter_taxonomy_id ?? null,
          product_category_ids: node.product_category_ids ?? [],
          needs_manual_review: node.needs_manual_review,
        })),
      });
      message.success("确认成功，已保存目录与分类");
      const targetOutlineId = result.bid_outline_id || taskDetail?.bid_outline_id;
      if (targetOutlineId) {
        navigate(`/outlines/${targetOutlineId}`);
      } else {
        navigate("/outlines");
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }
  if (!parseTaskId) {
    return <Alert message="缺少 parseTaskId" type="error" showIcon />;
  }

  return (
    <Card
      title="实际标书解析确认向导"
      extra={
        <Space>
          <Tag color={taskDetail?.status === "ready" ? "warning" : "default"}>{taskDetail?.status || "-"}</Tag>
          <Button onClick={() => navigate("/outlines")}>返回目录中心</Button>
        </Space>
      }
      style={{ minHeight: "calc(100vh - 120px)" }}
      bodyStyle={{ display: "flex", flexDirection: "column", gap: 16 }}
    >
      <Steps
        current={currentStep}
        items={[{ title: "项目信息" }, { title: "目录编辑" }, { title: "候选预览" }]}
      />
      <Spin spinning={loading || submitting}>
        <Form form={form} layout="vertical">
          {currentStep === 0 ? (
            <>
              <Form.Item name="bid_project_name" label="项目名称">
                <Input placeholder="请输入项目名称" />
              </Form.Item>
              <Form.Item name="bid_customer_name" label="客户名称">
                <Input placeholder="请输入客户名称" />
              </Form.Item>
              <Form.Item name="product_category_ids" label="产品分类">
                <Select mode="multiple" allowClear options={categoryOptions} />
              </Form.Item>
            </>
          ) : null}
        </Form>

        {currentStep === 1 ? (
          <>
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
              可编辑目录标题、层级、父子关系与章节分类，提交时将统一保存。
            </Typography.Text>
            <Table
              rowKey="node_id"
              pagination={false}
              columns={treeColumns}
              dataSource={documentTreeNodes}
              locale={{ emptyText: "暂无目录节点" }}
            />
          </>
        ) : null}

        {currentStep === 2 ? (
          <Table
            rowKey="candidate_id"
            pagination={false}
            columns={candidateColumns}
            dataSource={candidateRows}
            locale={{ emptyText: "暂无候选数据" }}
          />
        ) : null}
      </Spin>
      <Space>
        <Button disabled={currentStep === 0} onClick={() => setCurrentStep((step) => Math.max(step - 1, 0))}>
          上一步
        </Button>
        {currentStep < 2 ? (
          <Button type="primary" onClick={() => setCurrentStep((step) => Math.min(step + 1, 2))}>
            下一步
          </Button>
        ) : (
          <Button type="primary" loading={submitting} onClick={() => void handleConfirm()}>
            确认并进入目录
          </Button>
        )}
      </Space>
    </Card>
  );
}
