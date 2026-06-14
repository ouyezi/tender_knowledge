import { Alert, Button, Card, Empty, Input, Space, Table, Tabs, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useKBContext } from "../../layout/KBContext";
import {
  listKnowledgeUnits,
  listManualAssets,
  listWikis,
  type KnowledgeUnitItem,
  type ManualAssetItem,
  type WikiItem,
} from "../../services/knowledgeAssets";
import KnowledgeDetailDrawer, { type KnowledgeAssetType } from "./KnowledgeDetailDrawer";

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  published: { color: "success", label: "已发布" },
  draft: { color: "default", label: "草稿" },
  archived: { color: "default", label: "已归档" },
};

type TabKey = KnowledgeAssetType;

interface DrawerState {
  assetType: TabKey;
  assetId: string;
}

function contentExcerpt(content?: string | null, summary?: string | null): string {
  if (summary?.trim()) {
    return summary.trim();
  }
  if (!content?.trim()) {
    return "";
  }
  try {
    const payload = JSON.parse(content);
    if (payload?.format === "blocks_v1" && Array.isArray(payload.blocks)) {
      const text = payload.blocks
        .filter((block: { type?: string; text?: string }) => block.type === "paragraph" || block.type === "table")
        .map((block: { text?: string }) => block.text ?? "")
        .join(" ")
        .trim();
      if (text) {
        return text.length > 120 ? `${text.slice(0, 120)}…` : text;
      }
    }
  } catch {
    /* plain text */
  }
  const plain = content.trim();
  return plain.length > 120 ? `${plain.slice(0, 120)}…` : plain;
}

function matchesKeyword(keyword: string, title: string, summary?: string | null, content?: string | null) {
  const needle = keyword.trim().toLowerCase();
  if (!needle) {
    return true;
  }
  const haystack = [title, summary, contentExcerpt(content, summary)].filter(Boolean).join(" ").toLowerCase();
  return haystack.includes(needle);
}

