import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import ConfidenceBadge, { getConfidenceLevel } from "./ConfidenceBadge";

afterEach(() => cleanup());

describe("getConfidenceLevel", () => {
  it("returns default label for empty confidence", () => {
    expect(getConfidenceLevel(undefined)).toEqual({ label: "未评估", color: "default" });
    expect(getConfidenceLevel(null)).toEqual({ label: "未评估", color: "default" });
  });

  it("returns high level for score >= 85", () => {
    expect(getConfidenceLevel(92)).toEqual({ label: "高", color: "green" });
  });

  it("returns medium level for score in [50, 70)", () => {
    expect(getConfidenceLevel(63)).toEqual({ label: "中", color: "gold" });
  });
});

describe("ConfidenceBadge", () => {
  it("renders default state", () => {
    render(<ConfidenceBadge />);
    expect(screen.getByText("未评估")).toBeInTheDocument();
  });

  it("renders normalized score", () => {
    render(<ConfidenceBadge confidence={101} />);
    expect(screen.getByText("高 (100)")).toBeInTheDocument();
  });
});
