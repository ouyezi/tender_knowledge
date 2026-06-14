import { Button, Card, Form, Input, InputNumber, Select, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  confirmRetrievalEvalCase,
  createRetrievalEvalCase,
  createRetrievalEvalRun,
  createRetrievalEvalSet,
  getRetrievalEvalRun,
  listRetrievalEvalCases,
  listRetrievalEvalSets,
  listRetrievalStrategies,
  rejectRetrievalEvalCase,
  type RetrievalEvalCase,
  type RetrievalEvalRun,
  type RetrievalEvalSet,
  type RetrievalStrategyVersion,
} from "../../services/retrievalEval";

const INTENT_OPTIONS = [
  { label: "知识检索", value: "knowledge_lookup" },
  { label: "目录匹配", value: "directory_match" },
  { label: "模块建议", value: "module_suggestion" },
];

const METRIC_OPTIONS = [
  { label: "Recall@K", value: "recall_at_k" },
  { label: "Precision@K", value: "precision_at_k" },
  { label: "MRR", value: "mrr" },
  { label: "NDCG", value: "ndcg" },
  { label: "采纳率", value: "adoption_rate" },
  { label: "误召回率", value: "false_positive_rate" },
  { label: "漏召回率", value: "false_negative_rate" },
  { label: "可追溯率", value: "sourced_result_rate" },
];

interface Props {
  kbId: string;
  readOnly: boolean;
}