export default function KnowledgeCenterPage() {
  const { selectedKbId } = useKBContext();
  const [activeTab, setActiveTab] = useState<TabKey>("ku");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [kuItems, setKuItems] = useState<KnowledgeUnitItem[]>([]);
  const [wikiItems, setWikiItems] = useState<WikiItem[]>([]);
  const [manualItems, setManualItems] = useState<ManualAssetItem[]>([]);
  const [drawer, setDrawer] = useState<DrawerState>();

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setKuItems([]);
      setWikiItems([]);
      setManualItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      if (activeTab === "ku") {
        const result = await listKnowledgeUnits(selectedKbId, { page, page_size: pageSize });
        setKuItems(result.items ?? []);
        setTotal(result.total ?? 0);
      } else if (activeTab === "wiki") {
        const result = await listWikis(selectedKbId, { page, page_size: pageSize });
        setWikiItems(result.items ?? []);
        setTotal(result.total ?? 0);
      } else {
        const result = await listManualAssets(selectedKbId, { page, page_size: pageSize });
        setManualItems(result.items ?? []);
        setTotal(result.total ?? 0);
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [activeTab, page, pageSize, selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleTabChange = useCallback((key: string) => {
    setActiveTab(key as TabKey);
    setPage(1);
    setDrawer(undefined);
  }, []);

  const openDrawer = useCallback((assetType: TabKey, assetId: string) => {
    setDrawer({ assetType, assetId });
  }, []);

  const filteredKuItems = useMemo(
    () =>
      kuItems.filter((item) =>
        matchesKeyword(keyword, item.title, item.summary, item.content),
      ),
    [keyword, kuItems],
  );

  const filteredWikiItems = useMemo(
    () =>
      wikiItems.filter((item) =>
        matchesKeyword(keyword, item.title, item.summary, item.content),
      ),
    [keyword, wikiItems],
  );

  const filteredManualItems = useMemo(
    () =>
      manualItems.filter((item) =>
        matchesKeyword(keyword, item.title, item.summary, item.content),
      ),
    [keyword, manualItems],
  );

  const kuColumns: ColumnsType<KnowledgeUnitItem> = useMemo(
    () => [
      {
        title: "标题",
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        render: (value: string) => value || "-",
      },
      {
        title: "知识类型",
        dataIndex: "knowledge_type",
        key: "knowledge_type",
        width: 140,
        render: (value: string) => value || "-",
      },
      {
        title: "摘要",
        key: "summary",
        ellipsis: true,
        render: (_value, record) => contentExcerpt(record.content, record.summary) || "（仅标题）",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (value: string) => {
          const meta = STATUS_TAG[value] ?? { color: "default", label: value || "-" };
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        render: (_value, record) => (
          <Button type="link" size="small" onClick={() => openDrawer("ku", record.ku_id)}>
            查看
          </Button>
        ),
      },
    ],
    [openDrawer],
  );

  const wikiColumns: ColumnsType<WikiItem> = useMemo(
    () => [
      {
        title: "标题",
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        render: (value: string) => value || "-",
      },
      {
        title: "Wiki 类型",
        dataIndex: "wiki_type",
        key: "wiki_type",
        width: 140,
        render: (value: string | null) => value || "-",
      },
      {
        title: "摘要",
        key: "summary",
        ellipsis: true,
        render: (_value, record) => contentExcerpt(record.content, record.summary) || "（仅标题）",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (value: string) => {
          const meta = STATUS_TAG[value] ?? { color: "default", label: value || "-" };
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        render: (_value, record) => (
          <Button type="link" size="small" onClick={() => openDrawer("wiki", record.wiki_id)}>
            查看
          </Button>
        ),
      },
    ],
    [openDrawer],
  );

  const manualColumns: ColumnsType<ManualAssetItem> = useMemo(
    () => [
      {
        title: "标题",
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        render: (value: string) => value || "-",
      },
      {
        title: "资产类型",
        dataIndex: "asset_type",
        key: "asset_type",
        width: 140,
        render: (value: string) => value || "-",
      },
      {
        title: "摘要",
        key: "summary",
        ellipsis: true,
        render: (_value, record) => contentExcerpt(record.content, record.summary) || "（仅标题）",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (value: string) => {
          const meta = STATUS_TAG[value] ?? { color: "default", label: value || "-" };
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            onClick={() => openDrawer("manual_asset", record.manual_asset_id)}
          >
            查看
          </Button>
        ),
      },
    ],
    [openDrawer],
  );

  const pagination = {
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
      <Card title="正式知识">
        <Space style={{ marginBottom: 16 }}>
          <Input.Search
            allowClear
            placeholder="按标题或摘要筛选"
            style={{ width: 280 }}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </Space>

        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          items={[
            {
              key: "ku",
              label: "知识单元",
              children: (
                <Table
                  rowKey="ku_id"
                  size="small"
                  loading={loading}
                  columns={kuColumns}
                  dataSource={filteredKuItems}
                  locale={{ emptyText: <Empty description="暂无知识单元" /> }}
                  pagination={pagination}
                />
              ),
            },
            {
              key: "wiki",
              label: "Wiki",
              children: (
                <Table
                  rowKey="wiki_id"
                  size="small"
                  loading={loading}
                  columns={wikiColumns}
                  dataSource={filteredWikiItems}
                  locale={{ emptyText: <Empty description="暂无 Wiki" /> }}
                  pagination={pagination}
                />
              ),
            },
            {
              key: "manual_asset",
              label: "手册资产",
              children: (
                <Table
                  rowKey="manual_asset_id"
                  size="small"
                  loading={loading}
                  columns={manualColumns}
                  dataSource={filteredManualItems}
                  locale={{ emptyText: <Empty description="暂无手册资产" /> }}
                  pagination={pagination}
                />
              ),
            },
          ]}
        />
      </Card>

      {drawer ? (
        <KnowledgeDetailDrawer
          kbId={selectedKbId}
          open={Boolean(drawer)}
          assetType={drawer.assetType}
          assetId={drawer.assetId}
          onClose={() => setDrawer(undefined)}
        />
      ) : null}
    </>
  );
}
