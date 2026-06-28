import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BOOLEAN_OPTIONS, getEnumLabel, getEnumOptions, getFieldLabel } from "../../constants/knowledgeChunkMeta";
import { useKBContext } from "../../layout/KBContext";
import {
  generateWritingTechnique,
  getWritingTechniqueBySource,
} from "../../services/writingTechniques";
import {
  deleteKnowledgeChunk,
  indexKnowledgeChunk,
  listKnowledgeChunks,
  parseChunkSearchQuery,
  searchKnowledgeChunks,
  waitForChunkIndexComplete,
  type KnowledgeChunkListItem,
  type KnowledgeChunkSearchItem,
  type ListKnowledgeChunksParams,
} from "../../services/knowledgeChunks";
import KnowledgeChunkDetailDrawer from "./KnowledgeChunkDetailDrawer";

interface FilterFormValues {
  category?: string;
  knowledge_type?: string;
  source_type?: string;
  status?: string;
  products?: string[];
  industries?: string[];
  regions?: string[];
  tags?: string[];
  security_level?: string;
  is_template?: "true" | "false";
  winning_flag?: "true" | "false";
  review_status?: string;
  issue_date_from?: string;
  issue_date_to?: string;
  expire_date_from?: string;
  expire_date_to?: string;
  keyword?: string;
}

interface FilterPreset {
  name: string;
  filters: ListKnowledgeChunksParams;
}

function normalizeText(value?: string): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function toListParams(values: FilterFormValues): ListKnowledgeChunksParams {
  return {
    category: normalizeText(values.category),
    knowledge_type: normalizeText(values.knowledge_type),
    source_type: normalizeText(values.source_type),
    status: normalizeText(values.status),
    products: values.products?.length ? values.products : undefined,
    industries: values.industries?.length ? values.industries : undefined,
    regions: values.regions?.length ? values.regions : undefined,
    tags: values.tags?.length ? values.tags : undefined,
    security_level: normalizeText(values.security_level),
    is_template:
      values.is_template === undefined ? undefined : values.is_template === "true",
    winning_flag:
      values.winning_flag === undefined ? undefined : values.winning_flag === "true",
    review_status: normalizeText(values.review_status),
    issue_date_from: normalizeText(values.issue_date_from),
    issue_date_to: normalizeText(values.issue_date_to),
    expire_date_from: normalizeText(values.expire_date_from),
    expire_date_to: normalizeText(values.expire_date_to),
    keyword: normalizeText(values.keyword),
  };
}

