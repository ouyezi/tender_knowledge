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

export async function listCandidates(
  kbId: string,
  params?: {
    page?: number;
    page_size?: number;
    status?: string;
    import_id?: string;
    source_doc_id?: string;
    candidate_type?: string;
    source_channel?: string;
  },
): Promise<CandidateListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  if (params?.status) search.set("status", params.status);
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.source_doc_id) search.set("source_doc_id", params.source_doc_id);
  if (params?.candidate_type) search.set("candidate_type", params.candidate_type);
  if (params?.source_channel) search.set("source_channel", params.source_channel);
  const qs = search.toString();
  return apiRequest<CandidateListResult>(`/api/v1/kbs/${kbId}/candidates${qs ? `?${qs}` : ""}`);
}

export async function getCandidate(kbId: string, candidateId: string): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/api/v1/kbs/${kbId}/candidates/${candidateId}`);
}
