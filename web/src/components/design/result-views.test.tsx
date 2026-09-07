/**
 * The four new result views, rendered against real API responses.
 *
 * The fixtures are captured from a running API, so what is being checked is
 * that the component and the worker agree — not that the component agrees with
 * a hand-written object somebody wrote while looking at the component.
 *
 * What each test asserts is the one number that view exists to put in front of
 * somebody. That is deliberate: a render test that only checks the component
 * does not throw passes just as happily when the headline figure is missing,
 * and a missing headline is the failure mode that matters here. A probe view
 * that renders everything except how far the probe melts above its primers has
 * lost the only thing that decides whether the assay works.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import junctionFixture from "@/lib/api/__fixtures__/historical/gibson-assembly__pre-e5510-orderability-contract.json";
import historicalLoopSetFixture from "@/lib/api/__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json";
import historicalProbeFixture from "@/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
import mutagenicFixture from "@/lib/api/__fixtures__/historical/site-directed-mutagenesis__pre-q5-orderability-contract.json";
import singleFixture from "@/lib/api/__fixtures__/historical/sequencing-primer__pre-explicit-read-envelope.json";
import discriminatingFixture from "@/lib/api/__fixtures__/historical/tetra-primer-arms__pre-orderability-contract.json";
import tilingFixture from "@/lib/api/__fixtures__/historical/tiled-scheme__pre-orderability-contract.json";
import {
  discriminatingResultSchema,
  junctionResultSchema,
  loopSetResultSchema,
  mutagenicResultSchema,
  probeResultSchema,
  singleResultSchema,
  tilingResultSchema,
} from "@/lib/api/types";
import type { DesignResult } from "@/lib/api/types";

import { DiscriminatingResultView } from "./discriminating-result";
import { SelectionVerdict } from "./design-result";
import { JunctionResultView } from "./junction-result";
import { LoopSetResultView } from "./loop-set-result";
import { MutagenicResultView } from "./mutagenic-result";
import { ProbeResultView } from "./probe-result";
import { PrimerMatrix } from "./primer-matrix";
import { SingleResultView } from "./single-result";
import { TilingResultView } from "./tiling-result";

describe("the probe view", () => {
  const result = probeResultSchema.parse(historicalProbeFixture);
  const first = result.assays[0];
  if (!first) throw new Error("the captured response has no assay in it");

  it("leads with how far the probe melts above its primers", () => {
    render(<ProbeResultView result={result} />);
    // The mechanism: the probe is destroyed rather than extended, so it has to
    // be bound before the polymerase arrives.
    const separation = first.probe.above_primers;
    expect(screen.getAllByText(new RegExp(`\\+${separation}`)).length).toBeGreaterThan(0);
  });

  it("shows all three oligos, probe last and marked", () => {
    render(<ProbeResultView result={result} />);
    for (const sequence of [first.left.sequence, first.right.sequence, first.probe.sequence]) {
      expect(screen.getAllByText(sequence).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("Probe").length).toBeGreaterThan(0);
  });

  it("fails closed for a historical successful result that predates orderability", () => {
    render(<ProbeResultView result={result} />);
    expect(screen.getByText("Diagnostic design — do not order")).toBeInTheDocument();
    expect(screen.getByText("historical-result-orderability-not-recorded")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /download .* spreadsheet/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /copy .* names and sequences/i }),
    ).not.toBeInTheDocument();
  });

  it("says which reaction the temperatures were measured in", () => {
    render(<ProbeResultView result={result} />);
    expect(screen.getAllByText(/same reaction/i).length).toBeGreaterThan(0);
  });
});

describe("the candidate matrix", () => {
  it("uses the effective pair bound and the pipeline dimer watch line", () => {
    const pair = {
      left: { tm: 60 },
      right: { tm: 61 },
      product_size: 100,
      annealing_temperature: 60,
      score: 80,
      tm_difference: 2.5,
      cross_dimer_dg: -5.5,
    } as DesignResult["pairs"][number];

    const { rerender } = render(
      <PrimerMatrix
        pairs={[pair]}
        selectedRank={1}
        tmPairMaxDifference={2}
        onSelectPair={() => undefined}
      />,
    );

    expect(screen.getByText("2.5")).toHaveClass("text-warning");
    // -5.5 is above the shared -6.0 watch line and must not be coloured as a
    // warning merely because the old UI used a different -5.0 boundary.
    expect(screen.getByText("-5.5")).not.toHaveClass("text-destructive");

    rerender(
      <PrimerMatrix
        pairs={[pair]}
        selectedRank={1}
        tmPairMaxDifference={2}
        crossDimerThreshold={-5}
        onSelectPair={() => undefined}
      />,
    );
    expect(screen.getByText("-5.5")).toHaveClass("text-destructive");
  });

  it("uses native sortable controls and exposes the active sort direction", () => {
    const pairs = [
      {
        left: { tm: 60 },
        right: { tm: 61 },
        product_size: 140,
        annealing_temperature: 60,
        score: 70,
        tm_difference: 1,
        cross_dimer_dg: -4.5,
      },
      {
        left: { tm: 59 },
        right: { tm: 60 },
        product_size: 90,
        annealing_temperature: 59,
        score: 82,
        tm_difference: 1,
        cross_dimer_dg: -4,
      },
    ] as DesignResult["pairs"];

    render(<PrimerMatrix pairs={pairs} selectedRank={1} onSelectPair={() => undefined} />);

    const pairColumn = screen.getByRole("columnheader", { name: /Pair #/i });
    expect(pairColumn).toHaveAttribute("aria-sort", "ascending");
    const pairSortButton = within(pairColumn).getByRole("button", { name: /Pair #/i });
    fireEvent.click(pairSortButton);
    expect(pairColumn).toHaveAttribute("aria-sort", "descending");

    const scoreColumn = screen.getByRole("columnheader", { name: /Score/i });
    expect(scoreColumn).toHaveAttribute("aria-sort", "none");
    fireEvent.click(within(scoreColumn).getByRole("button", { name: /Score/i }));
    expect(scoreColumn).toHaveAttribute("aria-sort", "ascending");
    expect(pairColumn).toHaveAttribute("aria-sort", "none");
  });
});

describe("the single-primer view", () => {
  const result = singleResultSchema.parse(singleFixture);
  const first = result.primers[0];
  if (!first) throw new Error("the captured response has no primer in it");
  const read = result.read;
  if (!read) throw new Error("the captured response has no read window");

  it("leads with how far the target is rather than with a melting temperature", () => {
    render(<SingleResultView result={result} />);
    // Placement is the design here: a primer that is perfect by every
    // thermodynamic measure and far from its target is a wasted reaction.
    const reaches = first.reaches;
    expect(screen.getAllByText(String(reaches)).length).toBeGreaterThan(0);
  });

  it("shows the window the primer had to sit in", () => {
    render(<SingleResultView result={result} />);
    expect(screen.getByText(/Sequencing placement envelope/)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`${read.nearest}.{1,3}${read.furthest}`)),
    ).toBeInTheDocument();
  });

  it("reports nothing about a product, because there is no partner", () => {
    render(<SingleResultView result={result} />);
    expect(screen.queryByText(/product size/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/cross.dimer/i)).not.toBeInTheDocument();
  });
});

describe("the mutagenic view", () => {
  const result = mutagenicResultSchema.parse(mutagenicFixture);
  const first = result.pairs[0];
  if (!first) throw new Error("the captured response has no pair in it");

  it("shows both melting temperatures, not only the flattering one", () => {
    render(<MutagenicResultView result={result} />);
    const { melting } = first;
    expect(screen.getAllByText(`${melting.on_template} °C`).length).toBeGreaterThan(0);
    expect(screen.getAllByText(`${melting.on_product} °C`).length).toBeGreaterThan(0);
  });

  it("keeps screening Tm separate from the Q5 annealing-temperature decision", () => {
    render(<MutagenicResultView result={result} />);
    expect(screen.getAllByText(/NEBaseChanger \/ named protocol/i)).toHaveLength(
      result.pairs.length,
    );
    expect(screen.queryByText(/set the block by/i)).not.toBeInTheDocument();
  });

  it("shows the sequence before and after the edit", () => {
    render(<MutagenicResultView result={result} />);
    expect(screen.getByText(result.edit!.was)).toBeInTheDocument();
    expect(screen.getByText(result.edit!.becomes)).toBeInTheDocument();
  });

  it("fails closed for the historical pre-Q5/orderability capture", () => {
    render(<MutagenicResultView result={result} />);
    expect(screen.getByText("historical-result-orderability-not-recorded")).toBeInTheDocument();
    expect(screen.queryByText(/What to order/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/standard non-phosphorylated primers are acceptable/i),
    ).not.toBeInTheDocument();
  });
});

describe("the tiling view", () => {
  const result = tilingResultSchema.parse(tilingFixture);

  it("reports coverage as the headline", () => {
    render(<TilingResultView result={result} />);
    expect(screen.getByText(`${result.coverage.percent}%`)).toBeInTheDocument();
  });

  it("shows which tube every amplicon goes in", () => {
    render(<TilingResultView result={result} />);
    const pools = Object.keys(result.pools);
    expect(pools.length).toBeGreaterThan(1);
    for (const pool of pools) {
      expect(screen.getAllByText(`Pool ${Number(pool) + 1}`).length).toBeGreaterThan(0);
    }
  });

  it("fails closed for the historical pre-orderability scheme capture", () => {
    render(<TilingResultView result={result} />);
    expect(screen.getByText("historical-result-orderability-not-recorded")).toBeInTheDocument();
    expect(screen.queryByText(/What to order/i)).not.toBeInTheDocument();
  });

  it("names any stretch it could not cover", () => {
    render(<TilingResultView result={result} />);
    if (result.gaps.length === 0) {
      // Nothing to show, and nothing claiming there was.
      expect(screen.queryByText(/nothing could be placed over/)).not.toBeInTheDocument();
      return;
    }
    expect(screen.getByText(/nothing could be placed over/)).toBeInTheDocument();
    for (const gap of result.gaps) {
      // The span it covers and the reason, not a bare number that could be any
      // other figure on the page.
      expect(
        screen.getAllByText(
          (_, element) =>
            element?.tagName === "P" &&
            (element.textContent ?? "").includes(`(${gap.bases} bases)`),
        ).length,
      ).toBeGreaterThan(0);
      expect(screen.getAllByText(new RegExp(gap.why.slice(0, 30))).length).toBeGreaterThan(0);
    }
  });
});

describe("the assembly view", () => {
  const result = junctionResultSchema.parse(junctionFixture);
  const tailed = result.primers.find((primer) => primer.tail);
  if (!tailed) throw new Error("the captured response has no tailed primer");

  it("shows a tailed primer's two temperatures with which is which", () => {
    render(<JunctionResultView result={result} />);
    // The mistake this view exists to prevent: a block set by the whole
    // oligo's temperature amplifies nothing in the first cycle.
    expect(screen.getAllByText(/Annealing-core screening Tm/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not a setting/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(`${tailed.anneals.tm} °C`).length).toBeGreaterThan(0);
  });

  it("shows which tube each oligo belongs to", () => {
    // Two primers carrying the same join must not share a reaction.
    render(<JunctionResultView result={result} />);
    for (const fragment of Object.keys(result.tubes)) {
      expect(screen.getAllByText(new RegExp(`tube.*${fragment}`, "i")).length).toBeGreaterThan(0);
    }
  });

  it("names the joining chemistry, which has no default", () => {
    render(<JunctionResultView result={result} />);
    expect(screen.getAllByText(new RegExp(result.method.name)).length).toBeGreaterThan(0);
  });

  it("fails closed for the historical pre-named-protocol/orderability capture", () => {
    render(<JunctionResultView result={result} />);
    expect(screen.getByText("historical-result-orderability-not-recorded")).toBeInTheDocument();
    expect(screen.queryByText(/What to order/i)).not.toBeInTheDocument();
  });
});

describe("the genotyping view", () => {
  const result = discriminatingResultSchema.parse(discriminatingFixture);

  it("says what each allele is actually discriminated by", () => {
    render(<DiscriminatingResultView result={result} />);
    // Two primers and two temperatures look identical whether the assay
    // discriminates or not, so this is the sentence that carries the result.
    for (const how of Object.values(result.discrimination)) {
      const wanted =
        how.rests_on === "terminus"
          ? /Design relies on the variant-base mismatch/
          : how.rests_on === "second mismatch"
            ? /Design relies on a proposed second mismatch/
            : /No supported discrimination proposal/;
      expect(screen.getAllByText(wanted).length).toBeGreaterThan(0);
    }
  });

  it("says whether the variant is a transition or a transversion", () => {
    // It decides whether a blocking terminal mismatch exists at all.
    render(<DiscriminatingResultView result={result} />);
    expect(screen.getAllByText(result.variant.kind).length).toBeGreaterThan(0);
  });

  it("shows the mismatch pair each 3-prime end makes", () => {
    render(<DiscriminatingResultView result={result} />);
    for (const how of Object.values(result.discrimination)) {
      expect(screen.getAllByText(how.terminus).length).toBeGreaterThan(0);
    }
  });
});

describe("the loop-set view", () => {
  const result = loopSetResultSchema.parse(historicalLoopSetFixture);
  const entry = result.sets[0];
  if (!entry) throw new Error("the captured response has no set in it");

  it("names the parameter set and where it came from", () => {
    render(<LoopSetResultView result={result} />);
    expect(screen.getAllByText(new RegExp(result.parameter_set.name)).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(new RegExp(result.parameter_set.chosen_from.slice(0, 20))).length,
    ).toBeGreaterThan(0);
  });

  it("labels every one of the eight regions", () => {
    render(<LoopSetResultView result={result} />);
    for (const region of entry.regions) {
      expect(screen.getAllByText(region.name).length).toBeGreaterThan(0);
    }
  });

  it("quotes a composite's binding half rather than the whole molecule", () => {
    render(<LoopSetResultView result={result} />);
    const composites = entry.oligos.filter((oligo) => oligo.composite);
    expect(composites.length).toBe(2);
    for (const oligo of composites) {
      expect(
        screen.getAllByText(new RegExp(`binds at ${oligo.anneals!.tm}`)).length,
      ).toBeGreaterThan(0);
    }
    // Once per composite across every set rendered, not just the first.
    const everywhere = result.sets.flatMap((one) => one.oligos.filter((oligo) => oligo.composite));
    expect(screen.getAllByText(/not a cycler setting/i).length).toBe(everywhere.length);
  });

  it("shows the reaction is held rather than cycled", () => {
    render(<LoopSetResultView result={result} />);
    expect(
      screen.getAllByText(/Historical saved temperature field:.*65 °C/i).length,
    ).toBeGreaterThan(0);
  });
});

describe("order exports respect historical orderability", () => {
  /*
   * Historical captures may contain sequences without the read envelope,
   * protocol identity, or orderability verdict needed to safely hand them to a
   * supplier. Those views must fail closed. The loop-set capture retains a
   * complete order sheet and therefore keeps both export paths.
   *
   * The fixtures are captured API responses, so this protects the boundary
   * between diagnostic migration evidence and orderable current designs.
   */
  const views = [
    [
      "junction",
      <JunctionResultView key="j" result={junctionResultSchema.parse(junctionFixture)} />,
    ],
    [
      "loop set",
      <LoopSetResultView key="l" result={loopSetResultSchema.parse(historicalLoopSetFixture)} />,
    ],
    [
      "mutagenic",
      <MutagenicResultView key="m" result={mutagenicResultSchema.parse(mutagenicFixture)} />,
    ],
    ["single", <SingleResultView key="s" result={singleResultSchema.parse(singleFixture)} />],
    ["tiling", <TilingResultView key="t" result={tilingResultSchema.parse(tilingFixture)} />],
    [
      "discriminating",
      <DiscriminatingResultView
        key="d"
        result={discriminatingResultSchema.parse(discriminatingFixture)}
      />,
    ],
  ] as const;

  for (const [name, element] of views) {
    it(`${name} respects the orderability boundary`, () => {
      render(element);
      const download = screen.queryAllByRole("button", { name: /download .* spreadsheet/i });
      const copy = screen.queryAllByRole("button", { name: /copy .* names and sequences/i });
      if (name === "loop set") {
        expect(download.length).toBeGreaterThan(0);
        expect(copy.length).toBeGreaterThan(0);
      } else {
        expect(download).toHaveLength(0);
        expect(copy).toHaveLength(0);
      }
    });
  }
});

