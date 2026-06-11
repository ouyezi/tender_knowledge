import { apiRequest } from "./apiClient";

export interface ChapterTaxonomyNode {
  taxonomy_id: string;
  parent_id: string | null;
  standard_name: string;
  taxonomy_code: string;
  synonyms: string[];
  description: string;
  status: string;
  depth: number;
  children: ChapterTaxonomyNode[];
}

export interface ChapterTaxonomyDetail {
  taxonomy_id: string;
  parent_id: string | null;
  standard_name: string;
  taxonomy_code: string;
  description: string;
  status: string;
  depth: number;
  synonyms: string[];
  product_category_ids: string[];
  child_ids: string[];
  breadcrumb: Array<{ taxonomy_id: string; standard_name: string }>;
  created_at: string;
  updated_at: string;
}

interface CreateTaxonomyPayload {
  parent_id?: string | null;
  standard_name: string;
  taxonomy_code: string;
  description?: string;
  synonyms?: string[];
  product_category_ids?: string[];
}

interface PatchTaxonomyPayload {
  standard_name?: string;
  description?: string;
  status?: string;
}

export async function getChapterTaxonomyTree(
  kbId: string,
): Promise<ChapterTaxonomyNode[]> {
  const data = await apiRequest<{ nodes: ChapterTaxonomyNode[] }>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies/tree`,
    { method: "GET" },
  );
  return data.nodes;
}

export async function getChapterTaxonomyDetail(
  kbId: string,
  taxonomyId: string,
): Promise<ChapterTaxonomyDetail> {
  return apiRequest<ChapterTaxonomyDetail>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}`,
    { method: "GET" },
  );
}

export async function createChapterTaxonomy(
  kbId: string,
  payload: CreateTaxonomyPayload,
): Promise<{ taxonomy_id: string }> {
  return apiRequest<{ taxonomy_id: string }>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies`,
    { method: "POST", body: payload },
  );
}

export async function updateChapterTaxonomy(
  kbId: string,
  taxonomyId: string,
  payload: PatchTaxonomyPayload,
): Promise<void> {
  await apiRequest(`/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function replaceChapterTaxonomySynonyms(
  kbId: string,
  taxonomyId: string,
  synonyms: string[],
): Promise<string[]> {
  const data = await apiRequest<{ synonyms: string[] }>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}/synonyms`,
    { method: "PUT", body: { synonyms } },
  );
  return data.synonyms;
}

export async function replaceChapterTaxonomyBindings(
  kbId: string,
  taxonomyId: string,
  productCategoryIds: string[],
): Promise<string[]> {
  const data = await apiRequest<{ product_category_ids: string[] }>(
    `/api/v1/kbs/${kbId}/chapter-taxonomies/${taxonomyId}/product-categories`,
    { method: "PUT", body: { product_category_ids: productCategoryIds, source: "manual" } },
  );
  return data.product_category_ids;
}
