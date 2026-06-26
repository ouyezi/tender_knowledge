import { Tag } from "antd";

export interface ConfidenceBadgeProps {
  confidence?: number | null;
}

interface ConfidenceLevelMeta {
  label: string;
  color: string;
}

function normalizeConfidence(confidence: number): number {
  if (Number.isNaN(confidence)) return 0;
  return Math.max(0, Math.min(100, Math.round(confidence)));
}

export function getConfidenceLevel(confidence?: number | null): ConfidenceLevelMeta {
  if (confidence === undefined || confidence === null) {
    return { label: "未评估", color: "default" };
  }
  const score = normalizeConfidence(confidence);
  if (score >= 85) {
    return { label: "高", color: "green" };
  }
  if (score >= 70) {
    return { label: "较高", color: "blue" };
  }
  if (score >= 50) {
    return { label: "中", color: "gold" };
  }
  return { label: "低", color: "red" };
}

export default function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const score = confidence === undefined || confidence === null ? null : normalizeConfidence(confidence);
  const level = getConfidenceLevel(score);
  if (score === null) {
    return <Tag>{level.label}</Tag>;
  }
  return <Tag color={level.color}>{`${level.label} (${score})`}</Tag>;
}
