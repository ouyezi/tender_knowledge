import { Modal, Table, Typography } from "antd";
import { useMemo } from "react";
import type { ImpactReport } from "../services/lifecycleApi";

const OBJECT_TYPE_LABELS: Record<string, string> = {
  ku: "知识单元",
  wiki: "Wiki",
  template: "模板",
  template_chapter: "模板章节",
  bid_outline: "投标大纲",
  manual_asset: "人工资产",
  candidate_knowledge: "候选知识",
};

interface ImpactAnalysisModalProps {
  open: boolean;
  title?: string;
  loading?: boolean;
  report?: ImpactReport;
  counts?: Record<string, number>;
  totalCount?: number;
  description?: string;
  onClose: () => void;
  onConfirm?: () => void;
  confirmText?: string;
  confirmLoading?: boolean;
}

export default function ImpactAnalysisModal({
  open,
  title = "影响分析",
  loading = false,
  report,
  counts,
  totalCount,
  description,
  onClose,
  onConfirm,
  confirmText = "确认",
  confirmLoading = false,
}: ImpactAnalysisModalProps) {
  const dataSource = useMemo(() => {
    const source = counts ?? report?.by_object_type;
    if (!source) {
      return [];
    }
    return Object.entries(source).map(([key, count]) => ({
      key,
      object_type: key,
      label: OBJECT_TYPE_LABELS[key] ?? key,
      count,
    }));
  }, [counts, report]);

  const resolvedTotal = totalCount ?? report?.total_count ?? 0;

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onClose}
      onOk={onConfirm}
      okText={confirmText}
      okButtonProps={{ danger: Boolean(onConfirm), loading: confirmLoading }}
      cancelText="取消"
      footer={onConfirm ? undefined : null}
      width={560}
      destroyOnHidden
    >
      {description ? (
        <Typography.Paragraph type="warning">{description}</Typography.Paragraph>
      ) : null}
      <Typography.Paragraph type="secondary">引用总数：{resolvedTotal}</Typography.Paragraph>
      <Table
        loading={loading}
        size="small"
        pagination={false}
        dataSource={dataSource}
        columns={[
          { title: "对象类型", dataIndex: "label", key: "label" },
          { title: "数量", dataIndex: "count", key: "count", width: 100 },
        ]}
        locale={{ emptyText: "暂无引用" }}
      />
    </Modal>
  );
}
