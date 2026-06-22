import { apiRequest } from "./apiClient";

export type ImportanceLevel = "required" | "recommended" | "optional";

export interface BlueprintNode {
  node_id?: string;
  node_code?: string;
  node_title: string;
  node_level: number;
  node_order?: number;
  importance_level: ImportanceLevel;
  purpose?: string | null;
  writing_goal?: string | null;
  writing_hint?: string | null;
  content_description?: string | null;
  tender_response_hint?: string | null;
  content_type?: string | null;
  keyword_hint?: string[];
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
  related_regulations?: string[];
  overall_strategy?: string | null;
  common_mistakes?: string | null;
  template_style?: string | null;
  usual_page_range?: string | null;
  suggested_structure_md?: string | null;
  status?: string;
  version?: number;
  nodes: BlueprintNode[];
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
