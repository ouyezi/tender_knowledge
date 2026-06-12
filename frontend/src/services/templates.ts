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
  params?: { page?: number; page_size?: number },
): Promise<TemplateParseTaskListResult> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<TemplateParseTaskListResult>(
    `/api/v1/kbs/${kbId}/template-parse/tasks${qs ? `?${qs}` : ""}`,
  );
}
