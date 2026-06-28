import { apiRequest } from "./apiClient";

export type WritingTechniqueUsageMode = "DIRECT" | "REFERENCE" | "EXTRACT";
export type WritingTechniqueStatus = "draft" | "published";

export interface WritingTechniquePayload {
  title: string;
  applicable_scene?: string | null;
  writing_summary?: string | null;
  applicable_sections: string[];
  tags: string[];
  usage_mode: WritingTechniqueUsageMode;
  recommended_outline?: string | null;
  writing_strategy?: string | null;
  must_include?: string | null;
  notes?: string | null;
  output_requirement?: string | null;
  checklist?: string | null;
  confidence: number;
  source_chunk_id?: number | null;
}

export interface WritingTechniqueItem extends WritingTechniquePayload {
  technique_id: string;
  kb_id: string;
  source_invalid: boolean;
  status: WritingTechniqueStatus;
  version: number;
  created_at: string | null;
  updated_at: string | null;
  embedding_status?: string;
}

export interface GenerateWritingTechniqueRequest {
  chunk_id: number;
  confirm_overwrite?: boolean;
}

export interface BindTechniqueSourceRequest {
  chunk_id: number;
}

export interface ListWritingTechniquesParams {
  keyword?: string;
  tags?: string[];
  applicable_sections?: string[];
  usage_mode?: WritingTechniqueUsageMode;
  status?: WritingTechniqueStatus;
  confidence_min?: number;
  confidence_max?: number;
  source_invalid?: boolean;
  has_source?: boolean;
  page?: number;
  page_size?: number;
}

export interface PagedWritingTechniques {
  items: WritingTechniqueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DeleteWritingTechniqueResult {
  technique_id: string;
  deleted: boolean;
}

function appendList(search: URLSearchParams, key: string, values?: string[]): void {
  if (!values?.length) return;
  for (const value of values) {
    search.append(key, value);
  }
}

function buildListQuery(params?: ListWritingTechniquesParams): string {
  const search = new URLSearchParams();
  if (params?.keyword) search.set("keyword", params.keyword);
  appendList(search, "tags", params?.tags);
  appendList(search, "applicable_sections", params?.applicable_sections);
  if (params?.usage_mode) search.set("usage_mode", params.usage_mode);
  if (params?.status) search.set("status", params.status);
  if (params?.confidence_min !== undefined) search.set("confidence_min", String(params.confidence_min));
  if (params?.confidence_max !== undefined) search.set("confidence_max", String(params.confidence_max));
  if (params?.source_invalid !== undefined) search.set("source_invalid", String(params.source_invalid));
  if (params?.has_source !== undefined) search.set("has_source", String(params.has_source));
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function generateWritingTechnique(
  kbId: string,
  body: GenerateWritingTechniqueRequest,
): Promise<WritingTechniqueItem> {
  return apiRequest<WritingTechniqueItem>(`/api/v1/kbs/${kbId}/writing-techniques/generate`, {
    method: "POST",
    body: {
      chunk_id: body.chunk_id,
      confirm_overwrite: body.confirm_overwrite ?? false,
    },
  });
}

export async function createWritingTechnique(
  kbId: string,
  body: WritingTechniquePayload,
): Promise<WritingTechniqueItem> {
  return apiRequest<WritingTechniqueItem>(`/api/v1/kbs/${kbId}/writing-techniques`, {
    method: "POST",
    body,
  });
}

export async function updateWritingTechnique(
  kbId: string,
  techniqueId: string,
  body: WritingTechniquePayload,
): Promise<WritingTechniqueItem> {
  return apiRequest<WritingTechniqueItem>(`/api/v1/kbs/${kbId}/writing-techniques/${techniqueId}`, {
    method: "PUT",
    body,
  });
}

export async function publishWritingTechnique(
  kbId: string,
  techniqueId: string,
): Promise<WritingTechniqueItem> {
  return apiRequest<WritingTechniqueItem>(
    `/api/v1/kbs/${kbId}/writing-techniques/${techniqueId}/publish`,
    { method: "PUT" },
  );
}

export async function bindWritingTechniqueSource(
  kbId: string,
  techniqueId: string,
  body: BindTechniqueSourceRequest,
): Promise<WritingTechniqueItem> {
  return apiRequest<WritingTechniqueItem>(
    `/api/v1/kbs/${kbId}/writing-techniques/${techniqueId}/bind-source`,
    {
      method: "PUT",
      body,
    },
  );
}

export async function listWritingTechniques(
  kbId: string,
  params?: ListWritingTechniquesParams,
): Promise<PagedWritingTechniques> {
  return apiRequest<PagedWritingTechniques>(
    `/api/v1/kbs/${kbId}/writing-techniques${buildListQuery(params)}`,
  );
}

export async function getWritingTechniqueBySource(
  kbId: string,
  params: { chunk_id: number },
): Promise<WritingTechniqueItem | null> {
  const search = new URLSearchParams({
    chunk_id: String(params.chunk_id),
  });
  return apiRequest<WritingTechniqueItem | null>(
    `/api/v1/kbs/${kbId}/writing-techniques/by-source?${search.toString()}`,
  );
}

export async function getWritingTechnique(
  kbId: string,
  techniqueId: string,
): Promise<WritingTechniqueItem> {
  return apiRequest<WritingTechniqueItem>(`/api/v1/kbs/${kbId}/writing-techniques/${techniqueId}`);
}

export async function deleteWritingTechnique(
  kbId: string,
  techniqueId: string,
): Promise<DeleteWritingTechniqueResult> {
  return apiRequest<DeleteWritingTechniqueResult>(
    `/api/v1/kbs/${kbId}/writing-techniques/${techniqueId}`,
    {
      method: "DELETE",
    },
  );
}
