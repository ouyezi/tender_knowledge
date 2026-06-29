import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listKnowledgeTaxonomy,
  type KnowledgeTaxonomyDimension,
  type KnowledgeTaxonomyItem,
} from "../services/knowledgeTaxonomy";

const taxonomyCache = new Map<KnowledgeTaxonomyDimension, KnowledgeTaxonomyItem[]>();
const taxonomyInflight = new Map<KnowledgeTaxonomyDimension, Promise<KnowledgeTaxonomyItem[]>>();

async function loadTaxonomy(
  dimension: KnowledgeTaxonomyDimension,
  force = false,
): Promise<KnowledgeTaxonomyItem[]> {
  if (!force) {
    const cached = taxonomyCache.get(dimension);
    if (cached) {
      return cached;
    }
  } else {
    taxonomyCache.delete(dimension);
  }

  const inflight = taxonomyInflight.get(dimension);
  if (inflight) {
    return inflight;
  }

  const request = listKnowledgeTaxonomy(dimension)
    .then((items) => {
      taxonomyCache.set(dimension, items);
      return items;
    })
    .finally(() => {
      taxonomyInflight.delete(dimension);
    });

  taxonomyInflight.set(dimension, request);
  return request;
}

export function resetKnowledgeTaxonomyCache(): void {
  taxonomyCache.clear();
  taxonomyInflight.clear();
}

export function useKnowledgeTaxonomy(dimension: KnowledgeTaxonomyDimension) {
  const [items, setItems] = useState<KnowledgeTaxonomyItem[]>(() => taxonomyCache.get(dimension) ?? []);
  const [loading, setLoading] = useState(!taxonomyCache.has(dimension));
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(
    async (force = false): Promise<void> => {
      setLoading(true);
      try {
        const next = await loadTaxonomy(dimension, force);
        setItems(next);
        setError(null);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    },
    [dimension],
  );

  useEffect(() => {
    if (taxonomyCache.has(dimension)) {
      setItems(taxonomyCache.get(dimension) ?? []);
      setLoading(false);
      return;
    }
    void refresh();
  }, [dimension, refresh]);

  const codeToLabel = useMemo(() => {
    return items.reduce<Record<string, string>>((acc, item) => {
      acc[item.code] = item.label;
      return acc;
    }, {});
  }, [items]);

  return { items, loading, error, refresh, codeToLabel };
}