function splitIds(raw: string): string[] {
  return raw
    .split(/[\n,]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function EvalSetPanel({ kbId, readOnly }: Props) {
  const [setForm] = Form.useForm<{ name: string; description?: string }>();
  const [caseForm] = Form.useForm<{
    query: string;
    intent: string;
    expected_object_ids?: string;
    negative_object_ids?: string;
  }>();
  const [runForm] = Form.useForm<{
    strategy_version_id: string;
    baseline_strategy_version_id?: string;
    k: number;
    metrics: string[];
  }>();
  const [sets, setSets] = useState<RetrievalEvalSet[]>([]);
  const [activeSetId, setActiveSetId] = useState<string>();
  const [cases, setCases] = useState<RetrievalEvalCase[]>([]);
  const [strategies, setStrategies] = useState<RetrievalStrategyVersion[]>([]);
  const [latestRun, setLatestRun] = useState<RetrievalEvalRun | null>(null);
  const [loadingSets, setLoadingSets] = useState(false);
  const [loadingCases, setLoadingCases] = useState(false);

  const loadSets = useCallback(async () => {
    if (!kbId) return;
    setLoadingSets(true);
    try {
      const [setResult, strategyResult] = await Promise.all([
        listRetrievalEvalSets(kbId, { page_size: 100 }),
        listRetrievalStrategies(kbId, { page_size: 100 }),
      ]);
      const nextSets = setResult.items ?? [];
      setSets(nextSets);
      setStrategies(strategyResult.items ?? []);
      if (!activeSetId && nextSets.length > 0) {
        setActiveSetId(nextSets[0].eval_set_id);
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoadingSets(false);
    }
  }, [activeSetId, kbId]);

  const loadCases = useCallback(async () => {
    if (!kbId || !activeSetId) {
      setCases([]);
      return;
    }
    setLoadingCases(true);
    try {
      const result = await listRetrievalEvalCases(kbId, activeSetId, { page_size: 100 });
      setCases(result.items ?? []);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoadingCases(false);
    }
  }, [activeSetId, kbId]);

  useEffect(() => {
    void loadSets();
  }, [loadSets]);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  const caseColumns: ColumnsType<RetrievalEvalCase> = useMemo(
    () => [
      { title: "查询", dataIndex: "query", key: "query", ellipsis: true },
      { title: "意图", dataIndex: "intent", key: "intent", width: 140 },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value: string) => (
          <Tag color={value === "confirmed" ? "green" : value === "rejected" ? "red" : "gold"}>{value}</Tag>
        ),
      },
      {
        title: "来源",
        dataIndex: "created_from",
        key: "created_from",
        width: 140,
      },
      {
        title: "操作",
        key: "actions",
        width: 160,
        render: (_value, record) => (
          <Space size="small">
            <Button
              type="link"
              size="small"
              disabled={readOnly || record.status === "confirmed"}
              onClick={() =>
                void confirmRetrievalEvalCase(kbId, record.eval_case_id, "admin")
                  .then(() => {
                    message.success("已确认");
                    return loadCases();
                  })
                  .catch((error: Error) => message.error(error.message))
              }
            >
              确认
            </Button>
            <Button
              type="link"
              size="small"
              disabled={readOnly || record.status === "rejected"}
              onClick={() =>
                void rejectRetrievalEvalCase(kbId, record.eval_case_id)
                  .then(() => {
                    message.success("已拒绝");
                    return loadCases();
                  })
                  .catch((error: Error) => message.error(error.message))
              }
            >
              拒绝
            </Button>
          </Space>
        ),
      },
    ],
    [kbId, loadCases, readOnly],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title="评测集">
        <Space direction="vertical" style={{ width: "100%" }}>
          <Form
            form={setForm}
            layout="inline"
            onFinish={(values) =>
              void createRetrievalEvalSet(kbId, values)
                .then(async () => {
                  message.success("评测集已创建");
                  setForm.resetFields();
                  await loadSets();
                })
                .catch((error: Error) => message.error(error.message))
            }
          >
            <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
              <Input placeholder="例如：核心检索用例" style={{ width: 260 }} />
            </Form.Item>
            <Form.Item name="description" label="描述">
              <Input placeholder="可选" style={{ width: 320 }} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" disabled={readOnly}>
                新建评测集
              </Button>
            </Form.Item>
          </Form>
          <Select
            placeholder="选择评测集"
            loading={loadingSets}
            value={activeSetId}
            options={sets.map((item) => ({ label: `${item.name} (${item.status})`, value: item.eval_set_id }))}
            onChange={setActiveSetId}
          />
        </Space>
      </Card>

      <Card title="评测用例">
        <Space direction="vertical" style={{ width: "100%" }}>
          <Form
            form={caseForm}
            layout="inline"
            initialValues={{ intent: "knowledge_lookup" }}
            onFinish={(values) => {
              if (!activeSetId) {
                message.warning("请先选择评测集");
                return;
              }
              void createRetrievalEvalCase(kbId, activeSetId, {
                query: values.query,
                intent: values.intent,
                expected_object_ids: splitIds(values.expected_object_ids || ""),
                negative_object_ids: splitIds(values.negative_object_ids || ""),
              })
                .then(async () => {
                  message.success("用例已创建");
                  caseForm.resetFields(["query", "expected_object_ids", "negative_object_ids"]);
                  await loadCases();
                })
                .catch((error: Error) => message.error(error.message));
            }}
          >
            <Form.Item name="query" label="查询" rules={[{ required: true, message: "请输入查询语句" }]}>
              <Input placeholder="例如：售后服务承诺" style={{ width: 240 }} />
            </Form.Item>
            <Form.Item name="intent" label="意图" rules={[{ required: true }]}>
              <Select options={INTENT_OPTIONS} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="expected_object_ids" label="期望对象ID">
              <Input placeholder="逗号或换行分隔" style={{ width: 220 }} />
            </Form.Item>
            <Form.Item name="negative_object_ids" label="负例对象ID">
              <Input placeholder="逗号或换行分隔" style={{ width: 220 }} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" disabled={readOnly || !activeSetId}>
                新建用例
              </Button>
            </Form.Item>
          </Form>
          <Table
            rowKey="eval_case_id"
            size="small"
            loading={loadingCases}
            columns={caseColumns}
            dataSource={cases}
            pagination={{ pageSize: 8, showTotal: (total) => `共 ${total} 条` }}
          />
        </Space>
      </Card>

      <Card title="执行评测">
        <Form
          form={runForm}
          layout="inline"
          initialValues={{
            k: 10,
            metrics: ["recall_at_k", "precision_at_k", "mrr", "ndcg"],
          }}
          onFinish={(values) => {
            if (!activeSetId) {
              message.warning("请先选择评测集");
              return;
            }
            void createRetrievalEvalRun(kbId, {
              eval_set_id: activeSetId,
              strategy_version_id: values.strategy_version_id,
              baseline_strategy_version_id: values.baseline_strategy_version_id || undefined,
              k: values.k,
              metrics: values.metrics,
            })
              .then((run) => getRetrievalEvalRun(kbId, run.eval_run_id))
              .then((run) => {
                setLatestRun(run);
                message.success("评测执行完成");
              })
              .catch((error: Error) => message.error(error.message));
          }}
        >
          <Form.Item
            name="strategy_version_id"
            label="策略版本"
            rules={[{ required: true, message: "请选择策略版本" }]}
          >
            <Select
              style={{ width: 280 }}
              options={strategies.map((item) => ({
                value: item.strategy_version_id,
                label: `${item.name} (${item.version_tag})${item.is_active ? " [激活]" : ""}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="baseline_strategy_version_id" label="基线版本">
            <Select
              allowClear
              style={{ width: 280 }}
              options={strategies.map((item) => ({
                value: item.strategy_version_id,
                label: `${item.name} (${item.version_tag})`,
              }))}
            />
          </Form.Item>
          <Form.Item name="k" label="Top K">
            <InputNumber min={1} max={100} />
          </Form.Item>
          <Form.Item name="metrics" label="指标">
            <Select mode="multiple" style={{ minWidth: 320 }} options={METRIC_OPTIONS} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" disabled={readOnly || !activeSetId}>
              开始评测
            </Button>
          </Form.Item>
        </Form>
        {latestRun ? (
          <Space direction="vertical" style={{ marginTop: 16, width: "100%" }}>
            <Tag color="blue">最近运行：{latestRun.eval_run_id}</Tag>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(
                { metrics: latestRun.metrics, comparison_metrics: latestRun.comparison_metrics },
                null,
                2,
              )}
            </pre>
          </Space>
        ) : null}
      </Card>
    </Space>
  );
}
