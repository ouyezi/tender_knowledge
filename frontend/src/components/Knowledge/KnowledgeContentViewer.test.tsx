import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import KnowledgeContentViewer from "./KnowledgeContentViewer";

afterEach(() => cleanup());

describe("KnowledgeContentViewer", () => {
  it("renders markdown heading in preview mode by default", () => {
    render(
      <KnowledgeContentViewer
        contentMd={"# 章节标题\n\n正文段落"}
        assets={[]}
        sectionCharStart={0}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "章节标题" })).toBeInTheDocument();
    expect(screen.getByText("正文段落")).toBeInTheDocument();
  });

  it("switches to source mode and shows raw markdown", async () => {
    const user = userEvent.setup();
    render(<KnowledgeContentViewer contentMd={"# 标题"} assets={[]} sectionCharStart={0} />);
    await user.click(screen.getByTitle("源码"));
    expect(screen.getByText("# 标题")).toBeInTheDocument();
  });

  it("renders markdown table with empty header cells without duplicate keys", () => {
    render(
      <KnowledgeContentViewer
        contentMd={"| | 列一 | 列二 |\n| --- | --- | --- |\n| A | 1 | 2 |"}
        assets={[]}
        sectionCharStart={0}
      />,
    );
    expect(screen.getByText("列一")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
