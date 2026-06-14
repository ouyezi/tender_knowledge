import { apiRequest } from "./apiClient";

export interface CandidateSourceTrace {
  file_name?: string;
  document_name?: string;
  node_title?: string;
  import_id?: string;
  source_doc_id?: string;
  source_node_id?: string;
  parse_task_id?: string;
  bid_outline_node_id?: string;
}

export interface CandidateListItem {
  candidate_id: string;
  source_channel: string;
  import_id?: string;
  source_doc_id?: string;
  source_node_id?: string;
  candidate_type: string;
  title: string;
  summary?: string;
  suggested_knowledge_type?: string | null;
  suggested_chapter_taxonomy_id?: string | null;
  suggested_product_category_ids?: string[];
  confidence_score?: number | null;
  status: string;
  source_trace?: CandidateSourceTrace;
  created_at: string;
}

export interface CandidateListResult {
  items: CandidateListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CandidateDetail {
  candidate_id: string;
  source_channel: string;
  title: string;
  content?: string;
  summary?: string;
  status: string;
  candidate_type?: string;
  source_trace?: CandidateSourceTrace;
  created_at?: string;
}

export interface ListCandidatesParams {
  page?: number;
  page_size?: number;
  status?: string;
  import_id?: string;
  source_doc_id?: string;
  candidate_type?: string;
  source_channel?: string;
  chapter_taxonomy_id?: string;
  product_category_id?: string;
  confidence_min?: number;
}

export async function listCandidates(
  kbId: string,
  params?: ListCandidatesParams,
): Promise<CandidateListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  if (params?.status) search.set("status", params.status);
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.source_doc_id) search.set("source_doc_id", params.source_doc_id);
  if (params?.candidate_type) search.set("candidate_type", params.candidate_type);
  if (params?.source_channel) search.set("source_channel", params.source_channel);
  if (params?.chapter_taxonomy_id) search.set("chapter_taxonomy_id", params.chapter_taxonomy_id);
  if (params?.product_category_id) search.set("product_category_id", params.product_category_id);
  if (params?.confidence_min !== undefined) {
    search.set("confidence_min", String(params.confidence_min));
  }
  const qs = search.toString();
  return apiRequest<CandidateListResult>(`/api/v1/kbs/${kbId}/candidates${qs ? `?${qs}` : ""}`);
}

export async function getCandidate(kbId: string, candidateId: string): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/api/v1/kbs/${kbId}/candidates/${candidateId}`);
}

export interface CandidatePatchPayload {
  title?: string;
  summary?: string;
  content?: string;
  suggested_knowledge_type?: string | null;
  suggested_chapter_taxonomy_id?: string | null;
  suggested_product_category_ids?: string[];
  candidate_type?: string;
}

export interface CandidatePatchResult {
  candidate_id: string;
  status: string;
  updated_at: string;
}

export async function patchCandidate(
  kbId: string,
  candidateId: string,
  payload: CandidatePatchPayload,
): Promise<CandidatePatchResult> {
  return apiRequest<CandidatePatchResult>(`/api/v1/kbs/${kbId}/candidates/${candidateId}`, {
    method: "PATCH",
    body: payload,
  });
}

export type ConfirmAs =
  | "ku"
  | "wiki"
  | "template_chapter"
  | "manual_asset"
  | "chapter_pattern"
  | "product_category"
  | "ignore";

export interface ConfirmRequest {
  confirm_as: ConfirmAs;
  title?: string;
  summary?: string;
  content?: string;
  product_category_ids?: string[];
  chapter_taxonomy_id?: string | null;
  knowledge_type?: string | null;
  wiki_type?: string | null;
  asset_type?: string | null;
  searchable?: boolean;
  usage_hint?: string | null;
  review_comment?: string;
  template_id?: string | null;
  parent_chapter_id?: string | null;
  category_code?: string | null;
}

export interface ConfirmResult {
  candidate_id: string;
  confirmed_object_type: ConfirmAs;
  confirmed_object_id?: string | null;
  status: string;
  trace_id: string;
  idempotent?: boolean;
}

export async function confirmCandidate(
  kbId: string,
  candidateId: string,
  body: ConfirmRequest,
): Promise<ConfirmResult> {
  return apiRequest<ConfirmResult>(`/api/v1/kbs/${kbId}/candidates/${candidateId}/confirm`, {
    method: "POST",
    body,
  });
}

export async function retryPublishCandidate(
  kbId: string,
  candidateId: string,
  body: ConfirmRequest,
): Promise<ConfirmResult> {
  return apiRequest<ConfirmResult>(
    `/api/v1/kbs/${kbId}/candidates/${candidateId}/retry-publish`,
    {
      method: "POST",
      body,
    },
  );
}
