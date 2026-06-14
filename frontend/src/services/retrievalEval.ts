import { apiRequest } from "./apiClient";

export type RetrievalFeedbackType =
  | "click"
  | "adopt"
  | "copy"
  | "add_to_draft"
  | "useful"
  | "not_useful"
  | "false_positive"
  | "false_negative";

export interface RetrievalFeedbackItem {
  feedback_id: string;
  trace_id: string;
  feedback_type: RetrievalFeedbackType;
  object_type: string | null;
  object_id: string | null;
  rank_position: number | null;
  expected_object_ids: string[];
  comment: string | null;
  filter_adjustment: Record<string, unknown> | null;
  operator_id: string | null;
  created_at: string;
}

export interface RetrievalFeedbackListResult {
  items: RetrievalFeedbackItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListRetrievalFeedbackParams {
  trace_id?: string;
  feedback_type?: RetrievalFeedbackType;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
}

export interface CreateRetrievalFeedbackPayload {
  trace_id: string;
  feedback_type: RetrievalFeedbackType;
  object_type?: string;
  object_id?: string;
  rank_position?: number;
  expected_object_ids?: string[];
  comment?: string;
  filter_adjustment?: Record<string, unknown>;
}

export interface CreateRetrievalFeedbackResult {
  feedback_id: string;
  trace_id: string;
  feedback_type: RetrievalFeedbackType;
  created_at: string;
}

export interface PromoteFeedbackPayload {
  eval_set_id: string;
  expected_object_ids?: string[];
  negative_object_ids?: string[];
}

export interface PromoteFeedbackResult {
  eval_case_id: string;
  status: string;
}

export interface RetrievalStrategyVersion {
  strategy_version_id: string;
  name: string;
  version_tag: string;
  config: Record<string, unknown>;
  embedding_config_version: string | null;
  rerank_config_version: string | null;
  prompt_config_version: string | null;
  notes: string | null;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
}

export interface RetrievalStrategyListResult {
  items: RetrievalStrategyVersion[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateRetrievalStrategyPayload {
  name: string;
  version_tag: string;
  config?: Record<string, unknown>;
  embedding_config_version?: string | null;
  rerank_config_version?: string | null;
  prompt_config_version?: string | null;
  notes?: string | null;
}

export interface RetrievalEvalSet {
  eval_set_id: string;
  name: string;
  description: string | null;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface RetrievalEvalSetListResult {
  items: RetrievalEvalSet[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateRetrievalEvalSetPayload {
  name: string;
  description?: string;
}

export interface RetrievalEvalCase {
  eval_case_id: string;
  eval_set_id: string;
  query: string;
  intent: string;
  filters: Record<string, unknown>;
  expected_object_ids: string[];
  negative_object_ids: string[];
  product_category_ids: string[];
  chapter_taxonomy_ids: string[];
  created_from: string;
  source_feedback_id: string | null;
  status: string;
  confirmed_at: string | null;
  confirmed_by: string | null;
  created_at: string;
}

export interface RetrievalEvalCaseListResult {
  items: RetrievalEvalCase[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateRetrievalEvalCasePayload {
  query: string;
  intent: string;
  filters?: Record<string, unknown>;
  expected_object_ids?: string[];
  negative_object_ids?: string[];
  product_category_ids?: string[];
  chapter_taxonomy_ids?: string[];
}

export interface CreateRetrievalEvalRunPayload {
  eval_set_id: string;
  strategy_version_id: string;
  baseline_strategy_version_id?: string;
  k?: number;
  metrics?: string[];
}

export interface RetrievalEvalRun {
  eval_run_id: string;
  status: string;
  eval_set_id: string;
  strategy_version_id: string;
  baseline_strategy_version_id: string | null;
  metrics: Record<string, number> | null;
  comparison_metrics: Record<string, number> | null;
  started_at: string | null;
  finished_at: string | null;
  triggered_by: string | null;
}

export async function listRetrievalFeedback(
  kbId: string,
  params?: ListRetrievalFeedbackParams,
): Promise<RetrievalFeedbackListResult> {
  const search = new URLSearchParams();
  if (params?.trace_id) search.set("trace_id", params.trace_id);
  if (params?.feedback_type) search.set("feedback_type", params.feedback_type);
  if (params?.from) search.set("from", params.from);
  if (params?.to) search.set("to", params.to);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<RetrievalFeedbackListResult>(
    `/api/v1/kbs/${kbId}/retrieval/feedback${qs ? `?${qs}` : ""}`,
  );
}

export async function createRetrievalFeedback(
  kbId: string,
  payload: CreateRetrievalFeedbackPayload,
): Promise<CreateRetrievalFeedbackResult> {
  return apiRequest<CreateRetrievalFeedbackResult>(`/api/v1/kbs/${kbId}/retrieval/feedback`, {
    method: "POST",
    body: payload,
  });
}

export async function promoteFeedbackToEvalCase(
  kbId: string,
  feedbackId: string,
  payload: PromoteFeedbackPayload,
): Promise<PromoteFeedbackResult> {
  return apiRequest<PromoteFeedbackResult>(
    `/api/v1/kbs/${kbId}/retrieval/feedback/${feedbackId}/promote-to-eval-case`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function listRetrievalStrategies(
  kbId: string,
  params?: { is_active?: boolean; page?: number; page_size?: number },
): Promise<RetrievalStrategyListResult> {
  const search = new URLSearchParams();
  if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<RetrievalStrategyListResult>(
    `/api/v1/kbs/${kbId}/retrieval/strategies${qs ? `?${qs}` : ""}`,
  );
}

export async function createRetrievalStrategy(
  kbId: string,
  payload: CreateRetrievalStrategyPayload,
): Promise<RetrievalStrategyVersion> {
  return apiRequest<RetrievalStrategyVersion>(`/api/v1/kbs/${kbId}/retrieval/strategies`, {
    method: "POST",
    body: payload,
  });
}

export async function activateRetrievalStrategy(
  kbId: string,
  strategyVersionId: string,
): Promise<RetrievalStrategyVersion> {
  return apiRequest<RetrievalStrategyVersion>(
    `/api/v1/kbs/${kbId}/retrieval/strategies/${strategyVersionId}/activate`,
    {
      method: "POST",
      body: {},
    },
  );
}

export async function listRetrievalEvalSets(
  kbId: string,
  params?: { page?: number; page_size?: number },
): Promise<RetrievalEvalSetListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<RetrievalEvalSetListResult>(
    `/api/v1/kbs/${kbId}/retrieval/eval/sets${qs ? `?${qs}` : ""}`,
  );
}

export async function createRetrievalEvalSet(
  kbId: string,
  payload: CreateRetrievalEvalSetPayload,
): Promise<RetrievalEvalSet> {
  return apiRequest<RetrievalEvalSet>(`/api/v1/kbs/${kbId}/retrieval/eval/sets`, {
    method: "POST",
    body: payload,
  });
}

export async function listRetrievalEvalCases(
  kbId: string,
  evalSetId: string,
  params?: { status?: string; created_from?: string; page?: number; page_size?: number },
): Promise<RetrievalEvalCaseListResult> {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.created_from) search.set("created_from", params.created_from);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<RetrievalEvalCaseListResult>(
    `/api/v1/kbs/${kbId}/retrieval/eval/sets/${evalSetId}/cases${qs ? `?${qs}` : ""}`,
  );
}

export async function createRetrievalEvalCase(
  kbId: string,
  evalSetId: string,
  payload: CreateRetrievalEvalCasePayload,
): Promise<RetrievalEvalCase> {
  return apiRequest<RetrievalEvalCase>(`/api/v1/kbs/${kbId}/retrieval/eval/sets/${evalSetId}/cases`, {
    method: "POST",
    body: payload,
  });
}

export async function confirmRetrievalEvalCase(
  kbId: string,
  evalCaseId: string,
  confirmedBy: string,
): Promise<RetrievalEvalCase> {
  return apiRequest<RetrievalEvalCase>(`/api/v1/kbs/${kbId}/retrieval/eval/cases/${evalCaseId}/confirm`, {
    method: "POST",
    body: { confirmed_by: confirmedBy },
  });
}

export async function rejectRetrievalEvalCase(
  kbId: string,
  evalCaseId: string,
): Promise<RetrievalEvalCase> {
  return apiRequest<RetrievalEvalCase>(`/api/v1/kbs/${kbId}/retrieval/eval/cases/${evalCaseId}/reject`, {
    method: "POST",
    body: {},
  });
}

export async function createRetrievalEvalRun(
  kbId: string,
  payload: CreateRetrievalEvalRunPayload,
): Promise<RetrievalEvalRun> {
  return apiRequest<RetrievalEvalRun>(`/api/v1/kbs/${kbId}/retrieval/eval/runs`, {
    method: "POST",
    body: payload,
  });
}

export async function getRetrievalEvalRun(
  kbId: string,
  evalRunId: string,
): Promise<RetrievalEvalRun> {
  return apiRequest<RetrievalEvalRun>(`/api/v1/kbs/${kbId}/retrieval/eval/runs/${evalRunId}`);
}
