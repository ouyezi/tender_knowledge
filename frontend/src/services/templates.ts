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

export interface LLMProgress {
  total_chunks: number;
  completed_chunks: number;
  failed_chunks: number;
  degraded_to_rule: number;
  batch_size?: number;
}

export interface BlockClassificationFields {
  suggested_product_category_ids?: string[];
  suggested_chapter_taxonomy_id?: string | null;
  suggested_knowledge_type?: string | null;
  classification_confidence?: number;
  suggestion_source?: "rule" | "llm" | "hybrid";
  classification_rationale?: string | null;
}

export interface TemplateParseTaskListItem {
  parse_task_id: string;
  import_id: string;
  template_id: string | null;
  status: string;
  parse_strategy?: string | null;
  error_message?: string | null;
  retry_count?: number;
  llm_progress?: LLMProgress | null;
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
  params?: { page?: number; page_size?: number; status?: string },
): Promise<TemplateLibraryListResult> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  if (params?.status) search.set("status", params.status);
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

export interface ParseSuggestionChapterNode extends BlockClassificationFields {
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

export interface ParseSuggestionMaterial extends BlockClassificationFields {
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

export interface ParseSuggestionCandidate extends BlockClassificationFields {
  temp_id: string;
  chapter_temp_id?: string | null;
  candidate_type?: string;
  title?: string;
  summary?: string;
  content_preview?: string;
  product_category_ids?: string[];
  knowledge_type?: string | null;
  accepted?: boolean;
  chapter_taxonomy_id?: string | null;
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
  llm_progress?: LLMProgress | null;
  started_at: string | null;
  finished_at: string | null;
  suggestion: ParseSuggestion | null;
  structure_diff?: TemplateStructureDiff | null;
}

export interface TemplateStructureDiff {
  diff_id: string;
  parse_task_id: string;
  template_id: string;
  status: string;
  diff_payload: {
    summary?: { added: number; removed: number; changed: number };
    suggested_tree?: ParseSuggestionChapterNode[];
  } | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string;
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
    product_category_ids?: string[];
    chapter_taxonomy_id?: string | null;
    knowledge_type?: string | null;
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

export async function applyParseDiff(
  kbId: string,
  parseTaskId: string,
  payload: { diff_id?: string | null },
): Promise<{ parse_task_id: string; template_id: string; structure_diff: TemplateStructureDiff }> {
  return apiRequest(`/api/v1/kbs/${kbId}/template-parse/tasks/${parseTaskId}/diff/apply`, {
    method: "POST",
    body: payload,
  });
}

export async function rejectParseDiff(
  kbId: string,
  parseTaskId: string,
  payload: { diff_id?: string | null },
): Promise<{ parse_task_id: string; template_id: string; structure_diff: TemplateStructureDiff }> {
  return apiRequest(`/api/v1/kbs/${kbId}/template-parse/tasks/${parseTaskId}/diff/reject`, {
    method: "POST",
    body: payload,
  });
}

export interface ChapterTreeNode {
  template_chapter_id: string;
  parent_id: string | null;
  title: string;
  level: number;
  sort_order: number;
  chapter_taxonomy_id: string | null;
  product_category_ids: string[];
  required: boolean;
  is_fixed_section: boolean;
  ignored: boolean;
  status: string;
  bound_material_ids: string[];
  variable_ids: string[];
  rule_ids: string[];
  children: ChapterTreeNode[];
}

export interface ChapterTreeResult {
  template_id: string;
  roots: ChapterTreeNode[];
  audit_id?: string;
}

export interface ChapterBatchUpdatePayload {
  expected_template_updated_at?: string;
  chapters: Array<{
    template_chapter_id: string;
    parent_id: string | null;
    title: string;
    level: number;
    sort_order: number;
    chapter_taxonomy_id: string | null;
    product_category_ids: string[];
    required: boolean;
    is_fixed_section: boolean;
    ignored: boolean;
  }>;
}

export async function getTemplateChapterTree(
  kbId: string,
  templateId: string,
): Promise<ChapterTreeResult> {
  return apiRequest<ChapterTreeResult>(`/api/v1/kbs/${kbId}/templates/${templateId}/chapters/tree`);
}

export async function batchUpdateTemplateChapters(
  kbId: string,
  templateId: string,
  payload: ChapterBatchUpdatePayload,
): Promise<ChapterTreeResult> {
  return apiRequest<ChapterTreeResult>(`/api/v1/kbs/${kbId}/templates/${templateId}/chapters/batch-update`, {
    method: "POST",
    body: payload,
  });
}

export interface TemplateMaterialItem {
  material_id: string;
  template_chapter_id: string | null;
  material_type: string;
  title: string | null;
  summary: string | null;
  content: string | null;
  import_id: string | null;
  storage_path: string | null;
  product_category_ids: string[];
  extract_as_candidate: boolean;
  status: string;
  updated_at: string;
}

export interface TemplateVariableItem {
  variable_id: string;
  template_chapter_id: string | null;
  variable_key: string;
  display_name: string | null;
  value_type: string;
  required: boolean;
  default_value: string | null;
  description: string | null;
  options: string[];
  status: string;
  updated_at: string;
}

export interface TemplateRuleItem {
  rule_id: string;
  template_chapter_id: string | null;
  rule_type: string;
  condition: Record<string, unknown> | null;
  action: string;
  message: string | null;
  status: string;
  updated_at: string;
}

export interface PublishResult {
  status: string;
  version: string;
  version_no: number;
  snapshot_id: string;
  published_at: string;
  template_id?: string;
  template_library_id?: string;
}

export async function publishTemplate(kbId: string, templateId: string): Promise<PublishResult> {
  return apiRequest<PublishResult>(`/api/v1/kbs/${kbId}/templates/${templateId}/publish`, {
    method: "POST",
    body: {},
  });
}

export async function publishTemplateLibrary(
  kbId: string,
  templateLibraryId: string,
  payload?: { cascade_templates?: boolean; version_note?: string | null },
): Promise<PublishResult> {
  return apiRequest<PublishResult>(
    `/api/v1/kbs/${kbId}/template-libraries/${templateLibraryId}/publish`,
    {
      method: "POST",
      body: payload ?? { cascade_templates: true },
    },
  );
}

type ListResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export async function listTemplateMaterials(
  kbId: string,
  templateId: string,
): Promise<ListResult<TemplateMaterialItem>> {
  return apiRequest<ListResult<TemplateMaterialItem>>(
    `/api/v1/kbs/${kbId}/templates/${templateId}/materials?page_size=200`,
  );
}

export async function createTemplateMaterial(
  kbId: string,
  templateId: string,
  payload: {
    template_chapter_id?: string | null;
    material_type: string;
    title?: string;
    summary?: string;
    content?: string;
    import_id?: string | null;
    storage_path?: string | null;
    product_category_ids?: string[];
    extract_as_candidate?: boolean;
  },
): Promise<TemplateMaterialItem> {
  return apiRequest<TemplateMaterialItem>(`/api/v1/kbs/${kbId}/templates/${templateId}/materials`, {
    method: "POST",
    body: payload,
  });
}

export async function updateTemplateMaterial(
  kbId: string,
  templateId: string,
  materialId: string,
  payload: Partial<{
    template_chapter_id: string | null;
    material_type: string;
    title: string | null;
    summary: string | null;
    content: string | null;
    storage_path: string | null;
    product_category_ids: string[];
    extract_as_candidate: boolean;
    status: string;
  }>,
): Promise<TemplateMaterialItem> {
  return apiRequest<TemplateMaterialItem>(
    `/api/v1/kbs/${kbId}/templates/${templateId}/materials/${materialId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function listTemplateVariables(
  kbId: string,
  templateId: string,
): Promise<ListResult<TemplateVariableItem>> {
  return apiRequest<ListResult<TemplateVariableItem>>(
    `/api/v1/kbs/${kbId}/templates/${templateId}/variables?page_size=200`,
  );
}

export async function createTemplateVariable(
  kbId: string,
  templateId: string,
  payload: {
    template_chapter_id?: string | null;
    variable_key: string;
    display_name?: string;
    value_type?: string;
    required?: boolean;
    default_value?: string;
    description?: string;
    options?: string[];
  },
): Promise<TemplateVariableItem> {
  return apiRequest<TemplateVariableItem>(`/api/v1/kbs/${kbId}/templates/${templateId}/variables`, {
    method: "POST",
    body: payload,
  });
}

export async function updateTemplateVariable(
  kbId: string,
  templateId: string,
  variableId: string,
  payload: Partial<{
    template_chapter_id: string | null;
    display_name: string | null;
    value_type: string;
    required: boolean;
    default_value: string | null;
    description: string | null;
    options: string[];
    status: string;
  }>,
): Promise<TemplateVariableItem> {
  return apiRequest<TemplateVariableItem>(
    `/api/v1/kbs/${kbId}/templates/${templateId}/variables/${variableId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function listTemplateRules(
  kbId: string,
  templateId: string,
): Promise<ListResult<TemplateRuleItem>> {
  return apiRequest<ListResult<TemplateRuleItem>>(
    `/api/v1/kbs/${kbId}/templates/${templateId}/rules?page_size=200`,
  );
}

export async function createTemplateRule(
  kbId: string,
  templateId: string,
  payload: {
    template_chapter_id?: string | null;
    rule_type: string;
    condition?: Record<string, unknown> | null;
    action?: string;
    message?: string;
  },
): Promise<TemplateRuleItem> {
  return apiRequest<TemplateRuleItem>(`/api/v1/kbs/${kbId}/templates/${templateId}/rules`, {
    method: "POST",
    body: payload,
  });
}

export async function updateTemplateRule(
  kbId: string,
  templateId: string,
  ruleId: string,
  payload: Partial<{
    template_chapter_id: string | null;
    condition: Record<string, unknown> | null;
    action: string;
    message: string | null;
    status: string;
  }>,
): Promise<TemplateRuleItem> {
  return apiRequest<TemplateRuleItem>(`/api/v1/kbs/${kbId}/templates/${templateId}/rules/${ruleId}`, {
    method: "PATCH",
    body: payload,
  });
}
