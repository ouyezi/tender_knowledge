import type { Key } from "react";
import type {
  CreateKnowledgeChunkRequest,
  NodePreview,
  PrefillResult,
  TreeNode,
} from "../../services/knowledgeChunks";

export function collectCheckedNodeIds(nodes: TreeNode[], checkedKeys: Key[]): string[] {
  const checkedSet = new Set(checkedKeys.map(String));
  const result: string[] = [];

  function walk(ns: TreeNode[]) {
    for (const node of ns) {
      if (checkedSet.has(node.node_id)) {
        result.push(node.node_id);
      }
      if (node.children?.length) {
        walk(node.children);
      }
    }
  }

  walk(nodes);
  return result;
}

export function buildAutoCreatePayload(params: {
  docId: string;
  nodeId: string;
  preview: NodePreview;
  prefill: PrefillResult;
  documentName?: string;
  sourceType?: string;
}): CreateKnowledgeChunkRequest {
  const { docId, nodeId, preview, prefill, documentName, sourceType } = params;

  return {
    doc_id: docId,
    primary_node_id: nodeId,
    title: prefill.title || preview.title || "",
    content: preview.content_md,
    summary: prefill.summary ?? null,
    knowledge_type: prefill.knowledge_type,
    content_type: prefill.content_type || preview.content_type,
    source_type: prefill.source_type ?? sourceType,
    file_name: prefill.file_name || documentName || null,
    project_name: prefill.project_name ?? null,
    page_start: preview.page_start ?? null,
    page_end: preview.page_end ?? null,
    char_start: preview.char_start ?? null,
    char_end: preview.char_end ?? null,
    catalog_path: preview.catalog_path,
    parent_id: null,
    need_parent_context: false,
    quote_mode: prefill.quote_mode,
    category: prefill.category,
    tags: prefill.tags ?? [],
    products: prefill.products ?? [],
    industries: prefill.industries ?? [],
    customer_types: prefill.customer_types ?? [],
    regions: prefill.regions ?? [],
    issue_date: prefill.issue_date ?? null,
    expire_date: prefill.expire_date ?? null,
    status: prefill.status,
    is_template: Boolean(prefill.is_template),
    template_type: prefill.template_type ?? null,
    variables: [],
    is_immutable: false,
    exclusion_rules: [],
    retrieval_weight: 1,
    security_level: prefill.security_level,
    owner: null,
    review_status: prefill.review_status,
    winning_flag: Boolean(prefill.winning_flag),
    edit_distance_avg: null,
  };
}

export async function withRetry<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (firstError) {
    try {
      return await fn();
    } catch {
      throw firstError;
    }
  }
}
