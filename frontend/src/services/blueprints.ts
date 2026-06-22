import { apiRequest } from "./apiClient";

export type ImportanceLevel = "required" | "recommended" | "optional";

export interface BlueprintNode {
  node_id?: string;
  node_code?: string;
  node_title: string;
  node_level: number;
  node_order?: number;
  importance_level: ImportanceLevel;
  content_description?: string | null;
  tender_response_hint?: string | null;
  children?: BlueprintNode[];
}

export interface BlueprintDraft {
  blueprint_id?: string;
  name: string;
  description?: string | null;
  source_doc_id: string;
  source_node_id: string;
  source_chapter_title?: string | null;
  product_tags?: string[];
  industry_tags?: string[];
  scenario_tags?: string[];
  applicable_project_type?: string[];
  suggested_structure_md?: string | null;
  status?: string;
  version?: number;
  nodes: BlueprintNode[];
}

export interface SuggestOutlineRequest {
  blueprint_ids: string[];
  requirement_description: string;
}

export interface SuggestOutlineNode {
  title: string;
  content_suggestion: string;
  importance: ImportanceLevel;
  split_reason: string | null;
  no_split_reason: string | null;
  children: SuggestOutlineNode[];
}

export interface SuggestOutlineResult {
  outline_title: string;
  summary: string;
  nodes: SuggestOutlineNode[];
}

export interface BlueprintListItem {
  blueprint_id: string;
  kb_id: string;
  name: string;
  description: string | null;
  source_doc_id: string;
  source_node_id: string;
  source_chapter_title: string | null;
  product_tags: string[];
  industry_tags: string[];
  scenario_tags: string[];
  status: string;
  version: number;
  updated_at: string | null;
  embedding_status?: string;
}

export interface ListBlueprintsParams {
  keyword?: string;
  product_tags?: string[];
  industry_tags?: string[];
  scenario_tags?: string[];
  page?: number;
  page_size?: number;
}

export interface PagedBlueprints {
  items: BlueprintListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DeleteBlueprintResult {
  blueprint_id: string;
  deleted: boolean;
}

function appendList(search: URLSearchParams, key: string, values?: string[]): void {
  if (!values?.length) return;
  for (const value of values) {
    search.append(key, value);
  }
}

function buildListQuery(params?: ListBlueprintsParams): string {
  const search = new URLSearchParams();
  if (params?.keyword) search.set("keyword", params.keyword);
  appendList(search, "product_tags", params?.product_tags);
  appendList(search, "industry_tags", params?.industry_tags);
  appendList(search, "scenario_tags", params?.scenario_tags);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function generateBlueprint(
  kbId: string,
  body: { doc_id: string; node_id: string },
): Promise<BlueprintDraft> {
  return apiRequest<BlueprintDraft>(`/api/v1/kbs/${kbId}/blueprints/generate`, {
    method: "POST",
    body,
  });
}

export async function getBlueprintBySource(
  kbId: string,
  params: { doc_id: string; node_id: string },
): Promise<BlueprintListItem | null> {
  const search = new URLSearchParams({
    doc_id: params.doc_id,
    node_id: params.node_id,
  });
  return apiRequest<BlueprintListItem | null>(
    `/api/v1/kbs/${kbId}/blueprints/by-source?${search.toString()}`,
  );
}

export async function createBlueprint(
  kbId: string,
  body: BlueprintDraft,
): Promise<BlueprintListItem> {
  return apiRequest<BlueprintListItem>(`/api/v1/kbs/${kbId}/blueprints`, {
    method: "POST",
    body,
  });
}

export async function updateBlueprint(
  kbId: string,
  id: string,
  body: BlueprintDraft,
): Promise<BlueprintListItem> {
  return apiRequest<BlueprintListItem>(`/api/v1/kbs/${kbId}/blueprints/${id}`, {
    method: "PUT",
    body,
  });
}

export async function listBlueprints(
  kbId: string,
  params?: ListBlueprintsParams,
): Promise<PagedBlueprints> {
  return apiRequest<PagedBlueprints>(
    `/api/v1/kbs/${kbId}/blueprints${buildListQuery(params)}`,
  );
}

export async function getBlueprint(kbId: string, id: string): Promise<BlueprintDraft> {
  return apiRequest<BlueprintDraft>(`/api/v1/kbs/${kbId}/blueprints/${id}`);
}

export async function deleteBlueprint(
  kbId: string,
  id: string,
): Promise<DeleteBlueprintResult> {
  return apiRequest<DeleteBlueprintResult>(`/api/v1/kbs/${kbId}/blueprints/${id}`, {
    method: "DELETE",
  });
}

export async function suggestBlueprintOutline(
  kbId: string,
  body: SuggestOutlineRequest,
): Promise<SuggestOutlineResult> {
  return apiRequest<SuggestOutlineResult>(`/api/v1/kbs/${kbId}/blueprints/suggest-outline`, {
    method: "POST",
    body,
  });
}

export interface ParseSearchQueryRequest {
  query: string;
}

export interface ParseSearchQueryResult {
  semantic_query: string;
  keyword: string;
  product_tags: string[];
  industry_tags: string[];
  scenario_tags: string[];
}

export interface BlueprintSearchParams {
  semantic_query?: string;
  keyword?: string;
  product_tags?: string[];
  industry_tags?: string[];
  scenario_tags?: string[];
  vector_weight?: number;
  keyword_weight?: number;
  top_k?: number;
}

export interface BlueprintSearchHighlight {
  field: string;
  snippet: string;
}

export interface BlueprintSearchItem extends BlueprintListItem {
  score: number;
  score_detail: {
    vector_score: number;
    keyword_score: number;
    vector_weight: number;
    keyword_weight: number;
  };
  highlights: BlueprintSearchHighlight[];
}

export interface BlueprintSearchResult {
  items: BlueprintSearchItem[];
  total: number;
  search_meta: {
    vector_enabled: boolean;
    keyword_enabled: boolean;
    candidates_scanned: number;
  };
}

export async function parseBlueprintSearchQuery(
  kbId: string,
  body: ParseSearchQueryRequest,
): Promise<ParseSearchQueryResult> {
  return apiRequest<ParseSearchQueryResult>(
    `/api/v1/kbs/${kbId}/blueprints/parse-search-query`,
    { method: "POST", body },
  );
}

export async function searchBlueprints(
  kbId: string,
  body: BlueprintSearchParams,
): Promise<BlueprintSearchResult> {
  return apiRequest<BlueprintSearchResult>(`/api/v1/kbs/${kbId}/blueprints/search`, {
    method: "POST",
    body,
  });
}

export async function rebuildBlueprintIndex(
  kbId: string,
): Promise<{ queued: number; message: string }> {
  return apiRequest<{ queued: number; message: string }>(
    `/api/v1/kbs/${kbId}/blueprints/index/rebuild`,
    { method: "POST" },
  );
}
