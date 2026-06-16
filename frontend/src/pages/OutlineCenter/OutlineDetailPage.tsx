import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  TreeSelect,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import { getChapterTaxonomyTree, type ChapterTaxonomyNode } from "../../services/chapterTaxonomyApi";
import { getProductCategoryTree, type ProductCategoryNode } from "../../services/productCategoryApi";
import {
  batchOps,
  confirmOutline,
  getNodes,
  getOutline,
  patchNode,
  type BatchOperation,
  type BidOutlineDetail,
  type BidOutlineNode,
} from "../../services/bidOutlines";
import OutlineDiffDrawer from "./OutlineDiffDrawer";
import ModuleSuggestionWizard from "./ModuleSuggestionWizard";
import OutlineNodeContentDrawer from "./OutlineNodeContentDrawer";
import OutlineSimilarityDrawer from "./OutlineSimilarityDrawer";
import OutlineTreeEditor, { type OutlineTreeNode } from "./OutlineTreeEditor";

type FlatNode = BidOutlineNode;

function mapProductCategoryTree(nodes: ProductCategoryNode[]): Array<Record<string, unknown>> {
  return nodes.map((node) => ({
    title: node.category_name,
    value: node.category_id,
    key: node.category_id,
    children: mapProductCategoryTree(node.children),
  }));
}

function mapChapterTaxonomyTree(nodes: ChapterTaxonomyNode[]): Array<Record<string, unknown>> {
  return nodes.map((node) => ({
    title: node.standard_name,
    value: node.taxonomy_id,
    key: node.taxonomy_id,
    children: mapChapterTaxonomyTree(node.children),
  }));
}

function buildTree(nodes: FlatNode[]): OutlineTreeNode[] {
  const map = new Map<string, OutlineTreeNode>();
  const roots: OutlineTreeNode[] = [];
  for (const node of nodes) {
    map.set(node.outline_node_id, { ...node, children: [] });
  }
  for (const node of nodes) {
    const current = map.get(node.outline_node_id);
    if (!current) continue;
    if (!node.parent_id) {
      roots.push(current);
      continue;
    }
    const parent = map.get(node.parent_id);
    if (!parent) {
      roots.push(current);
      continue;
    }
    parent.children.push(current);
  }

  const normalize = (items: OutlineTreeNode[], level: number, parentId: string | null) => {
    items
      .sort((a, b) => a.sort_order - b.sort_order)
      .forEach((item, index) => {
        item.level = level;
        item.parent_id = parentId;
        item.sort_order = index;
        normalize(item.children, level + 1, item.outline_node_id);
      });
  };
  normalize(roots, 1, null);
  return roots;
}

function flattenTree(nodes: OutlineTreeNode[]): FlatNode[] {
  const result: FlatNode[] = [];
  const visit = (items: OutlineTreeNode[]) => {
    for (const item of items) {
      const { children, ...rest } = item;
      result.push(rest);
      if (children?.length) {
        visit(children);
      }
    }
  };
  visit(nodes);
  return result;
}

function moveNodeLocally(nodes: FlatNode[], dragId: string, dropId: string, dropToGap: boolean): FlatNode[] {
  if (dragId === dropId) return nodes;

  const byId = new Map(nodes.map((node) => [node.outline_node_id, { ...node }]));
  const drag = byId.get(dragId);
  const target = byId.get(dropId);
  if (!drag || !target) return nodes;

  let cursor: FlatNode | undefined = target;
  while (cursor) {
    if (cursor.outline_node_id === dragId) return nodes;
    cursor = cursor.parent_id ? byId.get(cursor.parent_id) : undefined;
  }

  drag.parent_id = dropToGap ? target.parent_id : target.outline_node_id;
  const regrouped = buildTree(Array.from(byId.values()));
  return flattenTree(regrouped);
}

function buildReorderOps(nodes: FlatNode[]): BatchOperation[] {
  const grouped = new Map<string, FlatNode[]>();
  for (const node of nodes) {
    const key = node.parent_id ?? "__root__";
    const current = grouped.get(key) ?? [];
    current.push(node);
    grouped.set(key, current);
  }
  const ops: BatchOperation[] = [];
  grouped.forEach((items, key) => {
    const ordered = items.sort((a, b) => a.sort_order - b.sort_order).map((item) => item.outline_node_id);
    if (ordered.length === 0) return;
    ops.push({
      op: "reorder",
      parent_id: key === "__root__" ? null : key,
      ordered_node_ids: ordered,
    });
  });
  return ops;
}

