import { apiRequest } from "./apiClient";

export type KBStatus = "active" | "inactive" | string;

export interface KnowledgeBase {
  id: string;
  name: string;
  status: KBStatus;
  created_at?: string;
  updated_at?: string;
}

interface RawKnowledgeBase {
  kb_id: string;
  name: string;
  status: KBStatus;
  created_at?: string;
  updated_at?: string;
}

interface CreateKBPayload {
  name: string;
  clone_from_kb_id?: string;
}

function mapKb(raw: RawKnowledgeBase): KnowledgeBase {
  return {
    id: raw.kb_id,
    name: raw.name,
    status: raw.status,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

export async function listKnowledgeBases(
  status: "active" | "inactive" = "active",
): Promise<KnowledgeBase[]> {
  const data = await apiRequest<{ items: RawKnowledgeBase[] }>(
    `/api/v1/kbs?status=${encodeURIComponent(status)}`,
    { method: "GET" },
  );
  return (data.items ?? []).map(mapKb);
}

export async function getKnowledgeBase(id: string): Promise<KnowledgeBase> {
  const data = await apiRequest<RawKnowledgeBase>(`/api/v1/kbs/${id}`, {
    method: "GET",
  });
  return mapKb(data);
}

export async function createKnowledgeBase(
  payload: CreateKBPayload,
): Promise<KnowledgeBase> {
  const data = await apiRequest<RawKnowledgeBase>("/api/v1/kbs", {
    method: "POST",
    body: payload,
  });
  return mapKb(data);
}

export async function deactivateKnowledgeBase(id: string): Promise<void> {
  await apiRequest<void>(`/api/v1/kbs/${id}/deactivate`, {
    method: "POST",
  });
}
