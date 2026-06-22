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

export function getImportanceLevelLabel(level: ImportanceLevel | undefined): string {
  if (!level) {
    return "-";
  }
  return IMPORTANCE_LEVEL_LABELS[level] ?? level;
}
