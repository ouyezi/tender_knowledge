import { apiRequest } from "./apiClient";
import type { OutlineNodePayload } from "./retrieval";

export interface ModuleSuggestionPayload {
  product_category_ids?: string[];
  project_type?: string;
  customer_type?: string;
  requirement_text?: string;
  requirement_context_id?: string;
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
    include_conflict_flags?: boolean;
  };
}

export interface ModuleSuggestionItem {
  suggestion_id: string;
  target_outline_node: Record<string, unknown>;
  suggested_template_chapter_ids: string[];
  suggested_ku_ids: string[];
  suggested_wiki_ids: string[];
  suggested_manual_asset_ids: string[];
  suggested_bid_outline_node_ids: string[];
  suggested_chapter_pattern_ids: string[];
  organization_hint: Record<string, unknown>;
  match_score: number;
  coverage_rate: number;
  score_detail: Record<string, number>;
  score_point_coverage: unknown[];
  rejection_risks: unknown[];
  risk_flags: Array<Record<string, unknown>>;
  hit_reason: string;
  available_ku_count: number;
  available_wiki_count: number;
  knowledge_pack_items: unknown[];
  status?: string;
  adoption_reason?: string | null;
  adopted_by?: string | null;
  adopted_at?: string | null;
  requirement_context_id?: string | null;
}

export interface ModuleSuggestionResponse {
  trace_id: string;
  module_suggestions: ModuleSuggestionItem[];
  missing_chapters: unknown[];
  latency_ms: number;
}

export async function createModuleSuggestion(
  kbId: string,
  payload: ModuleSuggestionPayload,
): Promise<ModuleSuggestionResponse> {
  return apiRequest<ModuleSuggestionResponse>(`/api/v1/kbs/${kbId}/module-suggestions`, {
    method: "POST",
    body: payload,
  });
}

export async function getModuleSuggestion(
  kbId: string,
  suggestionId: string,
): Promise<ModuleSuggestionItem & { trace_id: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/module-suggestions/${suggestionId}`);
}

export async function patchSuggestionAdoption(
  kbId: string,
  suggestionId: string,
  payload: { status: "adopted" | "rejected" | string; adoption_reason?: string },
): Promise<{ suggestion_id: string; status: string; adopted_by?: string; adopted_at?: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/module-suggestions/${suggestionId}/adoption`, {
    method: "PATCH",
    body: payload,
  });
}
