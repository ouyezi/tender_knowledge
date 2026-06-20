import { apiRequest } from "./apiClient";

export interface EntryDocument {
  doc_id: string;
  document_name: string;
  import_id: string;
  source_type?: string;
  updated_at: string | null;
}

export interface TreeNode {
  node_id: string;
  title: string;
  parent_id: string | null;
  level: number;
  sort_order: number;
  ingested: boolean;
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
  source_type?: string;
  file_name?: string | null;
  project_name?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  catalog_path?: CatalogPathItem[];
  parent_id?: number | null;
  need_parent_context?: boolean;
  quote_mode?: string;
  category?: string;
  tags?: string[];
  products?: string[];
  industries?: string[];
  customer_types?: string[];
  regions?: string[];
  issue_date?: string | null;
  expire_date?: string | null;
  status?: string;
  is_template?: boolean;
  template_type?: string | null;
  variables?: Record<string, unknown>[];
  is_immutable?: boolean;
  exclusion_rules?: Record<string, unknown>[];
  retrieval_weight?: number;
  security_level?: string;
  owner?: string | null;
  review_status?: string;
  winning_flag?: boolean;
  edit_distance_avg?: number | null;
  force?: boolean;
}

export interface KnowledgeChunkListItem {
  id: number;
  title: string;
  version: string;
  category: string;
  knowledge_type: string;
  status: string;
  token_count: number;
  update_time: string | null;
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
  source_type: string;
  project_name: string | null;
  page_start: number | null;
  page_end: number | null;
  char_start: number | null;
  char_end: number | null;
  catalog_path: CatalogPathItem[];
  primary_node_id: string;
  parent_id: number | null;
  need_parent_context: boolean;
  quote_mode: string;
  category: string;
  tags: string[];
  products: string[];
  industries: string[];
  customer_types: string[];
  regions: string[];
  issue_date: string | null;
  expire_date: string | null;
  status: string;
  is_template: boolean;
  template_type: string | null;
  variables: Record<string, unknown>[];
  is_immutable: boolean;
  exclusion_rules: Record<string, unknown>[];
  retrieval_weight: number;
  security_level: string;
  owner: string | null;
  review_status: string;
  winning_flag: boolean;
  edit_distance_avg: number | null;
  content_hash: string | null;
  token_count: number;
  has_children: boolean;
  children_count: number;
  create_time: string | null;
  update_time: string | null;
  embedding_status: string;
  previous_version: PreviousVersionSummary | null;
  assets: ChunkAssetDetail[];
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
  source_type: string;
  category: string;
  status: string;
  security_level: string;
  review_status: string;
  quote_mode: string;
  template_type: string | null;
  tags: string[];
  products: string[];
  industries: string[];
  customer_types: string[];
  regions: string[];
  issue_date: string | null;
  expire_date: string | null;
  is_template: boolean;
  winning_flag: boolean;
  file_name?: string;
  project_name?: string;
  warnings?: string[];
}

export interface PagedKnowledgeChunks {
  items: KnowledgeChunkListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListKnowledgeChunksParams {
  category?: string;
  knowledge_type?: string;
  source_type?: string;
  status?: string;
  products?: string[];
  industries?: string[];
  regions?: string[];
  tags?: string[];
  security_level?: string;
  is_template?: boolean;
  winning_flag?: boolean;
  review_status?: string;
  issue_date_from?: string;
  issue_date_to?: string;
  expire_date_from?: string;
  expire_date_to?: string;
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
  if (params?.category) search.set("category", params.category);
  if (params?.knowledge_type) search.set("knowledge_type", params.knowledge_type);
  if (params?.source_type) search.set("source_type", params.source_type);
  if (params?.status) search.set("status", params.status);
  appendList(search, "products", params?.products);
  appendList(search, "industries", params?.industries);
  appendList(search, "regions", params?.regions);
  appendList(search, "tags", params?.tags);
  if (params?.security_level) search.set("security_level", params.security_level);
  if (params?.is_template !== undefined) search.set("is_template", String(params.is_template));
  if (params?.winning_flag !== undefined) search.set("winning_flag", String(params.winning_flag));
  if (params?.review_status) search.set("review_status", params.review_status);
  if (params?.issue_date_from) search.set("issue_date_from", params.issue_date_from);
  if (params?.issue_date_to) search.set("issue_date_to", params.issue_date_to);
  if (params?.expire_date_from) search.set("expire_date_from", params.expire_date_from);
  if (params?.expire_date_to) search.set("expire_date_to", params.expire_date_to);
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
): Promise<NodePreview> {
  return apiRequest<NodePreview>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/entry/documents/${docId}/nodes/${nodeId}/preview`,
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
