import { Alert, Button, Card, Col, Row, Space, Tabs, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  batchUpdateTemplateChapters,
  getTemplateChapterTree,
  listTemplateMaterials,
  listTemplateRules,
  listTemplateVariables,
  type ChapterTreeNode,
  type TemplateMaterialItem,
  type TemplateRuleItem,
  type TemplateVariableItem,
} from "../../services/templates";
import ChapterPropertyPanel from "./ChapterPropertyPanel";
import ChapterTreeEditor from "./ChapterTreeEditor";
import MaterialPanel from "./MaterialPanel";
import VariableRulePanel from "./VariableRulePanel";

type FlatNode = Omit<ChapterTreeNode, "children">;

function flattenTree(nodes: ChapterTreeNode[]): FlatNode[] {
  const result: FlatNode[] = [];
  const visit = (items: ChapterTreeNode[]) => {
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

function buildTree(nodes: FlatNode[]): ChapterTreeNode[] {
  const map = new Map<string, ChapterTreeNode>();
  const roots: ChapterTreeNode[] = [];
  for (const node of nodes) {
    map.set(node.template_chapter_id, { ...node, children: [] });
  }
  for (const node of nodes) {
    const current = map.get(node.template_chapter_id);
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
  const normalize = (items: ChapterTreeNode[], level: number) => {
    items.forEach((item, index) => {
      item.level = level;
      item.sort_order = index;
      normalize(item.children, level + 1);
    });
  };
  normalize(roots, 1);
  return roots;
}

export default function TemplateDetailPage() {
  const { templateId } = useParams<{ templateId: string }>();
  const { selectedKbId } = useKBContext();
  const [loading, setLoading] = useState(false);
  const [savingTree, setSavingTree] = useState(false);
  const [treeRoots, setTreeRoots] = useState<ChapterTreeNode[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
  const [materials, setMaterials] = useState<TemplateMaterialItem[]>([]);
  const [variables, setVariables] = useState<TemplateVariableItem[]>([]);
  const [rules, setRules] = useState<TemplateRuleItem[]>([]);

  const loadData = useCallback(async () => {
    if (!selectedKbId || !templateId) return;
    setLoading(true);
    try {
      const [tree, materialResult, variableResult, ruleResult] = await Promise.all([
        getTemplateChapterTree(selectedKbId, templateId),
        listTemplateMaterials(selectedKbId, templateId),
        listTemplateVariables(selectedKbId, templateId),
        listTemplateRules(selectedKbId, templateId),
      ]);
      setTreeRoots(tree.roots ?? []);
      setMaterials(materialResult.items ?? []);
      setVariables(variableResult.items ?? []);
      setRules(ruleResult.items ?? []);
      setSelectedChapterId((prev) => prev ?? tree.roots?.[0]?.template_chapter_id ?? null);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selectedKbId, templateId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const flatNodes = useMemo(() => flattenTree(treeRoots), [treeRoots]);
  const selectedNode = useMemo(
    () => flatNodes.find((item) => item.template_chapter_id === selectedChapterId) ?? null,
    [flatNodes, selectedChapterId],
  );

  const applyFlatNodes = (nextFlat: FlatNode[]) => {
    setTreeRoots(buildTree(nextFlat));
  };

  const updateSelectedChapter = (patch: Partial<ChapterTreeNode>) => {
    if (!selectedChapterId) return;
    const nextFlat = flatNodes.map((item) =>
      item.template_chapter_id === selectedChapterId ? { ...item, ...patch } : item,
    );
    applyFlatNodes(nextFlat);
  };

  const moveNode = (dragId: string, dropId: string | null, dropToGap: boolean) => {
    if (!dropId || dragId === dropId) return;
    const byId = new Map(flatNodes.map((item) => [item.template_chapter_id, { ...item }]));
    const drag = byId.get(dragId);
    const target = byId.get(dropId);
    if (!drag || !target) return;
    let cursor: FlatNode | undefined = target;
    while (cursor) {
      if (cursor.template_chapter_id === dragId) {
        return;
      }
      cursor = cursor.parent_id ? byId.get(cursor.parent_id) : undefined;
    }
    drag.parent_id = dropToGap ? target.parent_id : target.template_chapter_id;
    applyFlatNodes(Array.from(byId.values()));
  };

  const saveChapterTree = async () => {
    if (!selectedKbId || !templateId) return;
    setSavingTree(true);
    try {
      const payload = {
        chapters: flattenTree(treeRoots).map((item) => ({
          template_chapter_id: item.template_chapter_id,
          parent_id: item.parent_id,
          title: item.title,
          level: item.level,
          sort_order: item.sort_order,
          chapter_taxonomy_id: item.chapter_taxonomy_id,
          product_category_ids: item.product_category_ids ?? [],
          required: item.required,
          is_fixed_section: item.is_fixed_section,
          ignored: item.ignored,
        })),
      };
      const result = await batchUpdateTemplateChapters(selectedKbId, templateId, payload);
      setTreeRoots(result.roots ?? []);
      message.success("章节树已保存");
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setSavingTree(false);
    }
  };

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }
  if (!templateId) {
    return <Alert message="缺少 templateId" type="error" showIcon />;
  }

  return (
    <Card
      title={`模板详情：${templateId}`}
      loading={loading}
      extra={
        <Space>
          <Button loading={savingTree} type="primary" onClick={() => void saveChapterTree()}>
            保存章节树
          </Button>
        </Space>
      }
    >
      <Tabs
        items={[
          {
            key: "chapters",
            label: "章节树",
            children: (
              <Row gutter={16}>
                <Col span={16}>
                  <ChapterTreeEditor
                    roots={treeRoots}
                    selectedId={selectedChapterId}
                    onSelect={setSelectedChapterId}
                    onDropNode={moveNode}
                  />
                </Col>
                <Col span={8}>
                  <ChapterPropertyPanel selected={selectedNode} onChange={updateSelectedChapter} />
                </Col>
              </Row>
            ),
          },
          {
            key: "materials",
            label: "素材",
            children: (
              <MaterialPanel
                kbId={selectedKbId}
                templateId={templateId}
                items={materials}
                onReload={loadData}
              />
            ),
          },
          {
            key: "variable-rules",
            label: "变量/规则",
            children: (
              <VariableRulePanel
                kbId={selectedKbId}
                templateId={templateId}
                variables={variables}
                rules={rules}
                onReload={loadData}
              />
            ),
          },
        ]}
      />
    </Card>
  );
}
