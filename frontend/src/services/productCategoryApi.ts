import { apiRequest } from "./apiClient";

export interface ProductCategoryNode {
  category_id: string;
  parent_id: string | null;
  category_name: string;
  category_code: string;
  aliases: string[];
  description: string;
  status: string;
  depth: number;
  children: ProductCategoryNode[];
}

export interface ProductCategoryDetail {
  category_id: string;
  parent_id: string | null;
  category_name: string;
  category_code: string;
  description: string;
  status: string;
  depth: number;
  aliases: string[];
  child_ids: string[];
  breadcrumb: Array<{ category_id: string; category_name: string }>;
  created_at: string;
  updated_at: string;
}

interface CreateCategoryPayload {
  parent_id?: string | null;
  category_name: string;
  category_code: string;
  description?: string;
  aliases?: string[];
}

interface PatchCategoryPayload {
  category_name?: string;
  description?: string;
  status?: string;
}

export async function getProductCategoryTree(
  kbId: string,
): Promise<ProductCategoryNode[]> {
  const data = await apiRequest<{ nodes: ProductCategoryNode[] }>(
    `/api/v1/kbs/${kbId}/product-categories/tree`,
    { method: "GET" },
  );
  return data.nodes;
}

export async function getProductCategoryDetail(
  kbId: string,
  categoryId: string,
): Promise<ProductCategoryDetail> {
  return apiRequest<ProductCategoryDetail>(
    `/api/v1/kbs/${kbId}/product-categories/${categoryId}`,
    { method: "GET" },
  );
}

export async function createProductCategory(
  kbId: string,
  payload: CreateCategoryPayload,
): Promise<{ category_id: string }> {
  return apiRequest<{ category_id: string }>(
    `/api/v1/kbs/${kbId}/product-categories`,
    { method: "POST", body: payload },
  );
}

export async function updateProductCategory(
  kbId: string,
  categoryId: string,
  payload: PatchCategoryPayload,
): Promise<void> {
  await apiRequest(`/api/v1/kbs/${kbId}/product-categories/${categoryId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function replaceProductCategoryAliases(
  kbId: string,
  categoryId: string,
  aliases: string[],
): Promise<string[]> {
  const data = await apiRequest<{ aliases: string[] }>(
    `/api/v1/kbs/${kbId}/product-categories/${categoryId}/aliases`,
    { method: "PUT", body: { aliases } },
  );
  return data.aliases;
}
