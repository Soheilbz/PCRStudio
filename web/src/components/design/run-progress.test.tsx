import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunJob } from "@/lib/api/types";
import { RunProgress } from "./run-progress";

const JOB: RunJob = {
  id: "job-1",
  projectId: "project-1",
  moduleId: "standard-pcr",
  engineId: "flanking-pair",
  requestFingerprint: "abc",
  label: "first pass",
  runId: null,
  status: "running",
  stage: "weighted-dispatch",
  progress: { measured: true },
  error: null,
  createdAt: "2026-09-04T08:00:00Z",
  startedAt: "2026-09-04T08:00:00Z",
  finishedAt: null,
  updatedAt: "2026-09-04T08:00:00Z",
};

describe("RunProgress", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-04T08:00:05Z"));
  });

  afterEach(() => vi.useRealTimers());

  it("shows the backend stage rather than inferring one from time", () => {
    render(<RunProgress job={JOB} />);
    expect(screen.getByText("Scientific design is running")).toBeInTheDocument();
    expect(screen.getByText("5 s")).toBeInTheDocument();

    act(() => {
      vi.setSystemTime(new Date("2026-09-04T08:02:05Z"));
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText("Scientific design is running")).toBeInTheDocument();
  });

  it("offers a real cancellation control only when supplied", async () => {
    const cancel = vi.fn();
    render(<RunProgress job={JOB} onCancel={cancel} />);
    const button = screen.getByRole("button", { name: "Cancel run" });
    button.click();
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it("reports submission before a durable job exists", () => {
    render(<RunProgress job={null} starting />);
    expect(screen.getByText("Submitting the durable run…")).toBeInTheDocument();
    expect(screen.getByText(/No synthetic percentage/)).toBeInTheDocument();
  });
});
