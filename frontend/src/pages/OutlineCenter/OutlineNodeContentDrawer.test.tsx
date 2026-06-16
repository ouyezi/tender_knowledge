import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import OutlineNodeContentDrawer from "./OutlineNodeContentDrawer";
import * as bidOutlines from "../../services/bidOutlines";

vi.mock("../../services/bidOutlines", () => ({
  getOutlineNodeContent: vi.fn(),
}));

describe("OutlineNodeContentDrawer", () => {
  it("renders section titles and paragraph content", async () => {
    vi.mocked(bidOutlines.getOutlineNodeContent).mockResolvedValue({
      outline_node_id: "n1",
      title: "技术方案",
      bid_outline_id: "o1",
      source_doc_id: "d1",
      sections: [
        {
          outline_node_id: "n1",
          title: "技术方案",
          level: 1,
          sort_order: 0,
          source_node_id: "s1",
          content: JSON.stringify({
            format: "blocks_v1",
            blocks: [{ type: "paragraph", text: "正文段落" }],
          }),
          has_content: true,
          empty_reason: null,
        },
        {
          outline_node_id: "n2",
          title: "子节",
          level: 2,
          sort_order: 0,
          source_node_id: null,
          content: JSON.stringify({ format: "blocks_v1", blocks: [] }),
          has_content: false,
          empty_reason: "no_source_node",
        },
      ],
    });

    render(
      <OutlineNodeContentDrawer
        open
        kbId="kb-1"
        bidOutlineId="o1"
        outlineNodeId="n1"
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("技术方案 — 章节内容")).toBeInTheDocument();
      expect(screen.getByText("正文段落")).toBeInTheDocument();
      expect(screen.getByText("子节")).toBeInTheDocument();
      expect(screen.getByText("暂无关联正文")).toBeInTheDocument();
    });
  });
});
