export interface ChunkEmbeddingRow {
  id: number;
  embedding_status?: string | null;
}

export interface PartitionResult {
  indexableIds: number[];
  indexingIds: number[];
}

export function partitionIndexableChunks(
  items: ChunkEmbeddingRow[],
  selectedIds: number[],
): PartitionResult {
  const byId = new Map(items.map((item) => [item.id, item]));
  const indexableIds: number[] = [];
  const indexingIds: number[] = [];

  for (const id of selectedIds) {
    const row = byId.get(id);
    if (!row) continue;
    if (row.embedding_status === "indexing") {
      indexingIds.push(id);
    } else {
      indexableIds.push(id);
    }
  }
  return { indexableIds, indexingIds };
}

export type ConcurrencyResult<T> =
  | { id: number; value: T }
  | { id: number; error: Error };

export async function runWithConcurrency<T>(
  ids: number[],
  fn: (id: number) => Promise<T>,
  limit: number,
): Promise<ConcurrencyResult<T>[]> {
  const results: ConcurrencyResult<T>[] = [];
  let cursor = 0;

  async function worker() {
    while (cursor < ids.length) {
      const current = cursor;
      cursor += 1;
      const id = ids[current];
      try {
        const value = await fn(id);
        results.push({ id, value });
      } catch (error) {
        results.push({ id, error: error as Error });
      }
    }
  }

  const workers = Array.from({ length: Math.min(limit, ids.length) }, () => worker());
  await Promise.all(workers);
  return results.sort((a, b) => a.id - b.id);
}
