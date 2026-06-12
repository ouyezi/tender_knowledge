import { apiRequest } from "./apiClient";

export interface TemplateLibraryListItem {
  template_library_id: string;
  library_name: string;
  library_type: string;
  status: string;
  version: string;
  updated_at: string;
}

export interface TemplateLibraryListResult {
  items: TemplateLibraryListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface TemplateParseTaskListItem {
  parse_task_id: string;
  import_id: string;
  template_id: string | null;
  status: string;
  parse_strategy?: string | null;
  error_message?: string | null;
  retry_count?: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
}

export interface TemplateParseTaskListResult {
  items: TemplateParseTaskListItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function listTemplateLibraries(
  kbId: string,
  params?: { page?: number; page_size?: number },
): Promise<TemplateLibraryListResult> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<TemplateLibraryListResult>(
    `/api/v1/kbs/${kbId}/template-libraries${qs ? `?${qs}` : ""}`,
  );
}

export async function listParseTasks(
  kbId: string,
  params?: { page?: number; page_size?: number; import_id?: string; status?: string },
): Promise<TemplateParseTaskListResult> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.status) search.set("status", params.status);
  const qs = search.toString();
  return apiRequest<TemplateParseTaskListResult>(
    `/api/v1/kbs/${kbId}/template-parse/tasks${qs ? `?${qs}` : ""}`,
  );
}

export interface ParseSuggestionChapterNode {
  temp_id: string;
  parent_temp_id: string | null;
  title: string;
  level: number;
  sort_order: number;
  chapter_taxonomy_id: string | null;
  product_category_ids: string[];
  required: boolean;
  is_fixed_section: boolean;
  ignored: boolean;
  needs_manual_review?: boolean;
}

export interface ParseSuggestionMaterial {
  temp_id: string;
  chapter_temp_id: string | null;
  material_type: string;
  title?: string;
  summary?: string;
  content?: string;
  product_category_ids?: string[];
  extract_as_candidate?: boolean;
  ignored?: boolean;
}

export interface ParseSuggestionCandidate {
  temp_id: string;
  chapter_temp_id?: string | null;
  candidate_type?: string;
  title?: string;
  summary?: string;
  content_preview?: string;
  product_category_ids?: string[];
  accepted?: boolean;
}

export interface ParseSuggestion {
  suggestion_id: string;
  suggested_library_id: string | null;
  suggested_library_name: string | null;
  suggested_product_category_ids: string[];
  suggested_chapter_tree: ParseSuggestionChapterNode[];
  suggested_materials: ParseSuggestionMaterial[];
  suggested_candidates: ParseSuggestionCandidate[];
  suggestion_source: string;
  rationale: string | null;
}

export interface ParseTaskDetail {
  parse_task_id: string;
  import_id: string;
  template_id: string | null;
  status: string;
  parse_strategy: string | null;
  log_lines: Array<{ ts: string; level: string; message: string }>;
  error_message: string | null;
  retry_count: number;
  started_at: string | null;
  finished_at: string | null;
  suggestion: ParseSuggestion | null;
}

export interface ConfirmParsePayload {
  template_library_id: string | null;
  create_library?: { library_name: string; library_type: string } | null;
  template_name: string;
  template_type: string;
  product_category_ids: string[];
  chapters: ParseSuggestionChapterNode[];
  materials: ParseSuggestionMaterial[];
  candidate_actions: Array<{
    temp_id: string;
    candidate_type: string;
    accepted: boolean;
  }>;
}

export interface ConfirmParseResult {
  parse_task_id: string;
  template_id: string;
  template_library_id: string | null;
  status: string;
  structure_locked_at: string;
  candidate_stubs_created: number;
}

export async function getParseTask(kbId: string, parseTaskId: string): Promise<ParseTaskDetail> {
  return apiRequest<ParseTaskDetail>(`/api/v1/kbs/${kbId}/template-parse/tasks/${parseTaskId}`);
}

export async function getParseSuggestion(
  kbId: string,
  parseTaskId: string,
): Promise<ParseSuggestion> {
  return apiRequest<ParseSuggestion>(`/api/v1/kbs/${kbId}/template-parse/tasks/${parseTaskId}/suggestion`);
}

export async function confirmParseTask(
  kbId: string,
  parseTaskId: string,
  payload: ConfirmParsePayload,
): Promise<ConfirmParseResult> {
  return apiRequest<ConfirmParseResult>(
    `/api/v1/kbs/${kbId}/template-parse/tasks/${parseTaskId}/confirm`,
    {
      method: "POST",
      body: payload,
    },
  );
}
