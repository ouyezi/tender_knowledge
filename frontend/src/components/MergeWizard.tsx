import { Alert, Modal, Select, Space, Typography } from "antd";
import { useEffect, useState } from "react";
import ImpactAnalysisModal from "./ImpactAnalysisModal";
import type { ImpactReport, MergeResult } from "../services/lifecycleApi";

export interface MergeTargetOption {
  label: string;
  value: string;
}

interface MergeWizardProps {
  open: boolean;
  sourceLabel: string;
  targetOptions: MergeTargetOption[];
  loadingTargets?: boolean;
  onClose: () => void;
  onLoadImpact: (targetId: string) => Promise<ImpactReport>;
  onConfirmMerge: (targetId: string) => Promise<MergeResult>;
  onMerged: (result: MergeResult) => void;
}

export default function MergeWizard({
  open,
  sourceLabel,
  targetOptions,
  loadingTargets = false,
  onClose,
  onLoadImpact,
  onConfirmMerge,
  onMerged,
}: MergeWizardProps) {
  const [targetId, setTargetId] = useState<string | undefined>();
  const [impactOpen, setImpactOpen] = useState(false);
  const [impactLoading, setImpactLoading] = useState(false);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [impactReport, setImpactReport] = useState<ImpactReport | undefined>();
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (!open) {
      setTargetId(undefined);
      setImpactReport(undefined);
      setError(undefined);
      setImpactOpen(false);
    }
  }, [open]);

  const handlePreviewImpact = async () => {
    if (!targetId) {
      return;
    }
    setImpactLoading(true);
    setError(undefined);
    try {
      const report = await onLoadImpact(targetId);
      setImpactReport(report);
      setImpactOpen(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImpactLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!targetId) {
      return;
    }
    setMergeLoading(true);
    setError(undefined);
    try {
      const result = await onConfirmMerge(targetId);
      onMerged(result);
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setMergeLoading(false);
    }
  };

  return (
    <>
      <Modal
        title="合并分类"
        open={open}
        onCancel={onClose}
        onOk={handleConfirm}
        okText="确认合并"
        okButtonProps={{ disabled: !targetId, loading: mergeLoading }}
        destroyOnHidden
      >
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Typography.Text>
            将 <strong>{sourceLabel}</strong> 合并到目标分类，引用将迁移至目标。
          </Typography.Text>
          <Select
            showSearch
            placeholder="选择目标分类"
            style={{ width: "100%" }}
            loading={loadingTargets}
            value={targetId}
            options={targetOptions}
            onChange={setTargetId}
            optionFilterProp="label"
          />
          <Typography.Link onClick={handlePreviewImpact} disabled={!targetId || impactLoading}>
            预览目标分类影响分析
          </Typography.Link>
          {error && <Alert type="error" showIcon message={error} />}
        </Space>
      </Modal>

      <ImpactAnalysisModal
        open={impactOpen}
        title="目标分类影响分析"
        loading={impactLoading}
        report={impactReport}
        onClose={() => setImpactOpen(false)}
      />
    </>
  );
}
