import { Modal, Table, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
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
  onClose: () => void;
}

export default function ImpactAnalysisModal({
  open,
  title = "影响分析",
  loading = false,
  report,
  onClose,
}: ImpactAnalysisModalProps) {
  const [visible, setVisible] = useState(open);

  useEffect(() => {
    setVisible(open);
  }, [open]);

  const dataSource = useMemo(() => {
    if (!report) {
      return [];
    }
    return Object.entries(report.by_object_type).map(([key, count]) => ({
      key,
      object_type: key,
      label: OBJECT_TYPE_LABELS[key] ?? key,
      count,
    }));
  }, [report]);

  return (
    <Modal
      title={title}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={560}
      destroyOnClose
    >
      <Typography.Paragraph type="secondary">
        引用总数：{report?.total_count ?? 0}
      </Typography.Paragraph>
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
