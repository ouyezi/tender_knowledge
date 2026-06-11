import { apiRequest } from "./apiClient";

export interface ImpactReport {
  classification_type: string;
  classification_id: string;
  total_count: number;
  by_object_type: Record<string, number>;
}

export interface MergeResult {
  source_id: string;
  target_id: string;
  migrated_reference_count: number;
}

export async function getProductCategoryImpact(
  kbId: string,
  categoryId: string,
): Promise<ImpactReport> {
  return apiRequest<ImpactReport>(
    `/api/v1/kbs/${kbId}/product-categories/${categoryId}/impact`,
    { method: "GET" },
  );
}

export async function mergeProductCategory(
  kbId: string,
  sourceId: string,
  targetCategoryId: string,
): Promise<MergeResult> {
  return apiRequest<MergeResult>(
    `/api/v1/kbs/${kbId}/product-categories/${sourceId}/merge`,
    { method: "POST", body: { target_category_id: targetCategoryId } },
  );
}

export async function deactivateProductCategory(
  kbId: string,
  categoryId: string,
): Promise<void> {
  await apiRequest(`/api/v1/kbs/${kbId}/product-categories/${categoryId}/deactivate`, {
    method: "POST",
  });
}

export async function archiveProductCategory(
  kbId: string,
  categoryId: string,
): Promise<void> {
  await apiRequest(`/api/v1/kbs/${kbId}/product-categories/${categoryId}/archive`, {
    method: "POST",
  });
}

export async function getChapterTaxonomyImpact(
  kbId: string,
  taxonomyId: string,
): Promise<ImpactReport> {
  return apiRequest<ImpactReport>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}/impact`,
    { method: "GET" },
  );
}

export async function mergeChapterTaxonomy(
  kbId: string,
  sourceId: string,
  targetTaxonomyId: string,
): Promise<MergeResult> {
  return apiRequest<MergeResult>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies/${sourceId}/merge`,
    { method: "POST", body: { target_taxonomy_id: targetTaxonomyId } },
  );
}

export async function deactivateChapterTaxonomy(
  kbId: string,
  taxonomyId: string,
): Promise<void> {
  await apiRequest(`/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}/deactivate`, {
    method: "POST",
  });
}

export async function archiveChapterTaxonomy(
  kbId: string,
  taxonomyId: string,
): Promise<void> {
  await apiRequest(`/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}/archive`, {
    method: "POST",
  });
}
