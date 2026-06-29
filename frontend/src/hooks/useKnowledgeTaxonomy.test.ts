import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listKnowledgeTaxonomy, type KnowledgeTaxonomyItem } from "../services/knowledgeTaxonomy";
import { resetKnowledgeTaxonomyCache, useKnowledgeTaxonomy } from "./useKnowledgeTaxonomy";

vi.mock("../services/knowledgeTaxonomy", () => ({
  listKnowledgeTaxonomy: vi.fn(),
}));

const mockListKnowledgeTaxonomy = vi.mocked(listKnowledgeTaxonomy);

const MOCK_ITEMS: KnowledgeTaxonomyItem[] = [
  {
    code: "qualification_document",
    dimension: "block_type",
    parent_code: null,
    label: "资质文件",
    label_en: null,
    level: 1,
    sort_order: 10,
    is_active: true,
  },
];

describe("useKnowledgeTaxonomy", () => {
  beforeEach(() => {
    resetKnowledgeTaxonomyCache();
    mockListKnowledgeTaxonomy.mockReset();
  });

  it("loads taxonomy data once and reuses module cache", async () => {
    mockListKnowledgeTaxonomy.mockResolvedValue(MOCK_ITEMS);

    const first = renderHook(() => useKnowledgeTaxonomy("block_type"));
    await waitFor(() => expect(first.result.current.loading).toBe(false));
    expect(first.result.current.items).toEqual(MOCK_ITEMS);
    expect(mockListKnowledgeTaxonomy).toHaveBeenCalledTimes(1);

    const second = renderHook(() => useKnowledgeTaxonomy("block_type"));
    await waitFor(() => expect(second.result.current.loading).toBe(false));
    expect(second.result.current.items).toEqual(MOCK_ITEMS);
    expect(mockListKnowledgeTaxonomy).toHaveBeenCalledTimes(1);
  });

  it("reloads when refresh is called with force=true", async () => {
    mockListKnowledgeTaxonomy
      .mockResolvedValueOnce(MOCK_ITEMS)
      .mockResolvedValueOnce([{ ...MOCK_ITEMS[0], label: "资质文件-更新" }]);

    const { result } = renderHook(() => useKnowledgeTaxonomy("block_type"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items[0]?.label).toBe("资质文件");

    await act(async () => {
      await result.current.refresh(true);
    });

    expect(result.current.items[0]?.label).toBe("资质文件-更新");
    expect(mockListKnowledgeTaxonomy).toHaveBeenCalledTimes(2);
  });
});