export default function OutlineDetailPage() {
  const { bidOutlineId } = useParams<{ bidOutlineId: string }>();
  const { selectedKbId, readOnly } = useKBContext();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [outline, setOutline] = useState<BidOutlineDetail | null>(null);
  const [flatNodes, setFlatNodes] = useState<FlatNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [taxonomyNodes, setTaxonomyNodes] = useState<ChapterTaxonomyNode[]>([]);
  const [categoryNodes, setCategoryNodes] = useState<ProductCategoryNode[]>([]);
  const [diffDrawerOpen, setDiffDrawerOpen] = useState(false);
  const [similarityDrawerOpen, setSimilarityDrawerOpen] = useState(false);
  const [suggestionWizardOpen, setSuggestionWizardOpen] = useState(false);
  const [contentDrawerNodeId, setContentDrawerNodeId] = useState<string | null>(null);

  const treeRoots = useMemo(() => buildTree(flatNodes), [flatNodes]);
  const selectedNode = useMemo(
    () => flatNodes.find((item) => item.outline_node_id === selectedNodeId) ?? null,
    [flatNodes, selectedNodeId],
  );

  const categoryTreeData = useMemo(() => mapProductCategoryTree(categoryNodes), [categoryNodes]);
  const taxonomyTreeData = useMemo(() => mapChapterTaxonomyTree(taxonomyNodes), [taxonomyNodes]);
  const nodeOptions = useMemo(
    () => flatNodes.map((node) => ({ label: node.title, value: node.outline_node_id })),
    [flatNodes],
  );
  const outlinePayload = useMemo(
    () =>
      flatNodes.map((node) => ({
        title: node.title,
        level: node.level,
        sort_order: node.sort_order,
        parent_id: node.parent_id,
      })),
    [flatNodes],
  );
  const categoryIds = useMemo(() => outline?.product_category_ids ?? [], [outline?.product_category_ids]);

  const reload = useCallback(async () => {
    if (!selectedKbId || !bidOutlineId) return;
    setLoading(true);
    try {
      const [outlineResult, nodeResult, categories, taxonomies] = await Promise.all([
        getOutline(selectedKbId, bidOutlineId),
        getNodes(selectedKbId, bidOutlineId),
        getProductCategoryTree(selectedKbId),
        getChapterTaxonomyTree(selectedKbId),
      ]);
      setOutline(outlineResult);
      setFlatNodes((nodeResult.nodes ?? []).map((node) => ({ ...node, product_category_ids: node.product_category_ids ?? [] })));
      setCategoryNodes(categories ?? []);
      setTaxonomyNodes(taxonomies ?? []);
      setSelectedNodeId((prev) => prev ?? nodeResult.nodes?.[0]?.outline_node_id ?? null);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [bidOutlineId, selectedKbId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const updateSelected = (patch: Partial<FlatNode>) => {
    if (!selectedNodeId) return;
    setFlatNodes((prev) => prev.map((node) => (node.outline_node_id === selectedNodeId ? { ...node, ...patch } : node)));
  };

  const handleDropNode = (dragId: string, dropId: string, dropToGap: boolean) => {
    setFlatNodes((prev) => moveNodeLocally(prev, dragId, dropId, dropToGap));
  };

  const handleSaveNode = async () => {
    if (!selectedKbId || !bidOutlineId || !selectedNode) return;
    setSaving(true);
    try {
      await patchNode(selectedKbId, bidOutlineId, selectedNode.outline_node_id, {
        title: selectedNode.title,
        parent_id: selectedNode.parent_id,
        level: selectedNode.level,
        sort_order: selectedNode.sort_order,
        chapter_taxonomy_id: selectedNode.chapter_taxonomy_id,
        product_category_ids: selectedNode.product_category_ids ?? [],
        needs_manual_review: selectedNode.needs_manual_review,
      });
      message.success("节点已保存");
      await reload();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveTree = async () => {
    if (!selectedKbId || !bidOutlineId) return;
    const operations = buildReorderOps(flatNodes);
    if (operations.length === 0) return;
    setSaving(true);
    try {
      const result = await batchOps(selectedKbId, bidOutlineId, operations);
      setFlatNodes(result.nodes ?? []);
      message.success("目录结构已保存");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteNode = async () => {
    if (!selectedKbId || !bidOutlineId || !selectedNodeId) return;
    setSaving(true);
    try {
      const result = await batchOps(selectedKbId, bidOutlineId, [{ op: "delete", outline_node_id: selectedNodeId }]);
      setFlatNodes(result.nodes ?? []);
      setSelectedNodeId(null);
      message.success("节点已删除");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmOutline = async () => {
    if (!selectedKbId || !bidOutlineId) return;
    setSaving(true);
    try {
      const result = await confirmOutline(selectedKbId, bidOutlineId);
      setOutline(result);
      message.success("目录已确认");
      await reload();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }
  if (!bidOutlineId) {
    return <Alert message="缺少 bidOutlineId" type="error" showIcon />;
  }

  return (
    <>
      <Card
        loading={loading}
        title={`目录详情：${outline?.outline_name ?? bidOutlineId}`}
        extra={
          <Space>
            <Tag color={outline?.status === "confirmed" ? "green" : "default"}>{outline?.status ?? "-"}</Tag>
            <Button onClick={() => navigate("/outlines")}>返回目录中心</Button>
            <Button onClick={() => setDiffDrawerOpen(true)}>查看差异</Button>
            <Button onClick={() => setSimilarityDrawerOpen(true)}>目录相似度</Button>
            <Button onClick={() => setSuggestionWizardOpen(true)}>模块建议</Button>
            <Button type="primary" disabled={readOnly} loading={saving} onClick={() => void handleConfirmOutline()}>
              确认目录
            </Button>
          </Space>
        }
      >
        <Descriptions column={3} size="small" style={{ marginBottom: 16 }}>
          <Descriptions.Item label="项目名">{outline?.project_name || "-"}</Descriptions.Item>
          <Descriptions.Item label="客户名">{outline?.customer_name || "-"}</Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {outline?.updated_at ? new Date(outline.updated_at).toLocaleString() : "-"}
          </Descriptions.Item>
        </Descriptions>
        <Row gutter={16}>
          <Col span={15}>
            <OutlineTreeEditor
              roots={treeRoots}
              selectedId={selectedNodeId}
              onSelect={setSelectedNodeId}
              onDropNode={handleDropNode}
              onViewContent={setContentDrawerNodeId}
            />
            <Space style={{ marginTop: 12 }}>
              <Button loading={saving} disabled={readOnly} onClick={() => void handleSaveTree()}>
                保存拖拽结构
              </Button>
            </Space>
          </Col>
          <Col span={9}>
            <Card size="small" title="节点属性">
              {!selectedNode ? (
                <Alert type="info" showIcon message="请先在左侧选择一个节点" />
              ) : (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <Input
                    value={selectedNode.title}
                    onChange={(event) => updateSelected({ title: event.target.value })}
                    placeholder="章节标题"
                  />
                  <Select
                    allowClear
                    value={selectedNode.parent_id ?? undefined}
                    options={nodeOptions.filter((item) => item.value !== selectedNode.outline_node_id)}
                    onChange={(value) => updateSelected({ parent_id: (value as string) ?? null })}
                    placeholder="父节点"
                  />
                  <TreeSelect
                    allowClear
                    treeData={taxonomyTreeData}
                    value={selectedNode.chapter_taxonomy_id ?? undefined}
                    onChange={(value) => updateSelected({ chapter_taxonomy_id: (value as string) ?? null })}
                    placeholder="章节类型"
                  />
                  <TreeSelect
                    treeCheckable
                    treeData={categoryTreeData}
                    value={selectedNode.product_category_ids}
                    onChange={(value) => updateSelected({ product_category_ids: (value as string[]) ?? [] })}
                    placeholder="产品分类"
                  />
                  <Space>
                    <span>人工复核</span>
                    <Switch
                      checked={selectedNode.needs_manual_review}
                      onChange={(checked) => updateSelected({ needs_manual_review: checked })}
                    />
                  </Space>
                  <Space>
                    <Button type="primary" loading={saving} disabled={readOnly} onClick={() => void handleSaveNode()}>
                      保存节点
                    </Button>
                    <Popconfirm
                      title="确认删除该节点及其子节点？"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => void handleDeleteNode()}
                    >
                      <Button danger loading={saving} disabled={readOnly}>
                        删除节点
                      </Button>
                    </Popconfirm>
                  </Space>
                </Space>
              )}
            </Card>
          </Col>
        </Row>
      </Card>
      <OutlineDiffDrawer
        open={diffDrawerOpen}
        kbId={selectedKbId}
        bidOutlineId={bidOutlineId}
        onClose={() => setDiffDrawerOpen(false)}
        onApplied={reload}
      />
      <OutlineSimilarityDrawer
        open={similarityDrawerOpen}
        kbId={selectedKbId}
        outlineNodes={outlinePayload}
        productCategoryIds={categoryIds}
        onClose={() => setSimilarityDrawerOpen(false)}
      />
      <ModuleSuggestionWizard
        open={suggestionWizardOpen}
        kbId={selectedKbId}
        outlineNodes={outlinePayload}
        productCategoryIds={categoryIds}
        onClose={() => setSuggestionWizardOpen(false)}
      />
      <OutlineNodeContentDrawer
        open={contentDrawerNodeId != null}
        kbId={selectedKbId}
        bidOutlineId={bidOutlineId}
        outlineNodeId={contentDrawerNodeId}
        onClose={() => setContentDrawerNodeId(null)}
      />
    </>
  );
}
