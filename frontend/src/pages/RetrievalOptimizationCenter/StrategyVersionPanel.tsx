import { Button, Form, Input, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  activateRetrievalStrategy,
  createRetrievalStrategy,
  listRetrievalStrategies,
  type RetrievalStrategyVersion,
} from "../../services/retrievalEval";

interface Props {
  kbId: string;
  readOnly: boolean;
}

function parseConfig(raw: string): Record<string, unknown> {
  if (!raw.trim()) return {};
  return JSON.parse(raw) as Record<string, unknown>;
}

export default function StrategyVersionPanel({ kbId, readOnly }: Props) {
  const [form] = Form.useForm<{
    name: string;
    version_tag: string;
    notes?: string;
    config?: string;
    embedding_config_version?: string;
    rerank_config_version?: string;
    prompt_config_version?: string;
  }>();
  const [items, setItems] = useState<RetrievalStrategyVersion[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    try {
      const result = await listRetrievalStrategies(kbId, { page_size: 100 });
      setItems(result.items ?? []);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const columns: ColumnsType<RetrievalStrategyVersion> = useMemo(
    () => [
      {
        title: "名称",
        dataIndex: "name",
        key: "name",
      },
      {
        title: "版本",
        dataIndex: "version_tag",
        key: "version_tag",
        width: 120,
      },
      {
        title: "状态",
        dataIndex: "is_active",
        key: "is_active",
        width: 100,
        render: (value: boolean) => (
          <Tag color={value ? "green" : "default"}>{value ? "激活中" : "未激活"}</Tag>
        ),
      },
      {
        title: "配置版本",
        key: "config_versions",
        render: (_value, record) =>
          [
            record.embedding_config_version && `emb:${record.embedding_config_version}`,
            record.rerank_config_version && `rerank:${record.rerank_config_version}`,
            record.prompt_config_version && `prompt:${record.prompt_config_version}`,
          ]
            .filter(Boolean)
            .join(" | ") || "-",
      },
      {
        title: "备注",
        dataIndex: "notes",
        key: "notes",
        ellipsis: true,
        render: (value: string | null) => value || "-",
      },
      {
        title: "操作",
        key: "actions",
        width: 110,
        render: (_value, record) => (
          <Button
            type="link"
            size="small"
            disabled={readOnly || record.is_active}
            onClick={() =>
              void activateRetrievalStrategy(kbId, record.strategy_version_id)
                .then(async () => {
                  message.success("策略已激活");
                  await loadData();
                })
                .catch((error: Error) => message.error(error.message))
            }
          >
            设为激活
          </Button>
        ),
      },
    ],
    [kbId, loadData, readOnly],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => {
          let parsedConfig: Record<string, unknown> = {};
          try {
            parsedConfig = parseConfig(values.config || "");
          } catch {
            message.error("config 不是合法 JSON");
            return;
          }
          void createRetrievalStrategy(kbId, {
            name: values.name,
            version_tag: values.version_tag,
            notes: values.notes || undefined,
            config: parsedConfig,
            embedding_config_version: values.embedding_config_version || undefined,
            rerank_config_version: values.rerank_config_version || undefined,
            prompt_config_version: values.prompt_config_version || undefined,
          })
            .then(async () => {
              message.success("策略版本已创建");
              form.resetFields();
              await loadData();
            })
            .catch((error: Error) => message.error(error.message));
        }}
      >
        <Space align="start" wrap>
          <Form.Item name="name" label="策略名称" rules={[{ required: true, message: "请输入策略名称" }]}>
            <Input placeholder="例如 default-v2" style={{ width: 220 }} />
          </Form.Item>
          <Form.Item name="version_tag" label="版本号" rules={[{ required: true, message: "请输入版本号" }]}>
            <Input placeholder="例如 2.0.0" style={{ width: 140 }} />
          </Form.Item>
          <Form.Item name="embedding_config_version" label="Embedding版本">
            <Input style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="rerank_config_version" label="Rerank版本">
            <Input style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="prompt_config_version" label="Prompt版本">
            <Input style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input style={{ width: 220 }} />
          </Form.Item>
        </Space>
        <Form.Item name="config" label="配置(JSON)" extra='例如 {"weights":{"keyword":0.7}}'>
          <Input.TextArea rows={3} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" disabled={readOnly}>
            创建策略版本
          </Button>
        </Form.Item>
      </Form>

      <Table
        rowKey="strategy_version_id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={items}
        pagination={{ pageSize: 8, showTotal: (total) => `共 ${total} 条` }}
      />
    </Space>
  );
}
