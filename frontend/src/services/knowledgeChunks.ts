import { apiRequest } from "./apiClient";

export interface EntryDocument {
  doc_id: string;
  document_name: string;
  import_id: string;
  source_type?: string;
  parse_status?: "ready" | "pending" | "parsing" | "failed" | null;
  updated_at: string | null;
}

export interface TreeNode {
  node_id: string;
  title: string;
  parent_id: string | null;
  level: number;
  sort_order: number;
  ingested: boolean;
  has_blueprint?: boolean;
  children: TreeNode[];
}

export interface CatalogPathItem {
  node_id: string;
  title: string;
  level: number;
}

export interface PreviewAsset {
  id: number;
  asset_type: string;
  asset_code: string | null;
  char_start: number | null;
  char_end: number | null;
  page_start: number | null;
  page_end: number | null;
  raw_markdown: string | null;
  image_storage_url: string | null;
}

export interface NodePreview {
  title: string;
  content_md: string;
  content_type: string;
  char_start: number | null;
  char_end: number | null;
  page_start: number | null;
  page_end: number | null;
  catalog_path: CatalogPathItem[];
  assets: PreviewAsset[];
  image_ref_map?: Record<string, string>;
}

export interface PrefillRequest {
  doc_id: string;
  primary_node_id: string;
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface CreateKnowledgeChunkRequest {
  doc_id: string;
  primary_node_id: string;
  title: string;
  content: string;
  summary?: string | null;
  knowledge_type?: string;
  content_type?: string;
  file_name?: string | null;
  catalog_path?: CatalogPathItem[];
  block_type_code?: string;
  application_type_code?: string;
  business_line_codes?: string[];
  tags?: string[];
  regions?: string[];
  certificate_number?: string | null;
  certificate_date?: string | null;
  expire_date?: string | null;
  status?: string;
  is_template?: boolean;
  template_type?: string | null;
  security_level?: string;
  owner?: string | null;
  review_status?: string;
  force?: boolean;
}

export interface KnowledgeChunkListItem {
  id: number;
  title: string;
  version: string;
  block_type_code: string;
  application_type_code: string;
  business_line_codes: string[];
  block_type_label: string;
  application_type_label: string;
  business_line_labels: string[];
  is_expired: boolean;
  knowledge_type: string;
  status: string;
  embedding_status?: string;
  indexed_at?: string | null;
  token_count: number;
  update_time: string | null;
}

export interface KnowledgeChunkSearchItem extends KnowledgeChunkListItem {
  summary?: string | null;
  score: number;
  score_detail: Record<string, number>;
  highlights: Array<{ field: string; snippet: string }>;
}

export interface ChunkSearchParams {
  semantic_query?: string;
  keyword?: string;
  vector_weight?: number;
  keyword_weight?: number;
  title_vector_weight?: number;
  summary_vector_weight?: number;
  content_vector_weight?: number;
  top_k?: number;
}

export interface ChunkAssetDetail {
  id: number;
  asset_type: string;
  asset_code: string | null;
  chunk_id: number | null;
  page_start: number | null;
  page_end: number | null;
  char_start: number | null;
  char_end: number | null;
  raw_markdown: string | null;
  llm_summary: string | null;
  table_summary: string | null;
  table_schema: unknown;
  table_headers: unknown;
  table_rows: unknown;
  table_type: string | null;
  allow_row_filter: boolean | null;
  image_type: string | null;
  image_storage_url: string | null;
  image_caption: string | null;
  image_ocr_text: string | null;
  extracted_facts?: Record<string, unknown> | null;
  required_with_text: boolean | null;
  position_hint: string | null;
}

export interface PreviousVersionSummary {
  id: number;
  version: string;
  title: string;
  summary: string | null;
  update_time: string | null;
}

export interface KnowledgeChunkDetail {
  id: number;
  kb_id: string;
  knowledge_code: string;
  version: string;
  previous_version_id: number | null;
  is_latest: boolean;
  title: string;
  content: string;
  summary: string | null;
  knowledge_type: string;
  content_type: string;
  doc_id: string;
  file_name: string | null;
  catalog_path: CatalogPathItem[];
  primary_node_id: string;
  block_type_code: string;
  application_type_code: string;
  business_line_codes: string[];
  block_type_label: string;
  application_type_label: string;
  business_line_labels: string[];
  is_expired: boolean;
  tags: string[];
  regions: string[];
  certificate_number: string | null;
  certificate_date: string | null;
  expire_date: string | null;
  status: string;
  is_template: boolean;
  template_type: string | null;
  security_level: string;
  owner: string | null;
  review_status: string;
  content_hash: string | null;
  token_count: number;
  has_children: boolean;
  children_count: number;
  create_time: string | null;
  update_time: string | null;
  embedding_status: string;
  section_char_start: number | null;
  section_char_end: number | null;
  previous_version: PreviousVersionSummary | null;
  assets: ChunkAssetDetail[];
  image_ref_map?: Record<string, string>;
}

export interface CreateKnowledgeChunkResult {
  id: number;
  knowledge_code: string;
  version: string;
  previous_version_id: number | null;
  is_latest: boolean;
}

export interface PrefillResult {
  title: string;
  summary: string | null;
  knowledge_type: string;
  content_type: string;
  block_type_code: string;
  application_type_code: string;
  business_line_codes: string[];
  status: string;
  security_level: string;
  review_status: string;
  template_type: string | null;
  tags: string[];
  regions: string[];
  certificate_number: string | null;
  certificate_date: string | null;
  expire_date: string | null;
  is_template: boolean;
  file_name?: string;
  warnings?: string[];
}

export interface PagedKnowledgeChunks {
  items: KnowledgeChunkListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListKnowledgeChunksParams {
  block_type_code?: string;
  application_type_code?: string;
  business_line_codes?: string[];
  knowledge_type?: string;
  status?: string;
  regions?: string[];
  tags?: string[];
  security_level?: string;
  is_template?: boolean;
  review_status?: string;
  expire_date_from?: string;
  expire_date_to?: string;
  expired_only?: boolean;
  keyword?: string;
  page?: number;
  page_size?: number;
}

function appendList(search: URLSearchParams, key: string, values?: string[]): void {
  if (!values?.length) return;
  for (const value of values) {
    search.append(key, value);
  }
}

function buildListQuery(params?: ListKnowledgeChunksParams): string {
  const search = new URLSearchParams();
  if (params?.block_type_code) search.set("block_type_code", params.block_type_code);
  if (params?.application_type_code) search.set("application_type_code", params.application_type_code);
  appendList(search, "business_line_codes", params?.business_line_codes);
  if (params?.knowledge_type) search.set("knowledge_type", params.knowledge_type);
  if (params?.status) search.set("status", params.status);
  appendList(search, "regions", params?.regions);
  appendList(search, "tags", params?.tags);
  if (params?.security_level) search.set("security_level", params.security_level);
  if (params?.is_template !== undefined) search.set("is_template", String(params.is_template));
  if (params?.review_status) search.set("review_status", params.review_status);
  if (params?.expire_date_from) search.set("expire_date_from", params.expire_date_from);
  if (params?.expire_date_to) search.set("expire_date_to", params.expire_date_to);
  if (params?.expired_only !== undefined) search.set("expired_only", String(params.expired_only));
  if (params?.keyword) search.set("keyword", params.keyword);
  if (params?.page !== undefined) search.set("page", String(params.page));
  if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function listEntryDocuments(
  kbId: string,
): Promise<{ items: EntryDocument[] }> {
  return apiRequest<{ items: EntryDocument[] }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/entry/documents`,
  );
}

export async function getDocumentTree(
  kbId: string,
  docId: string,
): Promise<{ items: TreeNode[] }> {
  return apiRequest<{ items: TreeNode[] }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/entry/documents/${docId}/tree`,
  );
}

export async function getNodePreview(
  kbId: string,
  docId: string,
  nodeId: string,
  options?: { signal?: AbortSignal },
): Promise<NodePreview> {
  return apiRequest<NodePreview>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/entry/documents/${docId}/nodes/${nodeId}/preview`,
    { signal: options?.signal },
  );
}

export async function prefillKnowledgeChunk(
  kbId: string,
  body: PrefillRequest,
): Promise<PrefillResult> {
  return apiRequest<PrefillResult>(`/api/v1/kbs/${kbId}/knowledge-chunks/prefill`, {
    method: "POST",
    body,
  });
}

export async function createKnowledgeChunk(
  kbId: string,
  body: CreateKnowledgeChunkRequest,
  force?: boolean,
): Promise<CreateKnowledgeChunkResult> {
  return apiRequest<CreateKnowledgeChunkResult>(`/api/v1/kbs/${kbId}/knowledge-chunks`, {
    method: "POST",
    body: {
      ...body,
      force: force ?? body.force ?? false,
    },
  });
}

export async function listKnowledgeChunks(
  kbId: string,
  params?: ListKnowledgeChunksParams,
): Promise<PagedKnowledgeChunks> {
  return apiRequest<PagedKnowledgeChunks>(
    `/api/v1/kbs/${kbId}/knowledge-chunks${buildListQuery(params)}`,
  );
}

export async function getKnowledgeChunk(
  kbId: string,
  chunkId: number,
): Promise<KnowledgeChunkDetail | null> {
  return apiRequest<KnowledgeChunkDetail | null>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/${chunkId}`,
  );
}

const TERMINAL_EMBEDDING_STATUSES = new Set(["ready", "failed", "skipped"]);

export async function waitForChunkIndexComplete(
  kbId: string,
  chunkId: number,
  options?: { intervalMs?: number; maxAttempts?: number },
): Promise<KnowledgeChunkDetail | null> {
  const intervalMs = options?.intervalMs ?? 2000;
  const maxAttempts = options?.maxAttempts ?? 90;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    const detail = await getKnowledgeChunk(kbId, chunkId);
    if (!detail || TERMINAL_EMBEDDING_STATUSES.has(detail.embedding_status)) {
      return detail;
    }
  }
  return getKnowledgeChunk(kbId, chunkId);
}

export async function indexKnowledgeChunk(
  kbId: string,
  chunkId: number,
  force = false,
): Promise<{ chunk_id: number; embedding_status: string }> {
  return apiRequest<{ chunk_id: number; embedding_status: string }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/${chunkId}/index`,
    {
      method: "POST",
      body: { force },
    },
  );
}

export async function parseChunkSearchQuery(
  kbId: string,
  body: { query: string },
): Promise<{ semantic_query: string; keyword: string }> {
  return apiRequest<{ semantic_query: string; keyword: string }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/parse-search-query`,
    {
      method: "POST",
      body,
    },
  );
}

export async function searchKnowledgeChunks(
  kbId: string,
  body: ChunkSearchParams,
): Promise<{ items: KnowledgeChunkSearchItem[]; total: number }> {
  return apiRequest<{ items: KnowledgeChunkSearchItem[]; total: number }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/search`,
    {
      method: "POST",
      body,
    },
  );
}

export async function deleteKnowledgeChunk(
  kbId: string,
  chunkId: number,
): Promise<{ chunk_id: number; deleted: boolean }> {
  return apiRequest<{ chunk_id: number; deleted: boolean }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/${chunkId}`,
    { method: "DELETE" },
  );
}
