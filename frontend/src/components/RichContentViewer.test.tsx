import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RichContentViewer from "./RichContentViewer";

describe("RichContentViewer", () => {
  it("renders plain text fallback", () => {
    render(<RichContentViewer kbId="kb-1" content="hello world" />);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("renders blocks_v1 paragraph", () => {
    const content = JSON.stringify({
      format: "blocks_v1",
      blocks: [{ type: "paragraph", text: "段落内容" }],
    });
    render(<RichContentViewer kbId="kb-1" content={content} />);
    expect(screen.getByText("段落内容")).toBeInTheDocument();
  });

  it("renders image block with media url", () => {
    const content = JSON.stringify({
      format: "blocks_v1",
      blocks: [{ type: "image", asset_id: "asset-1" }],
    });
    render(<RichContentViewer kbId="kb-1" content={content} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", expect.stringContaining("/api/v1/kbs/kb-1/media/asset-1"));
  });
});
