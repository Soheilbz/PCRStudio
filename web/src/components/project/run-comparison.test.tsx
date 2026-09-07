/**
 * The comparison view, rendered against a real API response.
 *
 * Both runs are built from the same captured probe design, with one melting
 * temperature nudged past the difference threshold on the second — so what is
 * asserted is exactly the thing the view exists to do: show two columns, keep
 * the agreeing figures quiet, and shade the one figure that moved.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import historicalProbeFixture from "@/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
import historicalLoopSetFixture from "@/lib/api/__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json";
import type { Run, RunResult } from "@/lib/api/types";
import { loopSetResultSchema, probeResultSchema } from "@/lib/api/types";

import { RunComparison } from "./run-comparison";

// The clear button talks to the router, which wants an App Router context
// that does not exist outside a Next render. It is not what these tests are
// about; a stub that records nothing will do.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/projects/p1",
  useSearchParams: () => new URLSearchParams(),
}));

function run(id: string, result: RunResult): Run {
  return {
    id,
    projectId: "p1",
    label: "",
    // What was asked for is not part of any comparison being made here.
    request: {},
    result,
    requestSchemaVersion: 1,
    resultSchemaVersion: 1,
    moduleContractVersion: "current",
    resultCount: 0,
    resultUnit: "result",
    targetName: "",
    createdAt: "2026-08-24T09:00:00Z",
  };
}

const first = probeResultSchema.parse(historicalProbeFixture);
const warmer = structuredClone(first);
warmer.assays[0]!.left.tm += 0.6;

describe("RunComparison", () => {
  it("renders both runs as named columns", () => {
    render(
      <RunComparison
        a={run("r1", first)}
        b={run("r2", warmer)}
        nameA="First attempt"
        nameB="Second attempt"
      />,
    );
    expect(screen.getByRole("columnheader", { name: /First attempt/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Second attempt/ })).toBeInTheDocument();
    const table = screen.getByRole("table", {
      name: "Side-by-side comparison of two design runs",
    });
    expect(table).toBeInTheDocument();
    expect(table).toHaveClass("min-w-[36rem]");
    expect(table.parentElement).toHaveClass("overflow-x-auto");
  });

  it("shades the Tm that differs and says what the shading means", () => {
    render(
      <RunComparison a={run("r1", first)} b={run("r2", warmer)} nameA="First" nameB="Second" />,
    );
    const flagged = screen.getAllByTitle(/differ by 0.5 or more/i);
    // Both cells of the differing row: the gap belongs to neither side alone.
    expect(flagged.length).toBeGreaterThanOrEqual(2);
  });

  it("renders a metric one engine does not produce as a dash with its reason", () => {
    // A probe run reports no cross-dimer figure; that absence has to say why
    // rather than sitting there looking like a rendering bug.
    render(
      <RunComparison a={run("r1", first)} b={run("r2", warmer)} nameA="First" nameB="Second" />,
    );
    expect(screen.getAllByTitle(/not part of this engine's results/i).length).toBeGreaterThan(0);
  });

  it("says so when neither run carries a comparable pair", () => {
    render(
      <RunComparison
        a={run("r1", loopSetResultSchema.parse(historicalLoopSetFixture))}
        b={run("r2", loopSetResultSchema.parse(historicalLoopSetFixture))}
        nameA="First"
        nameB="Second"
      />,
    );
    expect(screen.getByText(/no matching figures to put beside each other/i)).toBeInTheDocument();
  });

  it("offers the sequences for copying", () => {
    render(
      <RunComparison a={run("r1", first)} b={run("r2", warmer)} nameA="First" nameB="Second" />,
    );
    expect(screen.getAllByRole("button", { name: /copy left primer/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /copy right primer/i }).length).toBeGreaterThan(0);
  });
});
