import { Alert, Button, Descriptions, Drawer, Empty, List, Space, Tag, Typography, message } from "antd";
import { useMemo, useState } from "react";
import { directoryMatch, type DirectoryMatchResult, type OutlineNodePayload } from "../../services/retrieval";

interface Props {
  open: boolean;
  kbId: string;
  outlineNodes: OutlineNodePayload[];
  productCategoryIds: string[];
  onClose: () => void;
}

export default function OutlineSimilarityDrawer({
  open,
  kbId,
  outlineNodes,
  productCategoryIds,
  onClose,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DirectoryMatchResult | null>(null);

  const canRun = useMemo(() => Boolean(kbId) && outlineNodes.length > 0, [kbId, outlineNodes.length]);

  const runDirectoryMatch = async () => {
    if (!canRun) return;
    setLoading(true);
    try {
      const data = await directoryMatch(kbId, {
        product_category_ids: productCategoryIds,
        outline_nodes: outlineNodes,
        retrieval_options: { top_k: 10 },
        return_options: { include_trace: true, include_score_detail: true },
      });
      setResult(data);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer
      title="目录相似度分析"
      open={open}
      width={560}
      onClose={onClose}
      extra={
        <Button type="primary" loading={loading} onClick={() => void runDirectoryMatch()} disabled={!canRun}>
          运行匹配
        </Button>
      }
    >
      {!canRun ? (
        <Alert type="info" showIcon message="当前目录为空，无法执行匹配分析" />
      ) : null}
      {!result ? (
        <Empty description="点击右上角“运行匹配”查看目录相似度" />
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="match_score">{result.directory_match.match_score}</Descriptions.Item>
            <Descriptions.Item label="coverage_rate">{result.directory_match.coverage_rate}</Descriptions.Item>
            <Descriptions.Item label="trace_id">
              <Typography.Text code>{result.trace_id}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="latency">{result.latency_ms} ms</Descriptions.Item>
          </Descriptions>
          <Space wrap>
            <Tag color="blue">匹配投标目录: {result.directory_match.matched_outline_ids.length}</Tag>
            <Tag color="green">匹配模板章节: {result.directory_match.matched_template_chapter_ids.length}</Tag>
            <Tag color="gold">匹配章节模式: {result.directory_match.matched_pattern_ids.length}</Tag>
          </Space>
          <List
            size="small"
            bordered
            header="缺失章节诊断"
            dataSource={result.directory_match.missing_chapters}
            locale={{ emptyText: "未发现明显缺失章节" }}
            renderItem={(item) => (
              <List.Item>
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{item.pattern_name}</Typography.Text>
                  <Typography.Text type="secondary">
                    频次 {item.frequency} · {item.reason}
                  </Typography.Text>
                </Space>
              </List.Item>
            )}
          />
        </Space>
      )}
    </Drawer>
  );
}
