import {
  Alert,
  Button,
  Card,
  Checkbox,
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
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getChapterTaxonomyTree, type ChapterTaxonomyNode } from "../../services/chapterTaxonomyApi";
import { useKBContext } from "../../layout/KBContext";
import { getProductCategoryTree } from "../../services/productCategoryApi";
import {
  confirmParseTask,
  getParseSuggestion,
  getParseTask,
  listTemplateLibraries,
  type ParseSuggestionCandidate,
  type ParseSuggestionChapterNode,
  type ParseSuggestionMaterial,
  type TemplateLibraryListItem,
} from "../../services/templates";

type CandidateActionRow = {
  temp_id: string;
  candidate_type: "ku" | "wiki";
  accepted: boolean;
  title?: string;
  product_category_ids?: string[];
  chapter_taxonomy_id?: string | null;
  knowledge_type?: string | null;
  suggestion_source?: string;
};

type ProductCategoryOption = { label: string; value: string };

const LIBRARY_TYPE_OPTIONS = [
  { label: "技术标", value: "technical" },
  { label: "商务标", value: "commercial" },
  { label: "资质标", value: "qualification" },
  { label: "产品专属", value: "product_specific" },
  { label: "自定义", value: "custom" },
];

const TEMPLATE_TYPE_OPTIONS = [
  { label: "技术标", value: "technical_bid" },
  { label: "商务标", value: "commercial_bid" },
  { label: "资质标", value: "qualification" },
  { label: "章节集", value: "chapter_set" },
  { label: "自定义", value: "custom" },
];

const KNOWLEDGE_TYPE_OPTIONS = [
  { label: "方案", value: "scheme" },
  { label: "产品", value: "product" },
  { label: "资质", value: "qualification" },
  { label: "其他", value: "other" },
];

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

