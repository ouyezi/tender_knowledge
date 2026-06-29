import { apiRequest } from "./apiClient";

export interface DynamicKnowledgeRecord {
  id: number;
  kb_id: string;
  dynamic_type_code: string;
  dynamic_type_label: string;
  title: string;
  content: string;
  structured_data: Record<string, unknown>;
  business_line_codes: string[];
  business_line_labels: string[];
  source_type: string;
  source_doc_id: string | null;
  source_chunk_id: number | null;
  issue_date: string | null;
  expire_date: string | null;
  is_expired: boolean;
  status: string;
  sync_status: string;
  last_synced_at: string | null;
  content_hash: string | null;
  create_time: string | null;
  update_time: string | null;
}

export interface DynamicKnowledgePayload {
  dynamic_type_code: string;
  title: string;
  content?: string;
  structured_data?: Record<string, unknown>;
  business_line_codes?: string[];
  source_type?: string;
  source_doc_id?: string | null;
  source_chunk_id?: number | null;
  issue_date?: string | null;
  expire_date?: string | null;
  status?: string;
  sync_status?: string;
}

export interface ListDynamicKnowledgeParams {
  dynamic_type_code?: string;
  status?: string;
  business_line_codes?: string[];
  expired_only?: boolean;
  page?: number;
  page_size?: number;
}

export interface PagedDynamicKnowledge {
  items: DynamicKnowledgeRecord[];
  total: number;
  page: number;
  page_size: number;
}

function appendList(search: URLSearchParams, key: string, values?: string[]): void {
  if (!values?.length) return;
  for (const value of values) {
    search.append(key, value);
  }
}

function buildListQuery(params?: ListDynamicKnowledgeParams): string {
  const search = new URLSearchParams();
  if (params?.dynamic_type_code) search.set("dynamic_type_code", params.dynamic_type_code);
  if (params?.status) search.set("status", params.status);
  appendList(search, "business_line_codes", params?.business_line_codes);
  if (params?.expired_only !== undefined) search.set("expired_only", String(params.expired_only));
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function listDynamicKnowledge(
  kbId: string,
  params?: ListDynamicKnowledgeParams,
): Promise<PagedDynamicKnowledge> {
  return apiRequest<PagedDynamicKnowledge>(`/api/v1/kbs/${kbId}/dynamic-knowledge${buildListQuery(params)}`);
}

export async function getDynamicKnowledge(
  kbId: string,
  recordId: number,
): Promise<DynamicKnowledgeRecord> {
  return apiRequest<DynamicKnowledgeRecord>(`/api/v1/kbs/${kbId}/dynamic-knowledge/${recordId}`);
}

export async function createDynamicKnowledge(
  kbId: string,
  body: DynamicKnowledgePayload,
): Promise<DynamicKnowledgeRecord> {
  return apiRequest<DynamicKnowledgeRecord>(`/api/v1/kbs/${kbId}/dynamic-knowledge`, {
    method: "POST",
    body,
  });
}

export async function updateDynamicKnowledge(
  kbId: string,
  recordId: number,
  body: Partial<DynamicKnowledgePayload>,
): Promise<DynamicKnowledgeRecord> {
  return apiRequest<DynamicKnowledgeRecord>(`/api/v1/kbs/${kbId}/dynamic-knowledge/${recordId}`, {
    method: "PUT",
    body,
  });
}

export async function deleteDynamicKnowledge(
  kbId: string,
  recordId: number,
): Promise<{ id: number; deleted: boolean }> {
  return apiRequest<{ id: number; deleted: boolean }>(`/api/v1/kbs/${kbId}/dynamic-knowledge/${recordId}`, {
    method: "DELETE",
  });
}
