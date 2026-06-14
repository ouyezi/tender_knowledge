import { apiRequest } from "./apiClient";

export type CandidateAuditAction =
  | "edit"
  | "publish"
  | "publish_failed"
  | "ignore"
  | "merge"
  | "split"
  | "batch_confirm"
  | "batch_reject";

export interface CandidateAuditLogItem {
  audit_id: string;
  candidate_id: string;
  batch_id?: string | null;
  action: CandidateAuditAction;
  operator_id: string;
  trace_id: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface CandidateAuditLogListResult {
  items: CandidateAuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListCandidateAuditLogsParams {
  candidate_id?: string;
  import_id?: string;
  batch_id?: string;
  action?: CandidateAuditAction;
  operator_id?: string;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
}

export async function listCandidateAuditLogs(
  kbId: string,
  params?: ListCandidateAuditLogsParams,
): Promise<CandidateAuditLogListResult> {
  const search = new URLSearchParams();
  if (params?.candidate_id) search.set("candidate_id", params.candidate_id);
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.batch_id) search.set("batch_id", params.batch_id);
  if (params?.action) search.set("action", params.action);
  if (params?.operator_id) search.set("operator_id", params.operator_id);
  if (params?.from) search.set("from", params.from);
  if (params?.to) search.set("to", params.to);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<CandidateAuditLogListResult>(
    `/api/v1/kbs/${kbId}/candidate-audit-logs${qs ? `?${qs}` : ""}`,
  );
}

export async function getCandidateAuditLog(
  kbId: string,
  auditId: string,
): Promise<CandidateAuditLogItem> {
  return apiRequest<CandidateAuditLogItem>(`/api/v1/kbs/${kbId}/candidate-audit-logs/${auditId}`);
}
