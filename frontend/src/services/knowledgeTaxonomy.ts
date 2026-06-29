import { apiRequest } from "./apiClient";

export type KnowledgeTaxonomyDimension =
  | "block_type"
  | "application_type"
  | "business_line"
  | "dynamic_type";

export interface KnowledgeTaxonomyItem {
  code: string;
  dimension: KnowledgeTaxonomyDimension;
  parent_code: string | null;
  label: string;
  label_en: string | null;
  level: number;
  sort_order: number;
  is_active: boolean;
}

export async function listKnowledgeTaxonomy(
  dimension: KnowledgeTaxonomyDimension,
): Promise<KnowledgeTaxonomyItem[]> {
  const search = new URLSearchParams({ dimension });
  const result = await apiRequest<{ items: KnowledgeTaxonomyItem[] }>(
    `/api/v1/knowledge-taxonomy?${search.toString()}`,
  );
  return result.items ?? [];
}
