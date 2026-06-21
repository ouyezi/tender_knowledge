import type { ImportanceLevel } from "../services/blueprints";

export const IMPORTANCE_LEVEL_LABELS: Record<ImportanceLevel, string> = {
  required: "必选",
  recommended: "推荐",
  optional: "可选",
};

export const IMPORTANCE_LEVEL_OPTIONS: { value: ImportanceLevel; label: string }[] = [
  { value: "required", label: IMPORTANCE_LEVEL_LABELS.required },
  { value: "recommended", label: IMPORTANCE_LEVEL_LABELS.recommended },
  { value: "optional", label: IMPORTANCE_LEVEL_LABELS.optional },
];

export const TEMPLATE_STYLE_OPTIONS: { value: string; label: string }[] = [
  { value: "formal", label: "正式严谨" },
  { value: "technical", label: "技术导向" },
  { value: "concise", label: "简洁高效" },
];

export const CONTENT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "text", label: "文本" },
  { value: "table", label: "表格" },
  { value: "list", label: "列表" },
  { value: "image", label: "图示" },
];

export function getImportanceLevelLabel(level: ImportanceLevel | undefined): string {
  if (!level) {
    return "-";
  }
  return IMPORTANCE_LEVEL_LABELS[level] ?? level;
}