describe("the selection verdict", () => {
  /*
   * The funnel the pair search kept, in the shape `considerationSchema`
   * declares. No captured fixture for this engine exists yet, so it is written
   * here — against the schema's type, so a drift between this object and what
   * the worker sends fails to compile rather than failing quietly.
   */
  const funnel: DesignResult["considered"] = [
    {
      stage: "scan",
      considered: 1200,
      accepted: 86,
      sentence: "Every window of the template was measured.",
      rejections: [
        {
          reason: "No product size fit",
          count: 214,
          share: 0.18,
          advice: "Widen the product-size limits and run it again.",
        },
        {
          reason: "Melting temperatures too far apart",
          count: 402,
          share: 0.33,
          advice: "Loosen the Tm difference the pair is allowed.",
        },
        { reason: "Hairpin at the three-prime end", count: 97, share: 0.08, advice: "" },
        { reason: "Too little GC", count: 12, share: 0.01, advice: "" },
      ],
    },
  ];

  it("says how many candidates were considered", () => {
    render(<SelectionVerdict considered={funnel} />);
    expect(screen.getByText(/evaluating 1,200 candidates under this profile/i)).toBeInTheDocument();
  });

  it("shows the three most common reasons as chips, largest first", () => {
    render(<SelectionVerdict considered={funnel} />);

    const chips = ["402", "214", "97"].map((figure) =>
      screen.getAllByText(
        (_, element) =>
          element?.tagName === "SPAN" &&
          Boolean(element.className.includes("rounded-full")) &&
          (element.textContent?.endsWith(` · ${figure}`) ?? false),
      ),
    );
    // Every one of the top three is present…
    for (const found of chips) expect(found.length).toBeGreaterThan(0);
    // …and nothing below the cut is.
    expect(screen.queryByText(/ · 12$/)).not.toBeInTheDocument();
  });

  it("offers the worker's advice on hover where it has any", () => {
    render(<SelectionVerdict considered={funnel} />);
    const sized = screen
      .getAllByText((_, element) => element?.textContent === "No product size fit · 214")
      .find((element) => element?.tagName === "SPAN");
    expect(sized).toHaveAttribute("title", "Widen the product-size limits and run it again.");
    const hairpin = screen
      .getAllByText((_, element) => element?.textContent === "Hairpin at the three-prime end · 97")
      .find((element) => element?.tagName === "SPAN");
    expect(hairpin).not.toHaveAttribute("title");
  });

  it("renders nothing when there is no funnel to show", () => {
    const { container } = render(<SelectionVerdict considered={[]} />);
    expect(container).toBeEmptyDOMElement();

    const zero = render(
      <SelectionVerdict
        considered={[{ ...funnel[0]!, considered: 0, accepted: 0, rejections: [] }]}
      />,
    );
    expect(zero.container).toBeEmptyDOMElement();
  });
});
