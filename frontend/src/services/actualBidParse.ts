import { apiRequest } from "./apiClient";

export interface EmbeddedRegionSample {
  trigger_title: string;
  resume_title: string;
  skipped_heading_count: number;
}

export interface OutlineQualitySummary {
  node_count: number;
  l1_ratio: number;
  max_depth: number;
  warnings: string[];
  extract_strategy: string;
  filter_stats?: { excluded: number; kept: number; by_reason?: Record<string, number> };
  embedded_heading_count?: number;
  embedded_regions_sample?: EmbeddedRegionSample[];
}

export interface ParseProgressLogEntry {
  ts: string;
  level: string;
  message: string;
}

export interface ParseLlmProgress {
  total_chunks?: number;
  completed_chunks?: number;
  failed_chunks?: number;
  degraded_to_rule?: number;
  logs?: ParseProgressLogEntry[];
  phase_timings_ms?: Record<string, number>;
  phase?: string;
}

export interface FilteredNodeSample {
  title: string;
  reason_code: string;
  level: number;
}

export interface ActualBidParseTaskListItem {
  parse_task_id: string;
  import_id: string;
  document_id: string | null;
  bid_outline_id: string | null;
  task_phase: string | null;
  status: string;
  parse_strategy: string | null;
  error_message: string | null;
  retry_count: number;
  file_name?: string | null;
  outline_quality?: OutlineQualitySummary | null;
  filtered_total?: number;
  filtered_nodes_sample?: FilteredNodeSample[];
  llm_progress?: ParseLlmProgress | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface ActualBidParseTaskListResult {
  items: ActualBidParseTaskListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ActualBidParseTaskDetail extends ActualBidParseTaskListItem {
  suggestion?: {
    outline_extract_strategy?: string | null;
    node_count?: number | null;
    candidate_count?: number | null;
    needs_manual_review?: boolean | null;
  } | null;
  downstream_entries?: Array<{ task_type: string; status: string }>;
}

export interface ActualBidDocument {
  document_id: string;
  import_id: string;
  source_type: string;
  source_usage: string;
  product_category_ids: string[];
  bid_project_name: string | null;
  bid_customer_name: string | null;
  document_name: string;
  parse_status: string;
  tree_version: number;
  bid_outline_id: string | null;
}

export interface DocumentTreeNode {
  node_id: string;
  parent_id: string | null;
  node_type: string;
  title: string;
  level: number;
  sort_order: number;
  chapter_taxonomy_id: string | null;
  product_category_ids: string[];
  is_outline_node: boolean;
  needs_manual_review: boolean;
  content_preview: string | null;
}

export interface DocumentTreeResult {
  document_id: string;
  tree_version: number;
  nodes: DocumentTreeNode[];
}

export interface CandidateListItem {
  candidate_id: string;
  source_channel?: string;
  import_id?: string;
  source_doc_id?: string;
  source_node_id?: string;
  candidate_type?: string;
  title?: string;
  summary?: string;
  suggested_knowledge_type?: string | null;
  suggested_chapter_taxonomy_id?: string | null;
  suggested_product_category_ids?: string[];
  confidence_score?: number | null;
  status?: string;
  source_trace?: {
    file_name?: string;
    document_name?: string;
    node_title?: string;
  };
  created_at?: string;
}

export interface CandidateListResult {
  items: CandidateListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConfirmActualBidParsePayload {
  document: {
    bid_project_name: string;
    bid_customer_name: string;
    product_category_ids: string[];
  };
  outline_nodes: Array<{
    outline_node_id?: string;
    node_id?: string;
    parent_id: string | null;
    title: string;
    level: number;
    sort_order: number;
    chapter_taxonomy_id: string | null;
    product_category_ids: string[];
    needs_manual_review?: boolean;
  }>;
}

export interface ConfirmActualBidParseResult {
  parse_task_id: string;
  document_id: string;
  bid_outline_id: string;
  status: string;
  structure_locked_at: string | null;
  updated_outline_nodes: number;
}

export async function listActualBidParseTasks(
  kbId: string,
  params?: { page?: number; page_size?: number; import_id?: string; status?: string },
): Promise<ActualBidParseTaskListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.status) search.set("status", params.status);
  const qs = search.toString();
  return apiRequest<ActualBidParseTaskListResult>(
    `/api/v1/kbs/${kbId}/actual-bid-parse/tasks${qs ? `?${qs}` : ""}`,
  );
}

export async function getActualBidParseTask(
  kbId: string,
  parseTaskId: string,
): Promise<ActualBidParseTaskDetail> {
  return apiRequest<ActualBidParseTaskDetail>(`/api/v1/kbs/${kbId}/actual-bid-parse/tasks/${parseTaskId}`);
}

export async function getActualBidDocument(
  kbId: string,
  documentId: string,
): Promise<ActualBidDocument> {
  return apiRequest<ActualBidDocument>(`/api/v1/kbs/${kbId}/actual-bid-parse/documents/${documentId}`);
}

export async function getActualBidDocumentTree(
  kbId: string,
  documentId: string,
): Promise<DocumentTreeResult> {
  return apiRequest<DocumentTreeResult>(`/api/v1/kbs/${kbId}/actual-bid-parse/documents/${documentId}/tree`);
}

export async function listActualBidCandidates(
  kbId: string,
  params?: { page?: number; page_size?: number; import_id?: string; source_doc_id?: string; status?: string },
): Promise<CandidateListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.source_doc_id) search.set("source_doc_id", params.source_doc_id);
  if (params?.status) search.set("status", params.status);
  const qs = search.toString();
  return apiRequest<CandidateListResult>(`/api/v1/kbs/${kbId}/candidates${qs ? `?${qs}` : ""}`);
}

export async function confirmActualBidParseTask(
  kbId: string,
  parseTaskId: string,
  payload: ConfirmActualBidParsePayload,
): Promise<ConfirmActualBidParseResult> {
  return apiRequest<ConfirmActualBidParseResult>(
    `/api/v1/kbs/${kbId}/actual-bid-parse/tasks/${parseTaskId}/confirm`,
    {
      method: "POST",
      body: payload,
    },
  );
}
