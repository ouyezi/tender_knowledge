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
  listKnowledgeChunks,
  type KnowledgeChunkListItem,
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
  const { selectedKbId } = useKBContext();
  const [form] = Form.useForm<FilterFormValues>();
  const [filters, setFilters] = useState<ListKnowledgeChunksParams>({});
  const [items, setItems] = useState<KnowledgeChunkListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [detailChunkId, setDetailChunkId] = useState<number>();
  const [presets, setPresets] = useState<FilterPreset[]>([]);
  const [selectedPresetName, setSelectedPresetName] = useState<string>();
  const [savePresetOpen, setSavePresetOpen] = useState(false);
  const [presetNameInput, setPresetNameInput] = useState("");
  const [filtersExpanded, setFiltersExpanded] = useState(false);

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
    void refreshList();
  }, [refreshList]);

  const applyFilters = useCallback(() => {
    const values = form.getFieldsValue();
    setFilters(toListParams(values));
    setPage(1);
  }, [form]);

  const resetFilters = useCallback(() => {
    form.resetFields();
    setFilters({});
    setPage(1);
    setSelectedPresetName(undefined);
  }, [form]);

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

  const columns: ColumnsType<KnowledgeChunkListItem> = useMemo(
    () => [
      {
        title: getFieldLabel("title"),
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        render: (_value, record) => (
          <Button type="link" size="small" onClick={() => setDetailChunkId(record.id)}>
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
        width: 140,
        render: (value: string) => <Tag>{getEnumLabel("status", value)}</Tag>,
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
    ],
    [],
  );

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card title="知识浏览">
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

        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          locale={{ emptyText: <Empty description="暂无知识记录" /> }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (count) => `共 ${count} 条`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>

      <KnowledgeChunkDetailDrawer
        kbId={selectedKbId}
        chunkId={detailChunkId}
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
