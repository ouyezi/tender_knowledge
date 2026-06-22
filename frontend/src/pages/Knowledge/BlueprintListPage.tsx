import { Alert, Button, Card, Form, Input, Popconfirm, Select, Space, Table, Tag, Tooltip, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import {
  deleteBlueprint,
  listBlueprints,
  parseBlueprintSearchQuery,
  searchBlueprints,
  type BlueprintListItem,
  type BlueprintSearchItem,
  type ListBlueprintsParams,
} from "../../services/blueprints";

interface FilterFormValues {
  keyword?: string;
  product_tags?: string[];
  industry_tags?: string[];
  scenario_tags?: string[];
}

function normalizeText(value?: string): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function toListParams(values: FilterFormValues): ListBlueprintsParams {
  return {
    keyword: normalizeText(values.keyword),
    product_tags: values.product_tags?.length ? values.product_tags : undefined,
    industry_tags: values.industry_tags?.length ? values.industry_tags : undefined,
    scenario_tags: values.scenario_tags?.length ? values.scenario_tags : undefined,
  };
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

const SMALL_TAG_STYLE: CSSProperties = {
  fontSize: 12,
  lineHeight: "18px",
  paddingInline: 4,
};

const EMBEDDING_STATUS_LABEL: Record<string, string> = {
  pending: "待处理",
  ready: "已完成",
  failed: "失败",
  skipped: "跳过",
};

function renderTags(tags?: string[]) {
  if (!tags?.length) {
    return "-";
  }
  return (
    <Space size={[4, 4]} wrap>
      {tags.map((tag) => (
        <Tag key={tag} style={SMALL_TAG_STYLE}>
          {tag}
        </Tag>
      ))}
    </Space>
  );
}

function formatScoreDetail(item: BlueprintSearchItem): string {
  const detail = item.score_detail;
  return [
    `综合分 ${item.score.toFixed(2)}`,
    `向量 ${detail.vector_score.toFixed(2)} (权重 ${detail.vector_weight})`,
    `关键词 ${detail.keyword_score.toFixed(2)} (权重 ${detail.keyword_weight})`,
  ].join("\n");
}

export default function BlueprintListPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [form] = Form.useForm<FilterFormValues>();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ListBlueprintsParams>({});
  const [items, setItems] = useState<BlueprintListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticQuery, setSemanticQuery] = useState("");
  const [searchItems, setSearchItems] = useState<BlueprintSearchItem[]>([]);

  const refreshList = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listBlueprints(selectedKbId, {
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
    setSemanticMode(false);
    setSearchItems([]);
  }, [form]);

  const handleSemanticSearch = useCallback(async () => {
    if (!selectedKbId || !semanticQuery.trim()) {
      return;
    }
    setLoading(true);
    try {
      const parsed = await parseBlueprintSearchQuery(selectedKbId, {
        query: semanticQuery.trim(),
      });
      const result = await searchBlueprints(selectedKbId, {
        ...parsed,
        vector_weight: 0.6,
        keyword_weight: 0.4,
        top_k: 10,
      });
      setSearchItems(result.items);
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

  const handleDelete = useCallback(
    async (blueprintId: string) => {
      if (!selectedKbId) {
        return;
      }
      setDeletingId(blueprintId);
      try {
        await deleteBlueprint(selectedKbId, blueprintId);
        message.success("目录蓝图已删除");
        if (semanticMode) {
          setSearchItems((prev) => prev.filter((item) => item.blueprint_id !== blueprintId));
        } else {
          await refreshList();
        }
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setDeletingId(undefined);
      }
    },
    [refreshList, selectedKbId, semanticMode],
  );

  const baseColumns: ColumnsType<BlueprintListItem> = useMemo(
    () => [
      {
        title: "蓝图名称",
        dataIndex: "name",
        key: "name",
        width: 260,
        ellipsis: true,
        render: (_value, record) => (
          <Tooltip title={record.name || "-"}>
            <Button
              type="link"
              size="small"
              style={{
                maxWidth: "100%",
                padding: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "inline-block",
                verticalAlign: "bottom",
              }}
              onClick={() => navigate(`/knowledge/blueprints/${record.blueprint_id}`)}
            >
              {record.name || "-"}
            </Button>
          </Tooltip>
        ),
      },
      {
        title: "来源章节",
        dataIndex: "source_chapter_title",
        key: "source_chapter_title",
        width: 180,
        ellipsis: true,
        render: (value: string | null) => value || "-",
      },
      {
        title: "产品标签",
        dataIndex: "product_tags",
        key: "product_tags",
        width: 140,
        render: (value: string[]) => renderTags(value),
      },
      {
        title: "行业标签",
        dataIndex: "industry_tags",
        key: "industry_tags",
        width: 140,
        render: (value: string[]) => renderTags(value),
      },
      {
        title: "场景标签",
        dataIndex: "scenario_tags",
        key: "scenario_tags",
        width: 140,
        render: (value: string[]) => renderTags(value),
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 80,
        render: (value: string) => <Tag style={SMALL_TAG_STYLE}>{value || "-"}</Tag>,
      },
      {
        title: "向量状态",
        dataIndex: "embedding_status",
        key: "embedding_status",
        width: 88,
        render: (value?: string) => (
          <Tag style={SMALL_TAG_STYLE}>{EMBEDDING_STATUS_LABEL[value ?? "pending"] ?? value ?? "-"}</Tag>
        ),
      },
      {
        title: "版本",
        dataIndex: "version",
        key: "version",
        width: 64,
        align: "center",
      },
      {
        title: "更新时间",
        dataIndex: "updated_at",
        key: "updated_at",
        width: 180,
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 90,
        render: (_value, record) => (
          <Popconfirm
            title="确认删除该目录蓝图吗？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(record.blueprint_id)}
            disabled={readOnly}
          >
            <Button
              danger
              size="small"
              loading={deletingId === record.blueprint_id}
              disabled={readOnly}
            >
              删除
            </Button>
          </Popconfirm>
        ),
      },
    ],
    [deletingId, handleDelete, navigate, readOnly],
  );

  const semanticColumns = useMemo((): ColumnsType<BlueprintSearchItem> => {
    const nameColumn = baseColumns[0] as ColumnsType<BlueprintSearchItem>[number];
    const restColumns = baseColumns
      .slice(1)
      .filter((col) => col.key !== "embedding_status") as ColumnsType<BlueprintSearchItem>;
    return [
      nameColumn,
      {
        title: "匹配分",
        dataIndex: "score",
        key: "score",
        width: 88,
        align: "center",
        render: (value: number, record) => (
          <Tooltip title={<span style={{ whiteSpace: "pre-line" }}>{formatScoreDetail(record)}</span>}>
            <span>{value.toFixed(2)}</span>
          </Tooltip>
        ),
      },
      {
        title: "匹配摘要",
        key: "highlight",
        width: 220,
        ellipsis: true,
        render: (_value, record) => {
          const snippet = record.highlights?.[0]?.snippet;
          if (!snippet) {
            return "-";
          }
          return <span dangerouslySetInnerHTML={{ __html: snippet }} />;
        },
      },
      ...restColumns,
    ];
  }, [baseColumns]);

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <Card title="目录蓝图">
      <Space style={{ width: "100%", marginBottom: 16 }} wrap>
        <Input
          style={{ minWidth: 360 }}
          value={semanticQuery}
          onChange={(event) => setSemanticQuery(event.target.value)}
          placeholder="用自然语言描述，如：政务云技术架构章节的正式风格蓝图"
          allowClear
          onPressEnter={() => void handleSemanticSearch()}
        />
        <Button type="primary" onClick={() => void handleSemanticSearch()} loading={loading}>
          语义搜索
        </Button>
        {semanticMode ? <Button onClick={handleExitSemanticSearch}>返回列表</Button> : null}
      </Space>

      <Form form={form} layout="vertical">
        <Space style={{ width: "100%" }} align="end" wrap>
          <Form.Item name="keyword" label="关键词" style={{ minWidth: 240, marginBottom: 12 }}>
            <Input allowClear placeholder="匹配蓝图名称/描述/来源章节" />
          </Form.Item>
          <Form.Item name="product_tags" label="产品标签" style={{ minWidth: 220, marginBottom: 12 }}>
            <Select mode="tags" allowClear />
          </Form.Item>
          <Form.Item name="industry_tags" label="行业标签" style={{ minWidth: 220, marginBottom: 12 }}>
            <Select mode="tags" allowClear />
          </Form.Item>
          <Form.Item name="scenario_tags" label="场景标签" style={{ minWidth: 220, marginBottom: 12 }}>
            <Select mode="tags" allowClear />
          </Form.Item>
          <Space style={{ marginBottom: 12 }}>
            <Button type="primary" onClick={applyFilters}>
              查询
            </Button>
            <Button onClick={resetFilters}>重置</Button>
          </Space>
        </Space>
      </Form>

      <Table
        rowKey="blueprint_id"
        size="small"
        loading={loading}
        columns={(semanticMode ? semanticColumns : baseColumns) as ColumnsType<BlueprintListItem>}
        dataSource={semanticMode ? searchItems : items}
        locale={{
          emptyText: semanticMode ? "未找到匹配的目录蓝图" : undefined,
        }}
        pagination={
          semanticMode
            ? false
            : {
                current: page,
                pageSize,
                total,
                showSizeChanger: true,
                showTotal: (count) => `共 ${count} 条`,
                onChange: (nextPage, nextPageSize) => {
                  setPage(nextPage);
                  setPageSize(nextPageSize);
                },
              }
        }
      />
    </Card>
  );
}