export default function ParseConfirmWizard() {
  const { parseTaskId } = useParams<{ parseTaskId: string }>();
  const navigate = useNavigate();
  const { selectedKbId } = useKBContext();
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [libraries, setLibraries] = useState<TemplateLibraryListItem[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<ProductCategoryOption[]>([]);
  const [taxonomyNodes, setTaxonomyNodes] = useState<ChapterTaxonomyNode[]>([]);
  const [chapters, setChapters] = useState<ParseSuggestionChapterNode[]>([]);
  const [materials, setMaterials] = useState<ParseSuggestionMaterial[]>([]);
  const [candidateActions, setCandidateActions] = useState<CandidateActionRow[]>([]);
  const [needsManualReview, setNeedsManualReview] = useState(false);
  const [parseStatus, setParseStatus] = useState<string>();
  const [createLibraryMode, setCreateLibraryMode] = useState(false);

  const chapterTaxonomyTreeData = useMemo(
    () => mapChapterTaxonomyTree(taxonomyNodes),
    [taxonomyNodes],
  );

  const loadData = useCallback(async () => {
    if (!selectedKbId || !parseTaskId) {
      return;
    }
    setLoading(true);
    try {
      const [task, suggestion, libraryResult, categoryTree, taxonomyTree] = await Promise.all([
        getParseTask(selectedKbId, parseTaskId),
        getParseSuggestion(selectedKbId, parseTaskId),
        listTemplateLibraries(selectedKbId, { page_size: 200 }),
        getProductCategoryTree(selectedKbId),
        getChapterTaxonomyTree(selectedKbId),
      ]);
      setParseStatus(task.status);
      setLibraries(libraryResult.items ?? []);
      setCategoryOptions(flattenCategoryTree(categoryTree ?? []));
      setTaxonomyNodes(taxonomyTree ?? []);
      setChapters(
        (suggestion.suggested_chapter_tree ?? []).map((chapter) => ({
          ...chapter,
          chapter_taxonomy_id:
            chapter.chapter_taxonomy_id ?? chapter.suggested_chapter_taxonomy_id ?? null,
          product_category_ids:
            chapter.product_category_ids?.length
              ? chapter.product_category_ids
              : (chapter.suggested_product_category_ids ?? []),
        })),
      );
      setMaterials(
        (suggestion.suggested_materials ?? []).map((material) => ({
          ...material,
          product_category_ids:
            material.product_category_ids?.length
              ? material.product_category_ids
              : (material.suggested_product_category_ids ?? []),
        })),
      );
      const candidateRows: CandidateActionRow[] = (suggestion.suggested_candidates ?? []).map(
        (candidate: ParseSuggestionCandidate) => ({
          temp_id: candidate.temp_id,
          candidate_type: candidate.candidate_type === "wiki" ? "wiki" : "ku",
          accepted: true,
          title: candidate.title,
          product_category_ids:
            candidate.product_category_ids?.length
              ? candidate.product_category_ids
              : (candidate.suggested_product_category_ids ?? []),
          chapter_taxonomy_id:
            candidate.chapter_taxonomy_id ?? candidate.suggested_chapter_taxonomy_id ?? null,
          knowledge_type: candidate.knowledge_type ?? candidate.suggested_knowledge_type ?? null,
          suggestion_source: candidate.suggestion_source,
        }),
      );
      setCandidateActions(candidateRows);
      setNeedsManualReview(
        Boolean((suggestion.suggested_chapter_tree ?? []).some((item) => item.needs_manual_review)),
      );
      form.setFieldsValue({
        template_library_id: suggestion.suggested_library_id ?? undefined,
        template_name: task.template_id ? task.suggestion?.suggested_library_name ?? "" : "",
        template_type: "technical_bid",
        product_category_ids: [],
        create_library_name: suggestion.suggested_library_name ?? "",
        create_library_type: "technical",
      });
      if (task.suggestion?.suggested_library_name) {
        form.setFieldValue("template_name", task.suggestion.suggested_library_name);
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [form, parseTaskId, selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const libraryOptions = useMemo(
    () =>
      libraries.map((library) => ({
        label: `${library.library_name} (${library.library_type})`,
        value: library.template_library_id,
      })),
    [libraries],
  );

  const updateChapter = (tempId: string, patch: Partial<ParseSuggestionChapterNode>) => {
    setChapters((prev) => prev.map((item) => (item.temp_id === tempId ? { ...item, ...patch } : item)));
  };

  const updateMaterial = (tempId: string, patch: Partial<ParseSuggestionMaterial>) => {
    setMaterials((prev) => prev.map((item) => (item.temp_id === tempId ? { ...item, ...patch } : item)));
  };

  const updateCandidate = (tempId: string, patch: Partial<CandidateActionRow>) => {
    setCandidateActions((prev) =>
      prev.map((item) => (item.temp_id === tempId ? { ...item, ...patch } : item)),
    );
  };

  const applyQuickCategoriesToChapters = () => {
    const quick = form.getFieldValue("product_category_ids") ?? [];
    if (!quick.length) {
      message.info("请先在 Step1 选择快捷产品分类");
      return;
    }
    setChapters((prev) =>
      prev.map((chapter) => ({ ...chapter, product_category_ids: [...quick] })),
    );
  };

  const step1Valid = useMemo(() => {
    const values = form.getFieldsValue();
    if (!values.template_name || !values.template_type) {
      return false;
    }
    if (createLibraryMode) {
      return Boolean(values.create_library_name && values.create_library_type);
    }
    return true;
  }, [createLibraryMode, form]);

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
      const result = await confirmParseTask(selectedKbId, parseTaskId, {
        template_library_id: createLibraryMode ? null : (values.template_library_id ?? null),
        create_library: createLibraryMode
          ? {
              library_name: values.create_library_name,
              library_type: values.create_library_type,
            }
          : null,
        template_name: values.template_name,
        template_type: values.template_type,
        product_category_ids: values.product_category_ids ?? [],
        chapters,
        materials,
        candidate_actions: candidateActions.map((item) => ({
          temp_id: item.temp_id,
          candidate_type: item.candidate_type,
          accepted: item.accepted,
          product_category_ids: item.product_category_ids ?? [],
          chapter_taxonomy_id: item.chapter_taxonomy_id ?? null,
          knowledge_type: item.knowledge_type ?? null,
        })),
      });
      message.success(`确认成功，已创建 ${result.candidate_stubs_created} 条候选占位`);
      navigate(`/template-libraries?highlight=${result.parse_task_id}`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const chapterColumns = [
    {
      title: "章节标题",
      dataIndex: "title",
      key: "title",
      render: (value: string, record: ParseSuggestionChapterNode) => (
        <Input value={value} onChange={(event) => updateChapter(record.temp_id, { title: event.target.value })} />
      ),
    },
    {
      title: "层级",
      dataIndex: "level",
      key: "level",
      width: 120,
      render: (value: number, record: ParseSuggestionChapterNode) => (
        <InputNumber
          min={1}
          max={9}
          value={value}
          onChange={(next) => updateChapter(record.temp_id, { level: Number(next ?? 1) })}
        />
      ),
    },
    {
      title: "父节点",
      dataIndex: "parent_temp_id",
      key: "parent_temp_id",
      render: (value: string | null, record: ParseSuggestionChapterNode) => (
        <Select
          style={{ width: 180 }}
          allowClear
          value={value ?? undefined}
          options={chapters
            .filter((item) => item.temp_id !== record.temp_id)
            .map((item) => ({ label: item.title, value: item.temp_id }))}
          onChange={(next) => updateChapter(record.temp_id, { parent_temp_id: next ?? null })}
        />
      ),
    },
    {
      title: "章节类型",
      dataIndex: "chapter_taxonomy_id",
      key: "chapter_taxonomy_id",
      width: 200,
      render: (value: string | null, record: ParseSuggestionChapterNode) => (
        <TreeSelect
          allowClear
          style={{ width: 180 }}
          treeData={chapterTaxonomyTreeData}
          value={value ?? undefined}
          onChange={(next) =>
            updateChapter(record.temp_id, { chapter_taxonomy_id: (next as string) ?? null })
          }
        />
      ),
    },
    {
      title: "产品分类",
      dataIndex: "product_category_ids",
      key: "product_category_ids",
      width: 200,
      render: (value: string[], record: ParseSuggestionChapterNode) => (
        <Select
          mode="multiple"
          allowClear
          style={{ width: 180 }}
          options={categoryOptions}
          value={value ?? []}
          onChange={(next) => updateChapter(record.temp_id, { product_category_ids: next })}
        />
      ),
    },
    {
      title: "建议来源",
      dataIndex: "suggestion_source",
      key: "suggestion_source",
      width: 100,
      render: (value: string | undefined) =>
        value ? <Tag>{value}</Tag> : <Tag>rule</Tag>,
    },
    {
      title: "属性",
      key: "flags",
      render: (_: unknown, record: ParseSuggestionChapterNode) => (
        <Space>
          <Checkbox
            checked={record.required}
            onChange={(event) => updateChapter(record.temp_id, { required: event.target.checked })}
          >
            必填
          </Checkbox>
          <Checkbox
            checked={record.is_fixed_section}
            onChange={(event) =>
              updateChapter(record.temp_id, { is_fixed_section: event.target.checked })
            }
          >
            固定章节
          </Checkbox>
          <Checkbox
            checked={record.ignored}
            onChange={(event) => updateChapter(record.temp_id, { ignored: event.target.checked })}
          >
            忽略
          </Checkbox>
        </Space>
      ),
    },
  ];

  const materialColumns = [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      render: (value: string, record: ParseSuggestionMaterial) => (
        <Input value={value} onChange={(event) => updateMaterial(record.temp_id, { title: event.target.value })} />
      ),
    },
    { title: "类型", dataIndex: "material_type", key: "material_type", width: 140 },
    {
      title: "章节",
      dataIndex: "chapter_temp_id",
      key: "chapter_temp_id",
      render: (value: string | null, record: ParseSuggestionMaterial) => (
        <Select
          allowClear
          style={{ width: 180 }}
          value={value ?? undefined}
          options={chapters.map((item) => ({ label: item.title, value: item.temp_id }))}
          onChange={(next) => updateMaterial(record.temp_id, { chapter_temp_id: next ?? null })}
        />
      ),
    },
    {
      title: "产品分类",
      dataIndex: "product_category_ids",
      key: "product_category_ids",
      render: (value: string[] | undefined, record: ParseSuggestionMaterial) => (
        <Select
          mode="multiple"
          allowClear
          style={{ width: 160 }}
          options={categoryOptions}
          value={value ?? []}
          onChange={(next) => updateMaterial(record.temp_id, { product_category_ids: next })}
        />
      ),
    },
    {
      title: "建议来源",
      dataIndex: "suggestion_source",
      key: "suggestion_source",
      width: 100,
      render: (value: string | undefined) => (value ? <Tag>{value}</Tag> : null),
    },
    {
      title: "候选提取",
      dataIndex: "extract_as_candidate",
      key: "extract_as_candidate",
      width: 120,
      render: (value: boolean, record: ParseSuggestionMaterial) => (
        <Switch
          size="small"
          checked={Boolean(value)}
          onChange={(next) => updateMaterial(record.temp_id, { extract_as_candidate: next })}
        />
      ),
    },
    {
      title: "忽略",
      dataIndex: "ignored",
      key: "ignored",
      width: 100,
      render: (value: boolean, record: ParseSuggestionMaterial) => (
        <Switch
          size="small"
          checked={Boolean(value)}
          onChange={(next) => updateMaterial(record.temp_id, { ignored: next })}
        />
      ),
    },
  ];

  const candidateColumns = [
    {
      title: "候选",
      dataIndex: "title",
      key: "title",
      render: (value: string | undefined, record: CandidateActionRow) => (
        <Space>
          <Tag>{record.temp_id}</Tag>
          <span>{value || "未命名候选"}</span>
        </Space>
      ),
    },
    {
      title: "类型",
      dataIndex: "candidate_type",
      key: "candidate_type",
      width: 140,
      render: (value: "ku" | "wiki", record: CandidateActionRow) => (
        <Select
          style={{ width: 110 }}
          value={value}
          options={[
            { label: "KU", value: "ku" },
            { label: "Wiki", value: "wiki" },
          ]}
          onChange={(next) => updateCandidate(record.temp_id, { candidate_type: next })}
        />
      ),
    },
    {
      title: "知识类型",
      dataIndex: "knowledge_type",
      key: "knowledge_type",
      width: 140,
      render: (value: string | null | undefined, record: CandidateActionRow) => (
        <Select
          allowClear
          style={{ width: 120 }}
          options={KNOWLEDGE_TYPE_OPTIONS}
          value={value ?? undefined}
          onChange={(next) => updateCandidate(record.temp_id, { knowledge_type: next ?? null })}
        />
      ),
    },
    {
      title: "产品分类",
      dataIndex: "product_category_ids",
      key: "product_category_ids",
      width: 180,
      render: (value: string[] | undefined, record: CandidateActionRow) => (
        <Select
          mode="multiple"
          allowClear
          style={{ width: 160 }}
          options={categoryOptions}
          value={value ?? []}
          onChange={(next) => updateCandidate(record.temp_id, { product_category_ids: next })}
        />
      ),
    },
    {
      title: "建议来源",
      dataIndex: "suggestion_source",
      key: "suggestion_source",
      width: 100,
      render: (value: string | undefined) => (value ? <Tag>{value}</Tag> : null),
    },
    {
      title: "接受",
      dataIndex: "accepted",
      key: "accepted",
      width: 100,
      render: (value: boolean, record: CandidateActionRow) => (
        <Switch checked={value} size="small" onChange={(next) => updateCandidate(record.temp_id, { accepted: next })} />
      ),
    },
  ];

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }
  if (!parseTaskId) {
    return <Alert message="缺少 parseTaskId" type="error" showIcon />;
  }

  return (
    <Card
      title="解析确认向导"
      extra={
        <Space>
          <Tag color={parseStatus === "parse_ready" ? "warning" : "default"}>{parseStatus || "-"}</Tag>
          <Button onClick={() => navigate("/template-libraries")}>返回模板库</Button>
        </Space>
      }
      style={{ minHeight: "calc(100vh - 120px)" }}
      bodyStyle={{ display: "flex", flexDirection: "column", gap: 16 }}
    >
      <Steps
        current={currentStep}
        items={[
          { title: "模板归类" },
          { title: "章节树编辑" },
          { title: "素材与候选" },
        ]}
      />
      <Spin spinning={loading || submitting}>
        {needsManualReview ? (
          <Alert
            type="warning"
            showIcon
            message="检测到文档标题样式不规范，请在 Step2 完整检查章节层级与父子关系。"
            style={{ marginBottom: 16 }}
          />
        ) : null}

        <Form form={form} layout="vertical">
          {currentStep === 0 ? (
            <>
              <Form.Item name="template_name" label="模板名称" rules={[{ required: true, message: "请输入模板名称" }]}>
                <Input placeholder="请输入模板名称" />
              </Form.Item>
              <Form.Item name="template_type" label="模板类型" rules={[{ required: true, message: "请选择模板类型" }]}>
                <Select options={TEMPLATE_TYPE_OPTIONS} />
              </Form.Item>
              <Form.Item name="product_category_ids" label="快捷产品分类（可选，可批量应用到章节）">
                <Select mode="multiple" allowClear options={categoryOptions} placeholder="可多选产品分类" />
              </Form.Item>
              <Space style={{ marginBottom: 16 }}>
                <Switch checked={createLibraryMode} onChange={setCreateLibraryMode} />
                <Typography.Text>新建模板库</Typography.Text>
              </Space>
              {createLibraryMode ? (
                <>
                  <Form.Item
                    name="create_library_name"
                    label="新模板库名称"
                    rules={[{ required: true, message: "请输入模板库名称" }]}
                  >
                    <Input placeholder="例如：餐补技术标模板库" />
                  </Form.Item>
                  <Form.Item
                    name="create_library_type"
                    label="模板库类型"
                    rules={[{ required: true, message: "请选择模板库类型" }]}
                  >
                    <Select options={LIBRARY_TYPE_OPTIONS} />
                  </Form.Item>
                </>
              ) : (
                <Form.Item name="template_library_id" label="选择模板库（可选）">
                  <Select allowClear options={libraryOptions} placeholder="为空时归入未归类模板" />
                </Form.Item>
              )}
            </>
          ) : null}
        </Form>

        {currentStep === 1 ? (
          <>
            <Space style={{ marginBottom: 12 }}>
              <Button onClick={applyQuickCategoriesToChapters}>将 Step1 快捷分类应用到全部章节</Button>
            </Space>
            <Table
              rowKey="temp_id"
              pagination={false}
              columns={chapterColumns}
              dataSource={chapters}
              locale={{ emptyText: "暂无章节建议" }}
            />
          </>
        ) : null}

        {currentStep === 2 ? (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            <div>
              <Typography.Title level={5}>素材建议</Typography.Title>
              <Table
                rowKey="temp_id"
                pagination={false}
                columns={materialColumns}
                dataSource={materials}
                locale={{ emptyText: "暂无素材建议" }}
              />
            </div>
            <div>
              <Typography.Title level={5}>候选占位建议</Typography.Title>
              <Table
                rowKey="temp_id"
                pagination={false}
                columns={candidateColumns}
                dataSource={candidateActions}
                locale={{ emptyText: "暂无候选建议" }}
              />
            </div>
          </Space>
        ) : null}
      </Spin>

      <Space>
        <Button disabled={currentStep === 0} onClick={() => setCurrentStep((step) => Math.max(step - 1, 0))}>
          上一步
        </Button>
        {currentStep < 2 ? (
          <Button
            type="primary"
            disabled={currentStep === 0 && !step1Valid}
            onClick={() => setCurrentStep((step) => Math.min(step + 1, 2))}
          >
            下一步
          </Button>
        ) : (
          <Button type="primary" loading={submitting} onClick={() => void handleConfirm()}>
            确认解析结果
          </Button>
        )}
      </Space>
    </Card>
  );
}
