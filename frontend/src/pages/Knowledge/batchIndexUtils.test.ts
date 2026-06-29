import { describe, expect, it } from "vitest";
import { partitionIndexableChunks, runWithConcurrency } from "./batchIndexUtils";

describe("partitionIndexableChunks", () => {
  const items = [
    { id: 1, embedding_status: "pending" },
    { id: 2, embedding_status: "indexing" },
    { id: 3, embedding_status: "ready" },
  ];

  it("splits indexable and indexing ids", () => {
    expect(partitionIndexableChunks(items, [1, 2, 3, 99])).toEqual({
      indexableIds: [1, 3],
      indexingIds: [2],
    });
  });
});

describe("runWithConcurrency", () => {
  it("limits parallel execution", async () => {
    let active = 0;
    let maxActive = 0;
    const ids = [1, 2, 3, 4];
    await runWithConcurrency(ids, async (id) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active -= 1;
      return id;
    }, 2);
    expect(maxActive).toBeLessThanOrEqual(2);
  });

  it("collects errors without stopping early", async () => {
    const results = await runWithConcurrency([1, 2], async (id) => {
      if (id === 1) throw new Error("boom");
      return id;
    }, 2);
    expect(results).toEqual([
      { id: 1, error: expect.any(Error) },
      { id: 2, value: 2 },
    ]);
  });
});
