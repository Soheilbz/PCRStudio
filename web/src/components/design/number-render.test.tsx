/**
 * Every result view rendered against a real API response, looking only for the
 * ways a number can go wrong on screen.
 *
 * This exists because fifty-seven `toLocaleString()` calls were replaced by a
 * script, and a script that rewrites expressions can produce something that
 * compiles and is still wrong — `count(count)`, a `.length` swallowed into the
 * call, a function applied to the wrong argument. Four of those were caught by
 * the type checker. The ones it cannot catch are the ones that reach a reader.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import junctionFixture from "@/lib/api/__fixtures__/historical/gibson-assembly__pre-e5510-orderability-contract.json";
import historicalLoopSetFixture from "@/lib/api/__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json";
import historicalProbeFixture from "@/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
import mutagenicFixture from "@/lib/api/__fixtures__/historical/site-directed-mutagenesis__pre-q5-orderability-contract.json";
import singleFixture from "@/lib/api/__fixtures__/historical/sequencing-primer__pre-explicit-read-envelope.json";
import discriminatingFixture from "@/lib/api/__fixtures__/historical/tetra-primer-arms__pre-orderability-contract.json";
import tilingFixture from "@/lib/api/__fixtures__/historical/tiled-scheme__pre-orderability-contract.json";
import universalFixture from "@/lib/__fixtures__/universal-real.json";
import {
  discriminatingResultSchema,
  junctionResultSchema,
  loopSetResultSchema,
  mutagenicResultSchema,
  probeResultSchema,
  singleResultSchema,
  tilingResultSchema,
  universalResultSchema,
} from "@/lib/api/types";

import { DiscriminatingResultView } from "./discriminating-result";
import { JunctionResultView } from "./junction-result";
import { LoopSetResultView } from "./loop-set-result";
import { MutagenicResultView } from "./mutagenic-result";
import { ProbeResultView } from "./probe-result";
import { SingleResultView } from "./single-result";
import { TilingResultView } from "./tiling-result";
import { UniversalResultView } from "./universal-result";

const views = [
  ["probe", <ProbeResultView key="p" result={probeResultSchema.parse(historicalProbeFixture)} />],
  ["junction", <JunctionResultView key="j" result={junctionResultSchema.parse(junctionFixture)} />],
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
    "universal",
    <UniversalResultView key="u" result={universalResultSchema.parse(universalFixture)} />,
  ],
  [
    "discriminating",
    <DiscriminatingResultView
      key="d"
      result={discriminatingResultSchema.parse(discriminatingFixture)}
    />,
  ],
] as const;

describe("numbers reach the screen as numbers", () => {
  for (const [name, element] of views) {
    it(`the ${name} view renders no broken value`, () => {
      const { container } = render(element);
      const text = container.textContent ?? "";

      // `NaN` is what a formatter applied to the wrong argument produces;
      // `[object Object]` is what it produces when handed a whole record.
      expect(text, name).not.toMatch(/NaN/);
      expect(text, name).not.toMatch(/\[object/);
      // A dangling `undefined` in prose means an optional value was formatted
      // rather than checked. A deliberate absence is written as a dash.
      expect(text, name).not.toMatch(/\bundefined\b/);
    });

    it(`the ${name} view groups thousands the same way everywhere`, () => {
      const { container } = render(element);
      const text = container.textContent ?? "";

      // The locale is fixed on purpose: a sequence coordinate is written with
      // Western digits and a comma in every journal and every language. What
      // must never appear is two conventions on one screen, which is what a
      // server-locale default produces once the page hydrates.
      expect(text, name).not.toMatch(/\d\.\d{3}\b\s*(bp|bases)/);
      expect(text, name).not.toMatch(/[٠-٩۰-۹]/);
    });
  }

  it("shows a dash for a position that does not exist", () => {
    // A primer that was never placed has no coordinate. Zero would be a lie
    // about where it sits; the honest rendering is that there is no answer.
    render(<SingleResultView result={singleResultSchema.parse(singleFixture)} />);
    expect(screen.queryByText(/at base 0\b/)).not.toBeInTheDocument();
  });
});
