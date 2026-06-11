import { Alert, Card, Col, Row, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import CategoryDetailPanel from "../../components/CategoryDetailPanel";
import CategoryTreePanel from "../../components/CategoryTreePanel";
import ClassificationLifecycleActions from "../../components/ClassificationLifecycleActions";
import ImpactAnalysisModal from "../../components/ImpactAnalysisModal";
import MergeWizard from "../../components/MergeWizard";
import { useKBContext } from "../../layout/KBContext";
import { ApiError } from "../../services/apiClient";
import {
  archiveProductCategory,
  deactivateProductCategory,
  getProductCategoryImpact,
  mergeProductCategory,
  type ImpactReport,
} from "../../services/lifecycleApi";
import {
  createProductCategory,
  getProductCategoryDetail,
  getProductCategoryTree,
  replaceProductCategoryAliases,
  updateProductCategory,
  type ProductCategoryDetail,
  type ProductCategoryNode,
} from "../../services/productCategoryApi";
import { collectDescendantIds, flattenTreeOptions } from "../../utils/classificationTree";

type EditorMode =
  | { kind: "none" }
  | { kind: "new"; parentId: string | null }
  | { kind: "existing"; categoryId: string };

export default function ProductCategoryCenterPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [nodes, setNodes] = useState<ProductCategoryNode[]>([]);
  const [detail, setDetail] = useState<ProductCategoryDetail | undefined>();
  const [editor, setEditor] = useState<EditorMode>({ kind: "none" });
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [impactOpen, setImpactOpen] = useState(false);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactReport, setImpactReport] = useState<ImpactReport | undefined>();
  const [mergeOpen, setMergeOpen] = useState(false);

  const treeOptions = useMemo(
    () =>
      flattenTreeOptions(
        nodes.map((n) => ({
          id: n.category_id,
          label: n.category_name,
          children: mapCategoryChildren(n.children),
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
        id: n.category_id,
        children: mapCategoryChildren(n.children),
      })),
      editor.categoryId,
    );
    return treeOptions.filter((opt) => !excluded.has(opt.value));
  }, [editor, nodes, treeOptions]);

  const loadTree = useCallback(async () => {
    if (!selectedKbId) {
      setNodes([]);
      return;
    }
    setLoadingTree(true);
    try {
      const tree = await getProductCategoryTree(selectedKbId);
      setNodes(tree);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoadingTree(false);
    }
  }, [selectedKbId]);

  const loadDetail = useCallback(
    async (categoryId: string) => {
      if (!selectedKbId) {
        return;
      }
      setLoadingDetail(true);
      try {
        const data = await getProductCategoryDetail(selectedKbId, categoryId);
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

  const handleSelect = (categoryId: string) => {
    setEditor({ kind: "existing", categoryId });
    void loadDetail(categoryId);
  };

  const handleSave = async (values: {
    category_name: string;
    category_code: string;
    description?: string;
    aliases: string[];
    status?: string;
  }) => {
    if (!selectedKbId || readOnly) {
      return;
    }
    setSaving(true);
    try {
      if (editor.kind === "new") {
        const created = await createProductCategory(selectedKbId, {
          parent_id: editor.parentId,
          category_name: values.category_name,
          category_code: values.category_code,
          description: values.description,
          aliases: values.aliases,
        });
        message.success("分类创建成功");
        await loadTree();
        setEditor({ kind: "existing", categoryId: created.category_id });
        await loadDetail(created.category_id);
        return;
      }

      if (editor.kind !== "existing") {
        return;
      }

      await updateProductCategory(selectedKbId, editor.categoryId, {
        category_name: values.category_name,
        description: values.description,
        status: values.status,
      });
      await replaceProductCategoryAliases(
        selectedKbId,
        editor.categoryId,
        values.aliases,
      );
      message.success("分类已保存");
      await Promise.all([loadTree(), loadDetail(editor.categoryId)]);
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
      const report = await getProductCategoryImpact(selectedKbId, editor.categoryId);
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
      await deactivateProductCategory(selectedKbId, editor.categoryId);
      message.success("分类已停用");
      await Promise.all([loadTree(), loadDetail(editor.categoryId)]);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const handleArchive = async () => {
    if (!selectedKbId || editor.kind !== "existing") {
      return;
    }
    try {
      await archiveProductCategory(selectedKbId, editor.categoryId);
      message.success("分类已归档");
      await Promise.all([loadTree(), loadDetail(editor.categoryId)]);
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
        <CategoryTreePanel
          nodes={nodes}
          selectedId={editor.kind === "existing" ? editor.categoryId : undefined}
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
        <CategoryDetailPanel
          detail={editor.kind === "existing" ? detail : undefined}
          readOnly={readOnly}
          saving={saving || loadingDetail}
          isNew={editor.kind === "new"}
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
          sourceLabel={detail.category_name}
          targetOptions={mergeTargetOptions}
          onClose={() => setMergeOpen(false)}
          onLoadImpact={(targetId) =>
            getProductCategoryImpact(selectedKbId, targetId)
          }
          onConfirmMerge={(targetId) =>
            mergeProductCategory(selectedKbId, editor.categoryId, targetId)
          }
          onMerged={async (result) => {
            message.success(`合并完成，迁移 ${result.migrated_reference_count} 条引用`);
            await loadTree();
            setEditor({ kind: "existing", categoryId: result.target_id });
            await loadDetail(result.target_id);
          }}
        />
      )}
    </Row>
  );
}

function mapCategoryChildren(
  children: ProductCategoryNode[],
): Array<{ id: string; label: string; children: ReturnType<typeof mapCategoryChildren> }> {
  return children.map((child) => ({
    id: child.category_id,
    label: child.category_name,
    children: mapCategoryChildren(child.children),
  }));
}
