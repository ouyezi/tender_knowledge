import {
  Alert,
  Descriptions,
  Drawer,
  Empty,
  Spin,
  Table,
  Tag,
  Timeline,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { ActualBidParseTaskDetail } from "../../services/actualBidParse";

const OUTLINE_WARNING_LABELS: Record<string, string> = {
  embedded_document_detected: "内嵌附件",
  high_l1_ratio: "L1占比偏高",
  flat_fallback: "扁平回退",
  empty_outline: "空目录",
  high_review_ratio: "待复核偏多",
};

interface ParseTaskLogDrawerProps {
  open: boolean;
  loading: boolean;
  task: ActualBidParseTaskDetail | null;
  onClose: () => void;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function ParseTaskLogDrawer({ open, loading, task, onClose }: ParseTaskLogDrawerProps) {
  const filteredColumns: ColumnsType<{ title: string; reason_code: string; level: number }> = [
    { title: "标题", dataIndex: "title", key: "title", ellipsis: true },
    { title: "原因", dataIndex: "reason_code", key: "reason_code", width: 140 },
    { title: "层级", dataIndex: "level", key: "level", width: 72 },
  ];

  const logs = task?.llm_progress?.logs ?? [];
  const phaseTimings = task?.llm_progress?.phase_timings_ms ?? {};

  return (
    <Drawer title={task?.file_name ?? "解析任务日志"} width={720} open={open} onClose={onClose} destroyOnClose>
      {loading ? (
        <Spin />
      ) : !task ? (
        <Empty description="暂无任务详情" />
      ) : (
        <>
          {task.error_message ? (
            <Alert type="error" showIcon message="解析失败" description={task.error_message} style={{ marginBottom: 16 }} />
          ) : null}

          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="任务 ID">{task.parse_task_id}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={task.status === "failed" ? "error" : task.status === "ready" ? "warning" : "default"}>
                {task.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="阶段">{task.task_phase ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="策略">{task.parse_strategy ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="开始">{formatDateTime(task.started_at)}</Descriptions.Item>
            <Descriptions.Item label="结束">{formatDateTime(task.finished_at)}</Descriptions.Item>
          </Descriptions>

          {task.outline_quality ? (
            <>
              <Typography.Title level={5}>目录质量</Typography.Title>
              <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
                <Descriptions.Item label="节点数">{task.outline_quality.node_count}</Descriptions.Item>
                <Descriptions.Item label="L1 占比">{Math.round(task.outline_quality.l1_ratio * 100)}%</Descriptions.Item>
                <Descriptions.Item label="最大深度">{task.outline_quality.max_depth}</Descriptions.Item>
                <Descriptions.Item label="抽取策略">{task.outline_quality.extract_strategy}</Descriptions.Item>
                <Descriptions.Item label="警告" span={2}>
                  {(task.outline_quality.warnings ?? []).length
                    ? (task.outline_quality.warnings ?? []).map((w) => (
                        <Tag key={w} color="warning">
                          {OUTLINE_WARNING_LABELS[w] ?? w}
                        </Tag>
                      ))
                    : "无"}
                </Descriptions.Item>
              </Descriptions>
            </>
          ) : null}

          {Object.keys(phaseTimings).length > 0 ? (
            <>
              <Typography.Title level={5}>阶段耗时 (ms)</Typography.Title>
              <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
                {Object.entries(phaseTimings).map(([key, value]) => (
                  <Descriptions.Item key={key} label={key}>
                    {value}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            </>
          ) : null}

          {task.downstream_entries?.length ? (
            <>
              <Typography.Title level={5}>下游任务</Typography.Title>
              <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
                {task.downstream_entries.map((entry) => (
                  <Descriptions.Item key={entry.task_type} label={entry.task_type}>
                    {entry.status}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            </>
          ) : null}

          {(task.filtered_total ?? 0) > 0 ? (
            <>
              <Typography.Title level={5}>已过滤节点 ({task.filtered_total})</Typography.Title>
              <Table
                rowKey={(row) => `${row.title}-${row.reason_code}`}
                size="small"
                pagination={false}
                columns={filteredColumns}
                dataSource={task.filtered_nodes_sample ?? []}
                style={{ marginBottom: 16 }}
              />
            </>
          ) : null}

          <Typography.Title level={5}>解析日志</Typography.Title>
          {logs.length === 0 ? (
            <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Timeline
              items={logs.map((log) => ({
                color: log.level === "error" ? "red" : "blue",
                children: (
                  <>
                    <Typography.Text type="secondary">{formatDateTime(log.ts)}</Typography.Text>
                    <div>{log.message}</div>
                  </>
                ),
              }))}
            />
          )}
        </>
      )}
    </Drawer>
  );
}