function fromListParams(params: ListKnowledgeChunksParams): FilterFormValues {
  return {
    category: params.category,
    knowledge_type: params.knowledge_type,
    source_type: params.source_type,
    status: params.status,
    products: params.products,
    industries: params.industries,
    regions: params.regions,
    tags: params.tags,
    security_level: params.security_level,
    is_template:
      params.is_template === undefined ? undefined : params.is_template ? "true" : "false",
    winning_flag:
      params.winning_flag === undefined ? undefined : params.winning_flag ? "true" : "false",
    review_status: params.review_status,
    issue_date_from: params.issue_date_from,
    issue_date_to: params.issue_date_to,
    expire_date_from: params.expire_date_from,
    expire_date_to: params.expire_date_to,
    keyword: params.keyword,
  };
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function filterPresetStorageKey(kbId: string) {
  return `knowledge-filters:${kbId}`;
}

function loadPresets(kbId: string): FilterPreset[] {
  try {
    const raw = localStorage.getItem(filterPresetStorageKey(kbId));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((item) => item && typeof item === "object")
      .map((item) => {
        const candidate = item as { name?: unknown; filters?: unknown };
        return {
          name: typeof candidate.name === "string" ? candidate.name : "",
          filters:
            candidate.filters && typeof candidate.filters === "object"
              ? (candidate.filters as ListKnowledgeChunksParams)
              : {},
        };
      })
      .filter((item) => item.name);
  } catch {
    return [];
  }
}

function savePresets(kbId: string, presets: FilterPreset[]) {
  localStorage.setItem(filterPresetStorageKey(kbId), JSON.stringify(presets));
}

export default function KnowledgeBrowsePage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [form] = Form.useForm<FilterFormValues>();
  const [filters, setFilters] = useState<ListKnowledgeChunksParams>({});
  const [items, setItems] = useState<KnowledgeChunkListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [detailChunkId, setDetailChunkId] = useState<number>();
  const [detailReloadKey, setDetailReloadKey] = useState(0);
  const [presets, setPresets] = useState<FilterPreset[]>([]);
  const [selectedPresetName, setSelectedPresetName] = useState<string>();
  const [savePresetOpen, setSavePresetOpen] = useState(false);
  const [presetNameInput, setPresetNameInput] = useState("");
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticQuery, setSemanticQuery] = useState("");
  const [searchItems, setSearchItems] = useState<KnowledgeChunkSearchItem[]>([]);
  const [indexingId, setIndexingId] = useState<number>();
  const [generatingTechniqueId, setGeneratingTechniqueId] = useState<number>();
  const [techniqueByChunkId, setTechniqueByChunkId] = useState<Record<number, string | null>>({});
  const [deletingId, setDeletingId] = useState<number>();

  useEffect(() => {
    if (!selectedKbId) {
      setPresets([]);
      setSelectedPresetName(undefined);
      return;
    }
    setPresets(loadPresets(selectedKbId));
    setSelectedPresetName(undefined);
  }, [selectedKbId]);

  const refreshList = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listKnowledgeChunks(selectedKbId, {
        ...filters,
        page,
        page_size: pageSize,
      });
      setItems(result.items ?? []);
      setTotal(result.total ?? 0);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, selectedKbId]);

  useEffect(() => {
    if (!semanticMode) {
      void refreshList();
    }
  }, [refreshList, semanticMode]);

  const applyFilters = useCallback(() => {
    const values = form.getFieldsValue();
    setFilters(toListParams(values));
    setPage(1);
    setSemanticMode(false);
    setSearchItems([]);
  }, [form]);

  const resetFilters = useCallback(() => {
    form.resetFields();
    setFilters({});
    setPage(1);
    setSelectedPresetName(undefined);
    setSemanticMode(false);
    setSearchItems([]);
  }, [form]);

  const handleSemanticSearch = useCallback(async () => {
    if (!selectedKbId || !semanticQuery.trim()) {
      return;
    }
    setLoading(true);
    try {
      const parsed = await parseChunkSearchQuery(selectedKbId, {
        query: semanticQuery.trim(),
      });
      const result = await searchKnowledgeChunks(selectedKbId, {
        ...parsed,
        vector_weight: 0.6,
        keyword_weight: 0.4,
        top_k: 10,
      });
      setSearchItems(result.items ?? []);
      setSemanticMode(true);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selectedKbId, semanticQuery]);

  const handleExitSemanticSearch = useCallback(() => {
    setSemanticMode(false);
    setSearchItems([]);
    void refreshList();
  }, [refreshList]);

  const refreshTechniqueBindings = useCallback(
    async (chunkIds: number[]) => {
      if (!selectedKbId || !chunkIds.length) {
        setTechniqueByChunkId({});
        return;
      }
      try {
        const pairs = await Promise.all(
          chunkIds.map(async (chunkId) => {
            const detail = await getWritingTechniqueBySource(selectedKbId, { chunk_id: chunkId });
            return [chunkId, detail?.technique_id ?? null] as const;
          }),
        );
        setTechniqueByChunkId(Object.fromEntries(pairs));
      } catch {
        // 不影响主流程：技巧映射失败时仅退化为“生成技巧”按钮
      }
    },
    [selectedKbId],
  );

  useEffect(() => {
    if (semanticMode) {
      setTechniqueByChunkId({});
      return;
    }
    void refreshTechniqueBindings(items.map((item) => item.id));
  }, [items, refreshTechniqueBindings, semanticMode]);

  const submitGenerateWritingTechnique = useCallback(
    async (chunkId: number, confirmOverwrite: boolean) => {
      if (!selectedKbId) return;
      setGeneratingTechniqueId(chunkId);
      try {
        const result = await generateWritingTechnique(selectedKbId, {
          chunk_id: chunkId,
          confirm_overwrite: confirmOverwrite,
        });
        setTechniqueByChunkId((prev) => ({ ...prev, [chunkId]: result.technique_id }));
        message.success(confirmOverwrite ? "撰写技巧已重新生成" : "撰写技巧生成成功");
      } finally {
        setGeneratingTechniqueId(undefined);
      }
    },
    [selectedKbId],
  );

  const handleGenerateWritingTechnique = useCallback(
    (chunkId: number) => {
      const hasExisting = Boolean(techniqueByChunkId[chunkId]);
      const triggerGenerate = async (confirmOverwrite: boolean) => {
        try {
          await submitGenerateWritingTechnique(chunkId, confirmOverwrite);
        } catch (error) {
          message.error((error as Error).message);
        }
      };
      if (hasExisting) {
        Modal.confirm({
          title: "确认重新生成撰写技巧？",
          content: "重新生成会覆盖该来源已有技巧内容。",
          okText: "重新生成",
          cancelText: "取消",
          onOk: async () => {
            await triggerGenerate(true);
          },
        });
        return;
      }
      void triggerGenerate(false);
    },
    [submitGenerateWritingTechnique, techniqueByChunkId],
  );

  const updateChunkEmbeddingStatus = useCallback((chunkId: number, embeddingStatus: string) => {
    if (semanticMode) {
      setSearchItems((prev) =>
        prev.map((item) => (item.id === chunkId ? { ...item, embedding_status: embeddingStatus } : item)),
      );
    } else {
      setItems((prev) =>
        prev.map((item) => (item.id === chunkId ? { ...item, embedding_status: embeddingStatus } : item)),
      );
    }
  }, [semanticMode]);

  const handleIndexChunk = useCallback(
    async (chunkId: number) => {
      if (!selectedKbId) {
        return;
      }
      setIndexingId(chunkId);
      try {
        await indexKnowledgeChunk(selectedKbId, chunkId);
        updateChunkEmbeddingStatus(chunkId, "indexing");
        const detail = await waitForChunkIndexComplete(selectedKbId, chunkId);
        const status = detail?.embedding_status ?? "failed";
        updateChunkEmbeddingStatus(chunkId, status);
        if (status === "ready") {
          message.success("索引构建完成");
        } else if (status === "skipped") {
          message.warning("索引已跳过（未配置向量服务）");
        } else if (status === "failed") {
          message.error("索引构建失败");
        } else if (status === "indexing") {
          message.info("索引仍在进行中，请稍后刷新查看");
        }
        if (detailChunkId === chunkId) {
          setDetailReloadKey((key) => key + 1);
        }
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setIndexingId(undefined);
      }
    },
    [detailChunkId, selectedKbId, updateChunkEmbeddingStatus],
  );

  const handleDeleteChunk = useCallback(
    async (chunkId: number) => {
      if (!selectedKbId) {
        return;
      }
      setDeletingId(chunkId);
      try {
        await deleteKnowledgeChunk(selectedKbId, chunkId);
        message.success("知识已删除");
        if (detailChunkId === chunkId) {
          setDetailChunkId(undefined);
        }
        if (semanticMode) {
          setSearchItems((prev) => prev.filter((item) => item.id !== chunkId));
        } else {
          await refreshList();
        }
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setDeletingId(undefined);
      }
    },
    [detailChunkId, refreshList, selectedKbId, semanticMode],
  );

  const handlePresetSave = useCallback(() => {
    if (!selectedKbId) {
      return;
    }
    const name = presetNameInput.trim();
    if (!name) {
      message.warning("请输入筛选方案名称");
      return;
    }
    const values = form.getFieldsValue();
    const nextFilter = toListParams(values);
    const nextPresets = [...presets];
    const index = nextPresets.findIndex((item) => item.name === name);
    const preset: FilterPreset = { name, filters: nextFilter };
    if (index >= 0) {
      nextPresets[index] = preset;
    } else {
      nextPresets.push(preset);
    }
    setPresets(nextPresets);
    setSelectedPresetName(name);
    savePresets(selectedKbId, nextPresets);
    setSavePresetOpen(false);
    setPresetNameInput("");
    message.success("筛选方案已保存");
  }, [form, presetNameInput, presets, selectedKbId]);

  const applyPreset = useCallback(
    (name?: string) => {
      if (!name) {
        setSelectedPresetName(undefined);
        return;
      }
      const target = presets.find((item) => item.name === name);
      if (!target) {
        message.warning("筛选方案不存在");
        return;
      }
      form.setFieldsValue(fromListParams(target.filters));
      setFilters(target.filters);
      setPage(1);
      setSelectedPresetName(name);
    },
    [form, presets],
  );

  const deletePreset = useCallback(
    (name?: string) => {
      if (!selectedKbId || !name) {
        return;
      }
      const nextPresets = presets.filter((item) => item.name !== name);
      setPresets(nextPresets);
      savePresets(selectedKbId, nextPresets);
      setSelectedPresetName(undefined);
      message.success("筛选方案已删除");
    },
    [presets, selectedKbId],
  );

  const baseColumns: ColumnsType<KnowledgeChunkListItem> = useMemo(
    () => [
      {
        title: getFieldLabel("title"),
        dataIndex: "title",
        key: "title",
        width: 280,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            style={{ padding: 0, whiteSpace: "nowrap" }}
            onClick={() => setDetailChunkId(record.id)}
          >
            {record.title || "-"}
          </Button>
        ),
      },
      {
        title: getFieldLabel("version"),
        dataIndex: "version",
        key: "version",
        width: 120,
      },
      {
        title: getFieldLabel("category"),
        dataIndex: "category",
        key: "category",
        width: 140,
        render: (value: string) => getEnumLabel("category", value) || "-",
      },
      {
        title: getFieldLabel("knowledge_type"),
        dataIndex: "knowledge_type",
        key: "knowledge_type",
        width: 160,
        render: (value: string) => <Tag>{getEnumLabel("knowledge_type", value)}</Tag>,
      },
      {
        title: getFieldLabel("status"),
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value: string) => <Tag>{getEnumLabel("status", value)}</Tag>,
      },
      {
        title: getFieldLabel("embedding_status"),
        dataIndex: "embedding_status",
        key: "embedding_status",
        width: 100,
        render: (value?: string) => (
          <Tag>{getEnumLabel("embedding_status", value ?? "pending")}</Tag>
        ),
      },
      {
        title: getFieldLabel("token_count"),
        dataIndex: "token_count",
        key: "token_count",
        width: 120,
      },
      {
        title: getFieldLabel("update_time"),
        dataIndex: "update_time",
        key: "update_time",
        width: 190,
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 300,
        fixed: "right" as const,
        render: (_value, record) => {
          const indexing = record.embedding_status === "indexing";
          const ready = record.embedding_status === "ready";
          const hasTechnique = Boolean(techniqueByChunkId[record.id]);
          return (
            <Space size={4}>
              <Button
                size="small"
                loading={indexingId === record.id || indexing}
                disabled={indexing}
                onClick={() => void handleIndexChunk(record.id)}
              >
                {ready ? "重新索引" : "构建索引"}
              </Button>
              <Button
                size="small"
                loading={generatingTechniqueId === record.id}
                disabled={readOnly}
                onClick={() => handleGenerateWritingTechnique(record.id)}
              >
                {hasTechnique ? "重新生成技巧" : "生成技巧"}
              </Button>
              <Popconfirm
                title="确认删除该知识吗？"
                okText="删除"
                cancelText="取消"
                onConfirm={() => void handleDeleteChunk(record.id)}
                disabled={readOnly}
              >
                <Button
                  danger
                  size="small"
                  loading={deletingId === record.id}
                  disabled={readOnly}
                >
                  删除
                </Button>
              </Popconfirm>
            </Space>
          );
        },
      },
    ],
    [
      deletingId,
      generatingTechniqueId,
      handleDeleteChunk,
      handleGenerateWritingTechnique,
      handleIndexChunk,
      indexingId,
      readOnly,
      techniqueByChunkId,
    ],
  );

  const semanticColumns = useMemo((): ColumnsType<KnowledgeChunkSearchItem> => {
    const titleColumn = baseColumns[0] as ColumnsType<KnowledgeChunkSearchItem>[number];
    const restColumns = baseColumns
      .slice(1)
      .filter((col) => col.key !== "embedding_status") as ColumnsType<KnowledgeChunkSearchItem>;
    return [
      titleColumn,
      {
        title: "匹配分",
        dataIndex: "score",
        key: "score",
        width: 88,
        align: "center",
        render: (value: number) => value.toFixed(2),
      },
      {
        title: "匹配摘要",
        key: "highlight",
        width: 220,
        ellipsis: true,
        render: (_value, record) => {
          const snippet = record.highlights?.[0]?.snippet;
          if (!snippet) {
            return record.summary || "-";
          }
          return <span dangerouslySetInnerHTML={{ __html: snippet }} />;
        },
      },
      ...restColumns,
    ];
  }, [baseColumns]);

  const tablePagination = semanticMode
    ? false
    : {
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        showTotal: (count: number) => `共 ${count} 条`,
        onChange: (nextPage: number, nextPageSize: number) => {
          setPage(nextPage);
          setPageSize(nextPageSize);
        },
      };

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card title="知识浏览">
        <Space style={{ width: "100%", marginBottom: 16 }} wrap>
          <Input
            style={{ minWidth: 360 }}
            value={semanticQuery}
            onChange={(event) => setSemanticQuery(event.target.value)}
            placeholder="用自然语言描述，如：餐饮行业的食品经营许可证要求"
            allowClear
            onPressEnter={() => void handleSemanticSearch()}
          />
          <Button type="primary" onClick={() => void handleSemanticSearch()} loading={loading}>
            语义搜索
          </Button>
          {semanticMode ? <Button onClick={handleExitSemanticSearch}>返回列表</Button> : null}
        </Space>

        <Form form={form} layout="vertical">
          <Row gutter={12} align="middle">
            <Col flex="1 1 160px">
              <Form.Item name="category" label={getFieldLabel("category")}>
                <Select allowClear options={getEnumOptions("category")} />
              </Form.Item>
            </Col>
            <Col flex="1 1 160px">
              <Form.Item name="knowledge_type" label={getFieldLabel("knowledge_type")}>
                <Select allowClear options={getEnumOptions("knowledge_type")} />
              </Form.Item>
            </Col>
            <Col flex="1 1 160px">
              <Form.Item name="status" label={getFieldLabel("status")}>
                <Select allowClear options={getEnumOptions("status")} />
              </Form.Item>
            </Col>
            <Col flex="2 1 220px">
              <Form.Item name="keyword" label={getFieldLabel("keyword")}>
                <Input allowClear placeholder="匹配 title/summary" />
              </Form.Item>
            </Col>
            <Col flex="0 0 auto">
              <Space style={{ marginBottom: 24 }}>
                <Button type="primary" onClick={applyFilters}>
                  查询
                </Button>
                <Button onClick={resetFilters}>重置</Button>
                <Button type="link" onClick={() => setFiltersExpanded((value) => !value)}>
                  {filtersExpanded ? "收起筛选" : "展开更多筛选"}
                </Button>
              </Space>
            </Col>
          </Row>

          {filtersExpanded ? (
            <>
              <Row gutter={12}>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="source_type" label={getFieldLabel("source_type")}>
                    <Select allowClear options={getEnumOptions("source_type")} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="products" label={getFieldLabel("products")}>
                    <Select mode="tags" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="industries" label={getFieldLabel("industries")}>
                    <Select mode="tags" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="regions" label={getFieldLabel("regions")}>
                    <Select mode="tags" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="tags" label={getFieldLabel("tags")}>
                    <Select mode="tags" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="security_level" label={getFieldLabel("security_level")}>
                    <Select allowClear options={getEnumOptions("security_level")} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="is_template" label={getFieldLabel("is_template")}>
                    <Select allowClear options={[...BOOLEAN_OPTIONS]} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="winning_flag" label={getFieldLabel("winning_flag")}>
                    <Select allowClear options={[...BOOLEAN_OPTIONS]} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="review_status" label={getFieldLabel("review_status")}>
                    <Select allowClear options={getEnumOptions("review_status")} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="issue_date_from" label={getFieldLabel("issue_date_from")}>
                    <Input placeholder="YYYY-MM-DD" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="issue_date_to" label={getFieldLabel("issue_date_to")}>
                    <Input placeholder="YYYY-MM-DD" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="expire_date_from" label={getFieldLabel("expire_date_from")}>
                    <Input placeholder="YYYY-MM-DD" allowClear />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item name="expire_date_to" label={getFieldLabel("expire_date_to")}>
                    <Input placeholder="YYYY-MM-DD" allowClear />
                  </Form.Item>
                </Col>
              </Row>
              <Space style={{ marginBottom: 16 }}>
                <Select
                  allowClear
                  placeholder="筛选方案"
                  style={{ width: 220 }}
                  value={selectedPresetName}
                  options={presets.map((item) => ({ label: item.name, value: item.name }))}
                  onChange={(value) => applyPreset(value)}
                />
                <Button onClick={() => setSavePresetOpen(true)}>保存方案</Button>
                <Popconfirm
                  title="确认删除当前筛选方案？"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => deletePreset(selectedPresetName)}
                  disabled={!selectedPresetName}
                >
                  <Button disabled={!selectedPresetName}>删除方案</Button>
                </Popconfirm>
              </Space>
            </>
          ) : null}
        </Form>

        <div style={{ marginBottom: 16 }} />

        {semanticMode ? (
          <Table
            rowKey="id"
            size="small"
            loading={loading}
            columns={semanticColumns}
            dataSource={searchItems}
            scroll={{ x: "max-content" }}
            locale={{ emptyText: <Empty description="暂无匹配知识" /> }}
            pagination={false}
          />
        ) : (
          <Table
            rowKey="id"
            size="small"
            loading={loading}
            columns={baseColumns}
            dataSource={items}
            scroll={{ x: "max-content" }}
            locale={{ emptyText: <Empty description="暂无知识记录" /> }}
            pagination={tablePagination}
          />
        )}
      </Card>

      <KnowledgeChunkDetailDrawer
        kbId={selectedKbId}
        chunkId={detailChunkId}
        reloadKey={detailReloadKey}
        open={detailChunkId !== undefined}
        onClose={() => setDetailChunkId(undefined)}
        onOpenChunk={(nextChunkId) => setDetailChunkId(nextChunkId)}
      />

      <Modal
        title="保存筛选方案"
        open={savePresetOpen}
        onOk={handlePresetSave}
        onCancel={() => {
          setSavePresetOpen(false);
          setPresetNameInput("");
        }}
        okText="保存"
        cancelText="取消"
      >
        <Input
          placeholder="请输入方案名称"
          value={presetNameInput}
          onChange={(event) => setPresetNameInput(event.target.value)}
          onPressEnter={handlePresetSave}
        />
      </Modal>
    </>
  );
}
