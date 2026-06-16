import { apiRequest } from "./apiClient";
import type { OutlineQualitySummary } from "./actualBidParse";

export interface BidOutlineListItem {
  bid_outline_id: string;
  source_doc_id: string;
  import_id: string;
  outline_name: string;
  outline_type: string;
  status: string;
  extract_strategy: string;
  project_name: string | null;
  customer_name: string | null;
  product_category_ids?: string[];
  node_count?: number;
  needs_manual_review?: boolean;
  outline_quality?: OutlineQualitySummary | null;
  structure_locked_at?: string | null;
  updated_at: string;
}

export interface BidOutlineListResult {
  items: BidOutlineListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface BidOutlineNode {
  outline_node_id: string;
  parent_id: string | null;
  title: string;
  level: number;
  sort_order: number;
  chapter_taxonomy_id: string | null;
  source_node_id: string | null;
  product_category_ids: string[];
  status: string;
  needs_manual_review: boolean;
  updated_at?: string;
}

export interface BidOutlineDetail extends BidOutlineListItem {
  root_nodes?: BidOutlineNode[];
}

export interface BidOutlineNodesResult {
  bid_outline_id: string;
  status: string;
  structure_locked_at: string | null;
  nodes: BidOutlineNode[];
}

export interface OutlineNodeContentSection {
  outline_node_id: string;
  title: string;
  level: number;
  sort_order: number;
  source_node_id: string | null;
  content: string;
  has_content: boolean;
  empty_reason: "no_source_node" | "empty_body" | null;
}

export interface OutlineNodeContentResult {
  outline_node_id: string;
  title: string;
  bid_outline_id: string;
  source_doc_id: string;
  sections: OutlineNodeContentSection[];
}

export interface BatchOperation {
  op: "delete" | "merge" | "reorder";
  outline_node_id?: string;
  source_node_ids?: string[];
  target_title?: string;
  parent_id?: string | null;
  ordered_node_ids?: string[];
}

export interface BidOutlineDiffItem {
  diff_id: string;
  parse_task_id: string;
  status: string;
  diff_payload: {
    added?: Array<Record<string, unknown>>;
    removed?: Array<Record<string, unknown>>;
    renamed?: Array<Record<string, unknown>>;
    moved?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  } | null;
  created_at: string;
}

export interface BidOutlineDiffListResult {
  items: BidOutlineDiffItem[];
  total?: number;
  page?: number;
  page_size?: number;
}

export async function listOutlines(
  kbId: string,
  params?: {
    page?: number;
    page_size?: number;
    import_id?: string;
    source_doc_id?: string;
    status?: string;
    q?: string;
  },
): Promise<BidOutlineListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  if (params?.import_id) search.set("import_id", params.import_id);
  if (params?.source_doc_id) search.set("source_doc_id", params.source_doc_id);
  if (params?.status) search.set("status", params.status);
  if (params?.q) search.set("q", params.q);
  const qs = search.toString();
  return apiRequest<BidOutlineListResult>(`/api/v1/kbs/${kbId}/bid-outlines${qs ? `?${qs}` : ""}`);
}

export async function getOutline(kbId: string, bidOutlineId: string): Promise<BidOutlineDetail> {
  return apiRequest<BidOutlineDetail>(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}`);
}

export async function getNodes(kbId: string, bidOutlineId: string): Promise<BidOutlineNodesResult> {
  return apiRequest<BidOutlineNodesResult>(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/nodes`);
}

export async function patchNode(
  kbId: string,
  bidOutlineId: string,
  outlineNodeId: string,
  payload: Partial<{
    title: string;
    parent_id: string | null;
    level: number;
    sort_order: number;
    chapter_taxonomy_id: string | null;
    product_category_ids: string[];
    needs_manual_review: boolean;
  }>,
): Promise<{ node: BidOutlineNode; audit_id?: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/nodes/${outlineNodeId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function batchOps(
  kbId: string,
  bidOutlineId: string,
  operations: BatchOperation[],
): Promise<{ bid_outline_id: string; nodes: BidOutlineNode[]; audit_id?: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/nodes/batch`, {
    method: "POST",
    body: { operations },
  });
}

export async function confirmOutline(
  kbId: string,
  bidOutlineId: string,
): Promise<BidOutlineDetail & { audit_id?: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/confirm`, {
    method: "POST",
    body: { status: "confirmed" },
  });
}

export async function listDiffs(
  kbId: string,
  bidOutlineId: string,
  params?: { page?: number; page_size?: number; status?: string },
): Promise<BidOutlineDiffListResult> {
  const search = new URLSearchParams();
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  if (params?.status) search.set("status", params.status);
  const qs = search.toString();
  return apiRequest<BidOutlineDiffListResult>(
    `/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/diffs${qs ? `?${qs}` : ""}`,
  );
}

export async function applyDiff(
  kbId: string,
  bidOutlineId: string,
  diffId: string,
  payload: {
    accept_added?: boolean;
    accept_removed_ids?: string[];
    accept_renamed_ids?: string[];
    accept_moved_ids?: string[];
  },
): Promise<{ bid_outline_id?: string; nodes?: BidOutlineNode[] }> {
  return apiRequest(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/diffs/${diffId}/apply`, {
    method: "POST",
    body: payload,
  });
}

export async function rejectDiff(
  kbId: string,
  bidOutlineId: string,
  diffId: string,
): Promise<{ diff_id?: string; status?: string }> {
  return apiRequest(`/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/diffs/${diffId}/reject`, {
    method: "POST",
    body: {},
  });
}

export async function getOutlineNodeContent(
  kbId: string,
  bidOutlineId: string,
  outlineNodeId: string,
): Promise<OutlineNodeContentResult> {
  return apiRequest<OutlineNodeContentResult>(
    `/api/v1/kbs/${kbId}/bid-outlines/${bidOutlineId}/nodes/${outlineNodeId}/content`,
  );
}
