import {
  Alert,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Spin,
  Steps,
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
  getActualBidParseTask,
  listActualBidCandidates,
  type ActualBidParseTaskDetail,
  type CandidateListItem,
} from "../../services/actualBidParse";
import { getNodes, type BidOutlineNode } from "../../services/bidOutlines";
import { getProductCategoryTree } from "../../services/productCategoryApi";

const OUTLINE_WARNING_LABELS: Record<string, string> = {
  embedded_document_detected: "内嵌附件",
  high_l1_ratio: "L1占比偏高",
  flat_fallback: "扁平回退",
  empty_outline: "空目录",
  high_review_ratio: "待复核偏多",
};

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
  const [outlineNodes, setOutlineNodes] = useState<BidOutlineNode[]>([]);
  const [documentNodeCount, setDocumentNodeCount] = useState(0);
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
      if (!task.bid_outline_id) {
        message.error("目录尚未生成，请稍后在文件导入中心查看解析进度");
        return;
      }

      const [document, outlineResult, candidates] = await Promise.all([
        getActualBidDocument(selectedKbId, task.document_id),
        getNodes(selectedKbId, task.bid_outline_id),
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
      setDocumentNodeCount(task.suggestion?.node_count ?? 0);
      setOutlineNodes(
        (outlineResult.nodes ?? []).map((node) => ({
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

  const updateOutlineNode = (outlineNodeId: string, patch: Partial<BidOutlineNode>) => {
    setOutlineNodes((prev) =>
      prev.map((item) => (item.outline_node_id === outlineNodeId ? { ...item, ...patch } : item)),
    );
  };

  const parentOptions = useMemo(
    () =>
      outlineNodes.map((item) => ({
        label: item.title || "未命名章节",
        value: item.outline_node_id,
      })),
    [outlineNodes],
  );

  const treeColumns: ColumnsType<BidOutlineNode> = [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      width: 320,
      fixed: "left",
      ellipsis: true,
      render: (value: string, record) => (
        <Input
          value={value ?? ""}
          style={{ minWidth: 280 }}
          onChange={(event) => updateOutlineNode(record.outline_node_id, { title: event.target.value })}
        />
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
          onChange={(next) => updateOutlineNode(record.outline_node_id, { level: Number(next ?? 1) })}
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
          options={parentOptions.filter((item) => item.value !== record.outline_node_id)}
          onChange={(next) => updateOutlineNode(record.outline_node_id, { parent_id: (next as string) ?? null })}
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
            updateOutlineNode(record.outline_node_id, { chapter_taxonomy_id: (next as string) ?? null })
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
          onChange={(next) => updateOutlineNode(record.outline_node_id, { product_category_ids: next })}
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
        outline_nodes: outlineNodes.map((node) => ({
          outline_node_id: node.outline_node_id,
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
      styles={{ body: { display: "flex", flexDirection: "column", gap: 16 } }}
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
            {taskDetail?.outline_quality?.warnings?.includes("embedded_document_detected") ? (
              <Alert
                type="info"
                showIcon
                message="检测到内嵌附件文档"
                description={
                  <Space direction="vertical" size={4}>
                    <span>
                      正文内嵌入了完整附件（如应急预案手册），已自动跳过约{" "}
                      {taskDetail.outline_quality?.embedded_heading_count ?? 0} 条附件内标题，主目录在附件结束后恢复衔接。
                    </span>
                    {(taskDetail.outline_quality?.embedded_regions_sample ?? []).map((region, index) => (
                      <span key={`${region.trigger_title}-${index}`}>
                        附件 {index + 1}：自「{region.trigger_title}」起，至「{region.resume_title || "—"}」恢复主目录（跳过{" "}
                        {region.skipped_heading_count} 条）
                      </span>
                    ))}
                  </Space>
                }
                style={{ marginBottom: 12 }}
              />
            ) : null}
            {taskDetail?.outline_quality?.warnings?.length ? (
              <Alert
                type="warning"
                showIcon
                message="目录质量提示"
                description={`策略 ${taskDetail.outline_quality.extract_strategy}；L1 占比 ${Math.round(
                  taskDetail.outline_quality.l1_ratio * 100,
                )}%${
                  taskDetail.outline_quality.warnings.length
                    ? `；提示：${taskDetail.outline_quality.warnings
                        .filter((w) => w !== "embedded_document_detected")
                        .map((w) => OUTLINE_WARNING_LABELS[w] ?? w)
                        .join("、")}`
                    : ""
                }`}
                style={{ marginBottom: 12 }}
              />
            ) : null}
            {(taskDetail?.filtered_total ?? 0) > 0 ? (
              <Collapse
                style={{ marginBottom: 12 }}
                items={[
                  {
                    key: "filtered",
                    label: `已自动过滤 ${taskDetail?.filtered_total} 条非章节内容（只读）`,
                    children: (
                      <Table
                        size="small"
                        pagination={false}
                        dataSource={taskDetail?.filtered_nodes_sample ?? []}
                        columns={[
                          { title: "标题", dataIndex: "title", ellipsis: true },
                          { title: "原因", dataIndex: "reason_code", width: 140 },
                          { title: "层级", dataIndex: "level", width: 60 },
                        ]}
                        rowKey={(row, index) => `${row.title}-${index}`}
                      />
                    ),
                  },
                ]}
              />
            ) : null}
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
              已从文档抽取 {outlineNodes.length} 条目录
              {documentNodeCount > 0 ? `（文档共 ${documentNodeCount} 个内容块）` : ""}
              ，可编辑标题、层级、父子关系与章节分类。
            </Typography.Text>
            <Table
              rowKey="outline_node_id"
              scroll={{ x: 1400 }}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["20", "50", "100"] }}
              columns={treeColumns}
              dataSource={outlineNodes}
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
