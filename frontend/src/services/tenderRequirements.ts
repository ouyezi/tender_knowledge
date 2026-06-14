import { apiRequest } from "./apiClient";
import type { OutlineNodePayload } from "./retrieval";

export interface TenderScorePoint {
  node_ref?: string;
  text: string;
}

export interface TenderRequirementItem {
  requirement_context_id: string;
  title: string;
  status: "active" | "archived" | string;
  created_at: string;
}

export interface TenderRequirementDetail extends TenderRequirementItem {
  outline_structure: Record<string, unknown>;
  outline_nodes: OutlineNodePayload[];
  score_points: TenderScorePoint[];
  rejection_clauses: string[];
  format_requirements: string[];
  qualification_requirements: string[];
  response_clauses: string[];
  source_note: string | null;
  created_by: string | null;
  updated_at: string;
}

export interface TenderRequirementListResult {
  items: TenderRequirementDetail[];
  total: number;
  page: number;
  page_size: number;
}

export interface TenderRequirementCreatePayload {
  title: string;
  outline_structure?: Record<string, unknown>;
  outline_nodes: OutlineNodePayload[];
  score_points?: TenderScorePoint[];
  rejection_clauses?: string[];
  format_requirements?: string[];
  qualification_requirements?: string[];
  response_clauses?: string[];
  source_note?: string | null;
}

export type TenderRequirementUpdatePayload = Partial<TenderRequirementCreatePayload> & {
  status?: "active" | "archived" | string;
};

export async function createTenderRequirement(
  kbId: string,
  payload: TenderRequirementCreatePayload,
): Promise<TenderRequirementItem> {
  return apiRequest<TenderRequirementItem>(`/api/v1/kbs/${kbId}/tender-requirements`, {
    method: "POST",
    body: payload,
  });
}

export async function getTenderRequirement(
  kbId: string,
  requirementContextId: string,
): Promise<TenderRequirementDetail> {
  return apiRequest<TenderRequirementDetail>(`/api/v1/kbs/${kbId}/tender-requirements/${requirementContextId}`);
}

export async function listTenderRequirements(
  kbId: string,
  params?: { status?: string; q?: string; page?: number; page_size?: number },
): Promise<TenderRequirementListResult> {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.q) search.set("q", params.q);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<TenderRequirementListResult>(`/api/v1/kbs/${kbId}/tender-requirements${qs ? `?${qs}` : ""}`);
}

export async function updateTenderRequirement(
  kbId: string,
  requirementContextId: string,
  payload: TenderRequirementUpdatePayload,
): Promise<TenderRequirementDetail> {
  return apiRequest<TenderRequirementDetail>(`/api/v1/kbs/${kbId}/tender-requirements/${requirementContextId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function archiveTenderRequirement(kbId: string, requirementContextId: string): Promise<TenderRequirementDetail> {
  return apiRequest<TenderRequirementDetail>(`/api/v1/kbs/${kbId}/tender-requirements/${requirementContextId}/archive`, {
    method: "POST",
    body: {},
  });
}
