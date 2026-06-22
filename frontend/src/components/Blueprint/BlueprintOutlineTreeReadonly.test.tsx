import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import BlueprintOutlineTreeReadonly from "./BlueprintOutlineTreeReadonly";
import type { BlueprintNode } from "../../services/blueprints";

afterEach(() => cleanup());

const nodes: BlueprintNode[] = [
  {
    node_title: "技术方案",
    node_level: 1,
    importance_level: "required",
    content_description: "写架构设计",
    tender_response_hint: "响应评分点",
    children: [],
  },
];

describe("BlueprintOutlineTreeReadonly", () => {
  it("selects node when clicking tree title", async () => {
    const user = userEvent.setup();
    const onSelectNode = vi.fn();
    render(
      <BlueprintOutlineTreeReadonly nodes={nodes} onSelectNode={onSelectNode} />,
    );
    await user.click(screen.getByText(/技术方案/));
    expect(onSelectNode).toHaveBeenCalledWith("0");
  });

  it("copies title via copy icon without changing selection callback order", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    const onSelectNode = vi.fn();
    render(
      <BlueprintOutlineTreeReadonly nodes={nodes} onSelectNode={onSelectNode} />,
    );
    await user.click(screen.getByRole("button", { name: "复制章节标题" }));
    expect(writeText).toHaveBeenCalledWith("技术方案");
    expect(onSelectNode).not.toHaveBeenCalled();
  });
});
