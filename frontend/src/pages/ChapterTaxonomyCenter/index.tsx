import { Alert, Card, Col, Row, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import TaxonomyDetailPanel from "../../components/TaxonomyDetailPanel";
import TaxonomyTreePanel from "../../components/TaxonomyTreePanel";
import ClassificationLifecycleActions from "../../components/ClassificationLifecycleActions";
import ImpactAnalysisModal from "../../components/ImpactAnalysisModal";
import MergeWizard from "../../components/MergeWizard";
import { useKBContext } from "../../layout/KBContext";
import { ApiError } from "../../services/apiClient";
import {
  createChapterTaxonomy,
  getChapterTaxonomyDetail,
  getChapterTaxonomyTree,
  replaceChapterTaxonomyBindings,
  replaceChapterTaxonomySynonyms,
  updateChapterTaxonomy,
  type ChapterTaxonomyDetail,
  type ChapterTaxonomyNode,
} from "../../services/chapterTaxonomyApi";
import {
  archiveChapterTaxonomy,
  deactivateChapterTaxonomy,
  getChapterTaxonomyImpact,
  mergeChapterTaxonomy,
  type ImpactReport,
} from "../../services/lifecycleApi";
import {
  getProductCategoryTree,
  type ProductCategoryNode,
} from "../../services/productCategoryApi";
import { collectDescendantIds, flattenTreeOptions } from "../../utils/classificationTree";

type EditorMode =
  | { kind: "none" }
  | { kind: "new"; parentId: string | null }
  | { kind: "existing"; taxonomyId: string };

function flattenCategories(
  nodes: ProductCategoryNode[],
  prefix = "",
): Array<{ label: string; value: string }> {
  const result: Array<{ label: string; value: string }> = [];
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.category_name}` : node.category_name;
    result.push({ label, value: node.category_id });
    result.push(...flattenCategories(node.children, label));
  }
  return result;
}

export default function ChapterTaxonomyCenterPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [nodes, setNodes] = useState<ChapterTaxonomyNode[]>([]);
  const [detail, setDetail] = useState<ChapterTaxonomyDetail | undefined>();
  const [categoryNodes, setCategoryNodes] = useState<ProductCategoryNode[]>([]);
  const [editor, setEditor] = useState<EditorMode>({ kind: "none" });
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [impactOpen, setImpactOpen] = useState(false);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactReport, setImpactReport] = useState<ImpactReport | undefined>();
  const [mergeOpen, setMergeOpen] = useState(false);

  const productCategoryOptions = useMemo(
    () => flattenCategories(categoryNodes),
    [categoryNodes],
  );

  const treeOptions = useMemo(
    () =>
      flattenTreeOptions(
        nodes.map((n) => ({
          id: n.taxonomy_id,
          label: n.standard_name,
          children: mapTaxonomyChildren(n.children),
        })),
      ),
    [nodes],
  );

  const mergeTargetOptions = useMemo(() => {
    if (editor.kind !== "existing") {
      return [];
    }
    const excluded = collectDescendantIds(
      nodes.map((n) => ({
        id: n.taxonomy_id,
        children: mapTaxonomyChildren(n.children),
      })),
      editor.taxonomyId,
    );
    return treeOptions.filter((opt) => !excluded.has(opt.value));
  }, [editor, nodes, treeOptions]);

  const loadTree = useCallback(async () => {
    if (!selectedKbId) {
      setNodes([]);
      setCategoryNodes([]);
      return;
    }
    setLoadingTree(true);
    try {
      const [taxonomyTree, categoryTree] = await Promise.all([
        getChapterTaxonomyTree(selectedKbId),
        getProductCategoryTree(selectedKbId),
      ]);
      setNodes(taxonomyTree);
      setCategoryNodes(categoryTree);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoadingTree(false);
    }
  }, [selectedKbId]);

  const loadDetail = useCallback(
    async (taxonomyId: string) => {
      if (!selectedKbId) {
        return;
      }
      setLoadingDetail(true);
      try {
        const data = await getChapterTaxonomyDetail(selectedKbId, taxonomyId);
        setDetail(data);
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setLoadingDetail(false);
      }
    },
    [selectedKbId],
  );

  useEffect(() => {
    void loadTree();
    setEditor({ kind: "none" });
    setDetail(undefined);
  }, [loadTree, selectedKbId]);

  const handleSelect = (taxonomyId: string) => {
    setEditor({ kind: "existing", taxonomyId });
    void loadDetail(taxonomyId);
  };

  const handleSave = async (values: {
    standard_name: string;
    taxonomy_code: string;
    description?: string;
    synonyms: string[];
    product_category_ids: string[];
    status?: string;
  }) => {
    if (!selectedKbId || readOnly) {
      return;
    }
    setSaving(true);
    try {
      if (editor.kind === "new") {
        const created = await createChapterTaxonomy(selectedKbId, {
          parent_id: editor.parentId,
          standard_name: values.standard_name,
          taxonomy_code: values.taxonomy_code,
          description: values.description,
          synonyms: values.synonyms,
          product_category_ids: values.product_category_ids,
        });
        message.success("章节类型创建成功");
        await loadTree();
        setEditor({ kind: "existing", taxonomyId: created.taxonomy_id });
        await loadDetail(created.taxonomy_id);
        return;
      }

      if (editor.kind !== "existing") {
        return;
      }

      await updateChapterTaxonomy(selectedKbId, editor.taxonomyId, {
        standard_name: values.standard_name,
        description: values.description,
        status: values.status,
      });
      await replaceChapterTaxonomySynonyms(
        selectedKbId,
        editor.taxonomyId,
        values.synonyms,
      );
      await replaceChapterTaxonomyBindings(
        selectedKbId,
        editor.taxonomyId,
        values.product_category_ids,
      );
      message.success("章节类型已保存");
      await Promise.all([loadTree(), loadDetail(editor.taxonomyId)]);
    } catch (error) {
      if (error instanceof ApiError) {
        message.error(error.message);
      } else {
        message.error((error as Error).message);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleImpact = async () => {
    if (!selectedKbId || editor.kind !== "existing") {
      return;
    }
    setImpactOpen(true);
    setImpactLoading(true);
    try {
      const report = await getChapterTaxonomyImpact(selectedKbId, editor.taxonomyId);
      setImpactReport(report);
    } catch (error) {
      message.error((error as Error).message);
      setImpactOpen(false);
    } finally {
      setImpactLoading(false);
    }
  };

  const handleDeactivate = async () => {
    if (!selectedKbId || editor.kind !== "existing") {
      return;
    }
    try {
      await deactivateChapterTaxonomy(selectedKbId, editor.taxonomyId);
      message.success("章节类型已停用");
      await Promise.all([loadTree(), loadDetail(editor.taxonomyId)]);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const handleArchive = async () => {
    if (!selectedKbId || editor.kind !== "existing") {
      return;
    }
    try {
      await archiveChapterTaxonomy(selectedKbId, editor.taxonomyId);
      message.success("章节类型已归档");
      await Promise.all([loadTree(), loadDetail(editor.taxonomyId)]);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  if (!selectedKbId) {
    return <Alert type="info" showIcon message="请先在顶栏选择一个知识库" />;
  }

  return (
    <Row gutter={16}>
      <Col span={10}>
        <TaxonomyTreePanel
          nodes={nodes}
          selectedId={editor.kind === "existing" ? editor.taxonomyId : undefined}
          readOnly={readOnly}
          loading={loadingTree}
          onSelect={handleSelect}
          onCreateRoot={() => {
            setEditor({ kind: "new", parentId: null });
            setDetail(undefined);
          }}
          onCreateChild={(parentId) => {
            setEditor({ kind: "new", parentId });
            setDetail(undefined);
          }}
        />
      </Col>
      <Col span={14}>
        {editor.kind === "existing" && detail && (
          <Card size="small" style={{ marginBottom: 16 }}>
            <ClassificationLifecycleActions
              readOnly={readOnly}
              status={detail.status}
              onImpact={handleImpact}
              onMerge={() => setMergeOpen(true)}
              onDeactivate={handleDeactivate}
              onArchive={handleArchive}
            />
          </Card>
        )}
        <TaxonomyDetailPanel
          detail={editor.kind === "existing" ? detail : undefined}
          readOnly={readOnly}
          saving={saving || loadingDetail}
          isNew={editor.kind === "new"}
          productCategoryOptions={productCategoryOptions}
          onSave={handleSave}
        />
      </Col>

      <ImpactAnalysisModal
        open={impactOpen}
        loading={impactLoading}
        report={impactReport}
        onClose={() => setImpactOpen(false)}
      />

      {editor.kind === "existing" && detail && (
        <MergeWizard
          open={mergeOpen}
          sourceLabel={detail.standard_name}
          targetOptions={mergeTargetOptions}
          onClose={() => setMergeOpen(false)}
          onLoadImpact={(targetId) =>
            getChapterTaxonomyImpact(selectedKbId, targetId)
          }
          onConfirmMerge={(targetId) =>
            mergeChapterTaxonomy(selectedKbId, editor.taxonomyId, targetId)
          }
          onMerged={async (result) => {
            message.success(`合并完成，迁移 ${result.migrated_reference_count} 条引用`);
            await loadTree();
            setEditor({ kind: "existing", taxonomyId: result.target_id });
            await loadDetail(result.target_id);
          }}
        />
      )}
    </Row>
  );
}

function mapTaxonomyChildren(
  children: ChapterTaxonomyNode[],
): Array<{ id: string; label: string; children: ReturnType<typeof mapTaxonomyChildren> }> {
  return children.map((child) => ({
    id: child.taxonomy_id,
    label: child.standard_name,
    children: mapTaxonomyChildren(child.children),
  }));
}
