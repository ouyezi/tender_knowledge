import type { Key } from "react";
import type {
  CreateKnowledgeChunkRequest,
  NodePreview,
  PrefillResult,
  TreeNode,
} from "../../services/knowledgeChunks";

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Pydantic `date` fields reject empty/invalid strings — normalize before create. */
export function normalizeOptionalDate(value: string | null | undefined): string | null {
  if (value == null) return null;
  const trimmed = value.trim();
  if (!trimmed || !ISO_DATE_RE.test(trimmed)) return null;
  return trimmed;
}

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

export function buildPrefillMetadata(params: {
  preview: NodePreview;
  documentName?: string;
  sourceType?: string;
}): Record<string, unknown> {
  const { preview, documentName, sourceType } = params;
  const byType: Record<string, number> = {};
  for (const asset of preview.assets ?? []) {
    byType[asset.asset_type] = (byType[asset.asset_type] ?? 0) + 1;
  }
  return {
    source_type: sourceType ?? "bid",
    file_name: documentName,
    chapter_title: preview.title,
    catalog_path: preview.catalog_path,
    content_type_hint: preview.content_type,
    asset_summary: {
      total: preview.assets?.length ?? 0,
      by_type: byType,
      has_table: Boolean(byType.table),
      has_image: Boolean(byType.image),
    },
  };
}

export function buildAutoCreatePayload(params: {
  docId: string;
  nodeId: string;
  preview: NodePreview;
  prefill: PrefillResult;
  documentName?: string;
  sourceType?: string;
}): CreateKnowledgeChunkRequest {
  const { docId, nodeId, preview, prefill, documentName } = params;
  const catalogTitle = preview.catalog_path?.[preview.catalog_path.length - 1]?.title;

  return {
    doc_id: docId,
    primary_node_id: nodeId,
    title: prefill.title?.trim() || preview.title?.trim() || catalogTitle?.trim() || "(未命名节点)",
    content: preview.content_md,
    summary: prefill.summary ?? null,
    knowledge_type: prefill.knowledge_type,
    content_type: prefill.content_type || preview.content_type,
    file_name: prefill.file_name || documentName || null,
    catalog_path: preview.catalog_path,
    block_type_code: prefill.block_type_code,
    application_type_code: prefill.application_type_code,
    business_line_codes: prefill.business_line_codes ?? [],
    tags: prefill.tags ?? [],
    regions: prefill.regions ?? [],
    qualification_info: prefill.qualification_info ?? null,
    expire_date: normalizeOptionalDate(prefill.expire_date),
    status: prefill.status,
    is_template: Boolean(prefill.is_template),
    template_type: prefill.template_type ?? null,
    security_level: prefill.security_level,
    owner: null,
    review_status: prefill.review_status,
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
