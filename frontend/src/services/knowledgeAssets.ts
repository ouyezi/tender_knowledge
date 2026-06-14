import { apiRequest } from "./apiClient";

export interface KnowledgeUnitItem {
  ku_id: string;
  title: string;
  summary?: string | null;
  content: string;
  knowledge_type: string;
  status: string;
  candidate_id: string;
  import_id: string;
  source_doc_id?: string | null;
  source_node_id?: string | null;
  product_category_ids?: string[];
  chapter_taxonomy_id?: string | null;
  searchable: boolean;
  usage_hint?: string | null;
}

export interface WikiItem {
  wiki_id: string;
  title: string;
  summary?: string | null;
  content: string;
  wiki_type?: string | null;
  status: string;
  candidate_id: string;
  import_id: string;
  source_doc_id?: string | null;
  source_node_id?: string | null;
  product_category_ids?: string[];
  chapter_taxonomy_id?: string | null;
  searchable: boolean;
  usage_hint?: string | null;
}

export interface ManualAssetItem {
  manual_asset_id: string;
  title: string;
  summary?: string | null;
  content?: string | null;
  asset_type: string;
  storage_path?: string | null;
  status: string;
  candidate_id: string;
  import_id: string;
  source_doc_id?: string | null;
  product_category_ids?: string[];
  searchable: boolean;
}

export interface PagedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListKnowledgeAssetsParams {
  page?: number;
  page_size?: number;
}

function buildQuery(params?: ListKnowledgeAssetsParams): string {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function listKnowledgeUnits(
  kbId: string,
  params?: ListKnowledgeAssetsParams,
): Promise<PagedResult<KnowledgeUnitItem>> {
  return apiRequest<PagedResult<KnowledgeUnitItem>>(
    `/api/v1/kbs/${kbId}/knowledge-units${buildQuery(params)}`,
  );
}

export async function getKnowledgeUnit(kbId: string, kuId: string): Promise<KnowledgeUnitItem> {
  return apiRequest<KnowledgeUnitItem>(`/api/v1/kbs/${kbId}/knowledge-units/${kuId}`);
}

export async function listWikis(
  kbId: string,
  params?: ListKnowledgeAssetsParams,
): Promise<PagedResult<WikiItem>> {
  return apiRequest<PagedResult<WikiItem>>(`/api/v1/kbs/${kbId}/wikis${buildQuery(params)}`);
}

export async function getWiki(kbId: string, wikiId: string): Promise<WikiItem> {
  return apiRequest<WikiItem>(`/api/v1/kbs/${kbId}/wikis/${wikiId}`);
}

export async function listManualAssets(
  kbId: string,
  params?: ListKnowledgeAssetsParams,
): Promise<PagedResult<ManualAssetItem>> {
  return apiRequest<PagedResult<ManualAssetItem>>(
    `/api/v1/kbs/${kbId}/manual-assets${buildQuery(params)}`,
  );
}

export async function getManualAsset(
  kbId: string,
  manualAssetId: string,
): Promise<ManualAssetItem> {
  return apiRequest<ManualAssetItem>(
    `/api/v1/kbs/${kbId}/manual-assets/${manualAssetId}`,
  );
}
