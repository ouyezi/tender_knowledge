import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CandidateConfirmPage from "./CandidateConfirmPage";

const mockGetCandidate = vi.fn();

vi.mock("../../services/candidates", () => ({
  getCandidate: (...args: unknown[]) => mockGetCandidate(...args),
  patchCandidate: vi.fn(),
  confirmCandidate: vi.fn(),
  retryPublishCandidate: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock("../../layout/KBContext", () => ({
  useKBContext: () => ({ selectedKbId: "kb-test-001" }),
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/candidates/confirm/doc_test"]}>
      <Routes>
        <Route path="/candidates/confirm/:candidateId" element={<CandidateConfirmPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CandidateConfirmPage", () => {
  beforeEach(() => {
    mockGetCandidate.mockReset();
    mockGetCandidate.mockResolvedValue({
      candidate_id: "doc_test",
      source_channel: "document",
      title: "测试候选",
      content: "正文",
      summary: "摘要",
      status: "pending",
      source_trace: { file_name: "demo.docx" },
    });
  });

  it("switches publish fields when confirm_as changes", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("正文")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: "发布" }));
    expect(screen.getByLabelText("knowledge_type")).toBeInTheDocument();

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText("手册资产"));

    await waitFor(() => {
      expect(screen.getByLabelText("asset_type")).toBeInTheDocument();
    });
    expect(screen.queryByLabelText("knowledge_type")).not.toBeInTheDocument();
  });
});
