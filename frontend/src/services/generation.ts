import { apiRequest } from "./apiClient";
import type { OutlineNodePayload } from "./retrieval";

export interface UserChapterSelection {
  template_chapter_id: string;
  enabled: boolean;
  source?: string;
}

export interface ManualAssetCompliance {
  manual_asset_id: string;
  status: string;
  message?: string | null;
}

export interface CreateDraftPayload {
  requirement_context_id: string;
  suggestion_id: string;
  target_outline_node: OutlineNodePayload;
  product_category_ids?: string[];
  variable_values?: Record<string, string>;
  user_chapter_selections?: UserChapterSelection[];
  manual_asset_compliance?: ManualAssetCompliance[];
  confirm_adoption?: boolean;
  regenerate_from_draft_id?: string | null;
}

export interface GenerationTask {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  requirement_context_id?: string;
  suggestion_id?: string | null;
  target_outline_node?: OutlineNodePayload;
  draft_id?: string | null;
  snapshot_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string;
}

export interface DraftCitation {
  source_type: string;
  source_id: string;
  source_label: string;
  excerpt: string;
  ref_id?: string | null;
}

export interface DraftParagraph {
  paragraph_index: number;
  text: string;
  citations: DraftCitation[];
}

export interface ChapterDraft {
  draft_id: string;
  task_id: string;
  snapshot_id: string;
  target_outline_node: OutlineNodePayload;
  paragraphs: DraftParagraph[];
  conflict_hints: Array<Record<string, unknown>>;
  missing_material_hints: Array<Record<string, unknown>>;
  outcome_status: "pending" | "accepted" | "discarded" | string;
  version_tag: string;
  is_active: boolean;
  created_at: string;
}

export interface GenerationSnapshot {
  snapshot_id: string;
  task_id: string;
  requirement_context_id: string;
  target_outline_node: OutlineNodePayload;
  prompt_version: string;
  result_version: string;
  created_at: string;
  requirement_context_snapshot?: Record<string, unknown>;
  suggestion_id?: string | null;
  suggestion_snapshot?: Record<string, unknown>;
  used_ku_ids?: string[];
  used_wiki_ids?: string[];
  used_template_chapter_ids?: string[];
  used_manual_asset_ids?: string[];
  variable_inputs?: Record<string, string>;
  retrieval_trace_summary?: Record<string, unknown>;
  conflict_hints?: Array<Record<string, unknown>>;
  missing_material_hints?: Array<Record<string, unknown>>;
  input_priority_layers?: Record<string, unknown>;
}

export async function createDraft(kbId: string, payload: CreateDraftPayload): Promise<GenerationTask> {
  return apiRequest<GenerationTask>(`/api/v1/kbs/${kbId}/generation/drafts`, {
    method: "POST",
    body: payload,
  });
}

export async function getTask(kbId: string, taskId: string): Promise<GenerationTask> {
  return apiRequest<GenerationTask>(`/api/v1/kbs/${kbId}/generation/tasks/${taskId}`);
}

export async function getDraft(kbId: string, draftId: string): Promise<ChapterDraft> {
  return apiRequest<ChapterDraft>(`/api/v1/kbs/${kbId}/generation/drafts/${draftId}`);
}

export async function getSnapshot(kbId: string, snapshotId: string): Promise<GenerationSnapshot> {
  return apiRequest<GenerationSnapshot>(`/api/v1/kbs/${kbId}/generation/snapshots/${snapshotId}`);
}

export async function accept(kbId: string, draftId: string): Promise<{ draft_id: string; outcome_status: string; outcome_at: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/generation/drafts/${draftId}/accept`, {
    method: "POST",
    body: {},
  });
}

export async function discard(kbId: string, draftId: string): Promise<{ draft_id: string; outcome_status: string; is_active: boolean }> {
  return apiRequest(`/api/v1/kbs/${kbId}/generation/drafts/${draftId}/discard`, {
    method: "POST",
    body: {},
  });
}

export async function regenerate(
  kbId: string,
  draftId: string,
  payload: { variable_values?: Record<string, string>; user_chapter_selections?: UserChapterSelection[] },
): Promise<GenerationTask> {
  return apiRequest<GenerationTask>(`/api/v1/kbs/${kbId}/generation/drafts/${draftId}/regenerate`, {
    method: "POST",
    body: payload,
  });
}
