import { apiRequest } from "./apiClient";

export interface OutlineNodePayload {
  title: string;
  level: number;
  sort_order?: number;
  parent_id?: string | null;
}

export interface DirectoryMatchPayload {
  product_category_ids?: string[];
  chapter_taxonomy_ids?: string[];
  outline_nodes: OutlineNodePayload[];
  tender_requirement_context?: {
    outline_title?: string;
    score_points?: string[];
    rejection_clauses?: string[];
    format_requirements?: string[];
  };
  retrieval_options?: {
    top_k?: number;
    strategy_version_id?: string;
  };
  return_options?: {
    include_trace?: boolean;
    include_score_detail?: boolean;
  };
}

export interface DirectoryMatchResult {
  trace_id: string;
  intent: string;
  strategy_version_id: string | null;
  latency_ms: number;
  total: number;
  directory_match: {
    match_score: number;
    coverage_rate: number;
    score_detail: Record<string, number>;
    matched_outline_ids: string[];
    matched_template_chapter_ids: string[];
    matched_pattern_ids: string[];
    missing_chapters: Array<{
      pattern_id: string;
      pattern_name: string;
      frequency: number;
      reason: string;
    }>;
  };
}

export interface RetrievalTraceListItem {
  trace_id: string;
  intent: string;
  strategy_version_id: string | null;
  status: string;
  latency_ms: number;
  result_count: number;
  created_at: string;
}

export interface RetrievalTraceListResult {
  items: RetrievalTraceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface RetrievalTraceDetail {
  trace_id: string;
  intent: string;
  strategy_version_id: string | null;
  status: string;
  latency_ms: number;
  request_snapshot: Record<string, unknown>;
  stages: Record<string, unknown>;
  response_summary: Record<string, unknown>;
  error_message: string | null;
  operator_id: string | null;
  created_at: string;
}

export async function directoryMatch(
  kbId: string,
  payload: DirectoryMatchPayload,
): Promise<DirectoryMatchResult> {
  return apiRequest<DirectoryMatchResult>(`/api/v1/kbs/${kbId}/retrieval/directory-match`, {
    method: "POST",
    body: payload,
  });
}

export interface ListRetrievalTracesParams {
  intent?: string;
  status?: string;
  from?: string;
  to?: string;
  operator_id?: string;
  page?: number;
  page_size?: number;
}

export async function listRetrievalTraces(
  kbId: string,
  params?: ListRetrievalTracesParams,
): Promise<RetrievalTraceListResult> {
  const search = new URLSearchParams();
  if (params?.intent) search.set("intent", params.intent);
  if (params?.status) search.set("status", params.status);
  if (params?.from) search.set("from", params.from);
  if (params?.to) search.set("to", params.to);
  if (params?.operator_id) search.set("operator_id", params.operator_id);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<RetrievalTraceListResult>(`/api/v1/kbs/${kbId}/retrieval/traces${qs ? `?${qs}` : ""}`);
}

export async function getRetrievalTrace(
  kbId: string,
  traceId: string,
): Promise<RetrievalTraceDetail> {
  return apiRequest<RetrievalTraceDetail>(`/api/v1/kbs/${kbId}/retrieval/traces/${traceId}`);
}
