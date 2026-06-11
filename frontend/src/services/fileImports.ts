import { ApiError, apiRequest } from "./apiClient";

export type FileImportStatus =
  | "uploaded"
  | "need_confirm"
  | "confirmed"
  | "processing"
  | "completed"
  | "failed"
  | "ignored"
  | string;

export type FileType = "docx" | "pdf" | "ppt" | "xlsx" | "image" | "other" | string;

export interface FileImportListItem {
  import_id: string;
  file_name: string;
  file_type: FileType;
  file_size: number;
  file_hash: string;
  file_purpose: string | null;
  status: FileImportStatus;
  version_no: number;
  created_at: string;
  updated_at: string;
}

export interface FileImportListResult {
  items: FileImportListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListFileImportsParams {
  status?: string;
  file_purpose?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface FilePurposeSuggestion {
  suggested_purpose: string | null;
  purpose_confidence: number | null;
  suggested_product_category_ids: string[];
  suggested_chapter_taxonomy_id: string | null;
  suggestion_source: string;
  rationale: string | null;
}

export interface FileImportDetail {
  import_id: string;
  kb_id: string;
  file_name: string;
  file_type: FileType;
  file_size: number;
  file_hash: string | null;
  hash_status: string;
  storage_path: string;
  file_purpose: string | null;
  product_category_ids: string[];
  chapter_taxonomy_id: string | null;
  target_object_type: string | null;
  enter_parsing: boolean;
  status: FileImportStatus;
  parent_import_id: string | null;
  version_no: number;
  version: number;
  suggestion: FilePurposeSuggestion | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ConfirmFileImportPayload {
  expected_version: number;
  file_purpose: string;
  product_category_ids: string[];
  chapter_taxonomy_id?: string | null;
  enter_parsing?: boolean;
  target_object_type?: string | null;
}

export interface ConfirmFileImportResult {
  import_id: string;
  status: string;
  file_purpose: string | null;
  product_category_ids: string[];
  chapter_taxonomy_id: string | null;
  target_object_type: string | null;
  enter_parsing: boolean;
  version: number;
  confirmed_by: string | null;
  confirmed_at: string | null;
}

export interface IgnoreFileImportResult {
  import_id: string;
  status: string;
  target_object_type: string | null;
  enter_parsing: boolean;
  version: number;
}

export interface UploadFileImportResult {
  import_id: string;
  kb_id: string;
  file_name: string;
  file_type: FileType;
  file_size: number;
  status: FileImportStatus;
  version_no: number;
  created_at: string;
}

export interface ImportTaskItem {
  task_id: string;
  task_type: string;
  status: string;
  retry_count: number;
  log_lines: Array<{ ts: string; level: string; message: string }>;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface DownstreamEntryItem {
  entry_id: string;
  task_type: string;
  status: string;
  created_at: string | null;
}

export interface RetryImportResult {
  import_id: string;
  status: string;
  tasks_enqueued: string[];
}

export async function listFileImports(
  kbId: string,
  params: ListFileImportsParams = {},
): Promise<FileImportListResult> {
  const searchParams = new URLSearchParams();
  if (params.status) {
    searchParams.set("status", params.status);
  }
  if (params.file_purpose) {
    searchParams.set("file_purpose", params.file_purpose);
  }
  if (params.q) {
    searchParams.set("q", params.q);
  }
  if (params.page !== undefined) {
    searchParams.set("page", String(params.page));
  }
  if (params.page_size !== undefined) {
    searchParams.set("page_size", String(params.page_size));
  }

  const query = searchParams.toString();
  const path = `/api/v1/kbs/${kbId}/file-imports${query ? `?${query}` : ""}`;

  return apiRequest<FileImportListResult>(path, { method: "GET" });
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const OPERATOR_ID = "admin";

export async function uploadFile(
  kbId: string,
  file: File,
  options?: { duplicate_action?: "normal" | "skip" | "new_version"; parent_import_id?: string },
): Promise<UploadFileImportResult> {
  const formData = new FormData();
  formData.set("file", file);
  if (options?.duplicate_action) {
    formData.set("duplicate_action", options.duplicate_action);
  }
  if (options?.parent_import_id) {
    formData.set("parent_import_id", options.parent_import_id);
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/kbs/${kbId}/file-imports`, {
    method: "POST",
    headers: {
      "X-Operator-Id": OPERATOR_ID,
    },
    body: formData,
  });
  const json = (await response.json()) as
    | { data: UploadFileImportResult }
    | { error?: { code?: string; message?: string; details?: Record<string, unknown> } };
  if (!response.ok) {
    const code = "error" in json ? (json.error?.code ?? "REQUEST_FAILED") : "REQUEST_FAILED";
    const errMessage = "error" in json ? (json.error?.message ?? "Upload failed") : "Upload failed";
    const details = "error" in json ? json.error?.details : undefined;
    throw new ApiError(errMessage, code, details);
  }
  return "data" in json ? json.data : (json as UploadFileImportResult);
}

export async function getFileImport(kbId: string, importId: string): Promise<FileImportDetail> {
  return apiRequest<FileImportDetail>(`/api/v1/kbs/${kbId}/file-imports/${importId}`, {
    method: "GET",
  });
}

export async function confirmFileImport(
  kbId: string,
  importId: string,
  payload: ConfirmFileImportPayload,
): Promise<ConfirmFileImportResult> {
  return apiRequest<ConfirmFileImportResult>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}/confirm`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function ignoreFileImport(
  kbId: string,
  importId: string,
  expectedVersion: number,
  reason?: string,
): Promise<IgnoreFileImportResult> {
  return apiRequest<IgnoreFileImportResult>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}/ignore`,
    {
      method: "POST",
      body: {
        expected_version: expectedVersion,
        reason,
      },
    },
  );
}

export async function listTasks(kbId: string, importId: string): Promise<{ items: ImportTaskItem[] }> {
  return apiRequest<{ items: ImportTaskItem[] }>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}/tasks`,
    {
      method: "GET",
    },
  );
}

export async function listDownstreamEntries(
  kbId: string,
  importId: string,
): Promise<{ items: DownstreamEntryItem[] }> {
  return apiRequest<{ items: DownstreamEntryItem[] }>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}/downstream-entries`,
    {
      method: "GET",
    },
  );
}

export async function retryImport(
  kbId: string,
  importId: string,
  scope: "all" | "classify" | "route" = "all",
): Promise<RetryImportResult> {
  return apiRequest<RetryImportResult>(`/api/v1/kbs/${kbId}/file-imports/${importId}/retry`, {
    method: "POST",
    body: { scope },
  });
}
