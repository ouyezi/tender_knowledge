import { Alert, Button, Card, Form, Input, Popconfirm, Select, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ConfidenceBadge from "../../components/WritingTechnique/ConfidenceBadge";
import { useKBContext } from "../../layout/KBContext";
import {
  deleteWritingTechnique,
  listWritingTechniques,
  type ListWritingTechniquesParams,
  type WritingTechniqueItem,
  type WritingTechniqueStatus,
  type WritingTechniqueUsageMode,
} from "../../services/writingTechniques";

interface FilterFormValues {
  keyword?: string;
  tags?: string[];
  applicable_sections?: string[];
  usage_mode?: WritingTechniqueUsageMode;
  status?: WritingTechniqueStatus;
  source_invalid?: "true" | "false";
  has_source?: "true" | "false";
  confidence_min?: number;
  confidence_max?: number;
}

const USAGE_MODE_LABEL: Record<WritingTechniqueUsageMode, string> = {
  DIRECT: "直接套用",
  REFERENCE: "参考改写",
  EXTRACT: "要点提炼",
};

const STATUS_LABEL: Record<WritingTechniqueStatus, string> = {
  draft: "草稿",
  published: "已发布",
};

function normalizeText(value?: string): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function toListParams(values: FilterFormValues): ListWritingTechniquesParams {
  return {
    keyword: normalizeText(values.keyword),
    tags: values.tags?.length ? values.tags : undefined,
    applicable_sections: values.applicable_sections?.length ? values.applicable_sections : undefined,
    usage_mode: values.usage_mode,
    status: values.status,
    source_invalid:
      values.source_invalid === undefined ? undefined : values.source_invalid === "true",
    has_source: values.has_source === undefined ? undefined : values.has_source === "true",
    confidence_min: values.confidence_min,
    confidence_max: values.confidence_max,
  };
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function WritingTechniqueListPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const [form] = Form.useForm<FilterFormValues>();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ListWritingTechniquesParams>({});
  const [items, setItems] = useState<WritingTechniqueItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const refreshList = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listWritingTechniques(selectedKbId, {
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
  }, [form]);

  const handleDelete = useCallback(
    async (techniqueId: string) => {
      if (!selectedKbId) {
        return;
      }
      setDeletingId(techniqueId);
      try {
        await deleteWritingTechnique(selectedKbId, techniqueId);
        message.success("撰写技巧已删除");
        await refreshList();
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setDeletingId(undefined);
      }
    },
    [refreshList, selectedKbId],
  );

  const columns: ColumnsType<WritingTechniqueItem> = useMemo(
    () => [
      {
        title: "技巧标题",
        dataIndex: "title",
        key: "title",
        width: 260,
        ellipsis: true,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => navigate(`/knowledge/writing-techniques/${record.technique_id}`)}
          >
            {record.title || "-"}
          </Button>
        ),
      },
      {
        title: "使用方式",
        dataIndex: "usage_mode",
        key: "usage_mode",
        width: 96,
        render: (value: WritingTechniqueUsageMode) => <Tag>{USAGE_MODE_LABEL[value] ?? value}</Tag>,
      },
      {
        title: "适用章节",
        dataIndex: "applicable_sections",
        key: "applicable_sections",
        width: 170,
        render: (value: string[]) => (value?.length ? value.join(" / ") : "-"),
      },
      {
        title: "标签",
        dataIndex: "tags",
        key: "tags",
        width: 140,
        render: (value: string[]) =>
          value?.length ? (
            <Space size={[4, 4]} wrap>
              {value.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </Space>
          ) : (
            "-"
          ),
      },
      {
        title: "置信度",
        dataIndex: "confidence",
        key: "confidence",
        width: 90,
        align: "center",
        render: (value: number) => <ConfidenceBadge confidence={value} />,
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 90,
        render: (value: WritingTechniqueStatus) => (
          <Tag color={value === "published" ? "green" : "default"}>{STATUS_LABEL[value] ?? value}</Tag>
        ),
      },
      {
        title: "来源 Chunk",
        dataIndex: "source_chunk_id",
        key: "source_chunk_id",
        width: 108,
        align: "right",
        render: (value: number | null) => value ?? "-",
      },
      {
        title: "版本",
        dataIndex: "version",
        key: "version",
        width: 66,
        align: "center",
      },
      {
        title: "更新时间",
        dataIndex: "updated_at",
        key: "updated_at",
        width: 170,
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 90,
        render: (_value, record) => (
          <Popconfirm
            title="确认删除该撰写技巧吗？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(record.technique_id)}
            disabled={readOnly}
          >
            <Button
              danger
              size="small"
              loading={deletingId === record.technique_id}
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

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <Card title="撰写技巧">
      <Form form={form} layout="vertical">
        <Space style={{ width: "100%" }} align="end" wrap>
          <Form.Item name="keyword" label="关键词" style={{ minWidth: 240, marginBottom: 12 }}>
            <Input allowClear placeholder="匹配标题/摘要/策略" />
          </Form.Item>
          <Form.Item name="usage_mode" label="使用方式" style={{ minWidth: 170, marginBottom: 12 }}>
            <Select
              allowClear
              options={Object.entries(USAGE_MODE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="status" label="状态" style={{ minWidth: 140, marginBottom: 12 }}>
            <Select
              allowClear
              options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="tags" label="标签" style={{ minWidth: 220, marginBottom: 12 }}>
            <Select mode="tags" allowClear />
          </Form.Item>
          <Form.Item name="applicable_sections" label="适用章节" style={{ minWidth: 220, marginBottom: 12 }}>
            <Select mode="tags" allowClear />
          </Form.Item>
          <Form.Item name="source_invalid" label="来源失效" style={{ minWidth: 120, marginBottom: 12 }}>
            <Select
              allowClear
              options={[
                { label: "是", value: "true" },
                { label: "否", value: "false" },
              ]}
            />
          </Form.Item>
          <Form.Item name="has_source" label="已绑定来源" style={{ minWidth: 120, marginBottom: 12 }}>
            <Select
              allowClear
              options={[
                { label: "是", value: "true" },
                { label: "否", value: "false" },
              ]}
            />
          </Form.Item>
          <Form.Item name="confidence_min" label="最小置信度" style={{ width: 120, marginBottom: 12 }}>
            <Input type="number" min={0} max={100} />
          </Form.Item>
          <Form.Item name="confidence_max" label="最大置信度" style={{ width: 120, marginBottom: 12 }}>
            <Input type="number" min={0} max={100} />
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
        rowKey="technique_id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={items}
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
  );
}
