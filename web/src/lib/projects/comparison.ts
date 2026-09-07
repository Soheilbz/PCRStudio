import type { Run, RunResult } from "@/lib/api/types";
import { count } from "@/lib/numbers";

/**
 * What two runs are compared by, and how a difference earns a highlight.
 *
 * The comparison is deliberately shallow and honest about it: it takes the
 * FIRST pair of each run — or the first assay of a probe run, the inner round
 * of a nest — and puts the same ten figures side by side. A multiplex result
 * is not saved as a run result here, and engines whose shapes carry no pair of
 * measured oligos (a tiling scheme, a loop set, a junction plan) return null
 * rather than pretending: an empty state that says so is worth more than rows
 * full of numbers read from the wrong field.
 *
 * The threshold is generous on purpose. Two runs of the same template will
 * never agree to the last decimal, and shading every 0.1-degree drift would
 * make the highlighting say nothing. Half a degree is around the resolution
 * at which an annealing temperature is actually chosen, so differences past
 * it are ones somebody might act on.
 */

/** Two figures at least this far apart get flagged in the comparison view. */
export const COMPARISON_EPSILON = 0.5;

/**
 * The figures of one run's first pair, flattened.
 *
 * Every field is present because the engines this covers all measure them;
 * the nullable ones are nullable because some of those engines genuinely do
 * not produce them, and a dash with a reason beats a zero nobody can trust.
 */
export interface PairMetrics {
  /** The closed vocabulary's name for what ran. */
  engine: string;
  /** The assay's own name, when the core sent one. */
  moduleName: string | null;
  leftSequence: string;
  rightSequence: string;
  leftTm: number;
  rightTm: number;
  gcLeft: number;
  gcRight: number;
  productSize: number | null;
  /** The heterodimer risk figure, where an engine reports one. */
  crossDimerDg: number | null;
  specificityNote: string | null;
}

/**
 * One run's first pair, in the shape above — or null when its engine does not
 * produce one this comparison knows how to read.
 */
export function firstPair(result: RunResult): PairMetrics | null {
  switch (result.engine) {
    case "flanking-pair": {
      const pair = result.pairs[0];
      if (!pair) return null;
      return {
        engine: result.engine,
        moduleName: result.assay?.name ?? null,
        leftSequence: pair.left.sequence,
        rightSequence: pair.right.sequence,
        leftTm: pair.left.tm,
        rightTm: pair.right.tm,
        gcLeft: pair.left.gc_percent,
        gcRight: pair.right.gc_percent,
        productSize: pair.product_size,
        crossDimerDg: pair.cross_dimer_dg,
        specificityNote: result.background?.note || null,
      };
    }
    case "pair-and-probe": {
      const assay = result.assays[0];
      if (!assay) return null;
      return {
        engine: result.engine,
        moduleName: result.assay?.name ?? null,
        leftSequence: assay.left.sequence,
        rightSequence: assay.right.sequence,
        leftTm: assay.left.tm,
        rightTm: assay.right.tm,
        gcLeft: assay.left.gc_percent,
        gcRight: assay.right.gc_percent,
        // A probe run scores three oligos against each other elsewhere; this
        // shape carries no cross-dimer figure, so it is a dash with a reason.
        productSize: assay.product_size,
        crossDimerDg: null,
        specificityNote: assay.off_targets?.note || result.background?.note || null,
      };
    }
    case "nested": {
      const nest = result.nests[0];
      if (!nest) return null;
      // The inner round is the one whose product ends up in the tube.
      const round = nest.inner;
      return {
        engine: result.engine,
        moduleName: result.assay?.name ?? null,
        leftSequence: round.left.sequence,
        rightSequence: round.right.sequence,
        leftTm: round.left.tm,
        rightTm: round.right.tm,
        gcLeft: round.left.gc_percent,
        gcRight: round.right.gc_percent,
        productSize: round.product_size,
        crossDimerDg: round.cross_dimer_dg,
        specificityNote: result.background?.note || null,
      };
    }
    case "outward-pair": {
      const pair = result.pairs[0];
      if (!pair) return null;
      return {
        engine: result.engine,
        moduleName: result.assay?.name ?? null,
        leftSequence: pair.left.sequence,
        rightSequence: pair.right.sequence,
        leftTm: pair.left.tm,
        rightTm: pair.right.tm,
        gcLeft: pair.left.gc_percent,
        gcRight: pair.right.gc_percent,
        // Null until the circle's length is known — the same dash the run's
        // own view shows.
        productSize: pair.product_size,
        crossDimerDg: pair.cross_dimer_dg,
        specificityNote: pair.off_targets?.note || result.background?.note || null,
      };
    }
    case "mutagenic-pair": {
      const pair = result.pairs[0];
      if (!pair) return null;
      return {
        engine: result.engine,
        moduleName: result.assay?.name ?? null,
        leftSequence: pair.forward.sequence,
        rightSequence: pair.reverse.sequence,
        // The primer meets two templates here; the plain figure is quoted, as
        // the mutagenic view itself leads with it.
        leftTm: pair.forward.tm,
        rightTm: pair.reverse.tm,
        gcLeft: pair.forward.gc_percent,
        gcRight: pair.reverse.gc_percent,
        productSize: result.edit?.product_length ?? null,
        crossDimerDg: pair.cross_dimer_dg,
        specificityNote: null,
      };
    }
    default:
      return null;
  }
}

/**
 * What to call the thing that produced a run's numbers.
 *
 * The assay's own name when the core sent one; otherwise the engine's id,
 * which is what older saved runs carry.
 */
export function engineLabel(result: RunResult): string {
  const assay = "assay" in result ? result.assay : undefined;
  return assay?.name || result.engine;
}

/* ── The rows the comparison view renders ─────────────────────────────── */

export interface ComparisonCell {
  /** Rendered as-is; null renders as an em dash beside the row's reason. */
  text: string | null;
  /**
   * The number behind the text, when there is one that can be differenced.
   * Text rows leave it null, and are never flagged.
   */
  numeric: number | null;
}

export interface ComparisonRow {
  label: string;
  /** Sequence rows render in a monospace face and carry a copy button. */
  monospace?: boolean;
  a: ComparisonCell;
  b: ComparisonCell;
  /**
   * How far apart two figures must be before either cell is shaded. Null for
   * rows that are stated rather than compared.
   */
  epsilon: number | null;
  /** Why a missing figure is missing — shown as the dash's title. */
  missingBecause: string | null;
}

const spread = (m: PairMetrics) => Math.abs(m.leftTm - m.rightTm);

/**
 * Every metric row the side-by-side view shows, both sides filled.
 *
 * When one side has no comparable pair at all, each of its cells is missing
 * for the same reason, and the reason says which: a table of dashes that all
 * blame "the engine" reads like a bug when the truth is that one column was
 * never going to have numbers in it.
 */
export function buildComparisonRows(a: PairMetrics | null, b: PairMetrics | null): ComparisonRow[] {
  if (!a && !b) return [];

  const absent =
    !a || !b
      ? "This engine does not produce a comparable primer pair."
      : "This metric is not part of this engine's results.";

  const cell = (text: string | null, numeric: number | null = null): ComparisonCell => ({
    text,
    numeric,
  });

  const row = (
    label: string,
    pick: (m: PairMetrics) => ComparisonCell,
    epsilon: number | null = null,
    monospace = false,
  ): ComparisonRow => ({
    label,
    a: a ? pick(a) : cell(null),
    b: b ? pick(b) : cell(null),
    epsilon,
    missingBecause: absent,
    monospace,
  });

  return [
    row("Left primer", (m) => cell(m.leftSequence), undefined, true),
    row("Right primer", (m) => cell(m.rightSequence), undefined, true),
    row("Left primer Tm", (m) => cell(`${m.leftTm} °C`, m.leftTm), COMPARISON_EPSILON),
    row("Right primer Tm", (m) => cell(`${m.rightTm} °C`, m.rightTm), COMPARISON_EPSILON),
    row("Tm spread", (m) => cell(`${spread(m)} °C`, spread(m)), COMPARISON_EPSILON),
    row("Left GC %", (m) => cell(`${m.gcLeft}%`, m.gcLeft), COMPARISON_EPSILON),
    row("Right GC %", (m) => cell(`${m.gcRight}%`, m.gcRight), COMPARISON_EPSILON),
    row(
      "Product size",
      (m) =>
        m.productSize === null ? cell(null) : cell(`${count(m.productSize)} bp`, m.productSize),
      COMPARISON_EPSILON,
    ),
    row(
      "Cross-dimer ΔG",
      (m) =>
        m.crossDimerDg === null ? cell(null) : cell(`${m.crossDimerDg} kcal/mol`, m.crossDimerDg),
      COMPARISON_EPSILON,
    ),
    row("Specificity", (m) => cell(m.specificityNote)),
  ];
}

/** Whether one cell of a row gets the difference shading. */
export function isFlagged(row: ComparisonRow, side: "a" | "b"): boolean {
  if (row.epsilon === null) return false;
  const mine = side === "a" ? row.a : row.b;
  const theirs = side === "a" ? row.b : row.a;
  // One side missing is not a difference: there is nothing to differ from.
  if (mine.numeric === null || theirs.numeric === null) return false;
  return Math.abs(mine.numeric - theirs.numeric) >= row.epsilon;
}

/**
 * Which runs a `?compare=` asked for — of this project's runs only, at most two.
 *
 * The membership check is the same one opening a single run applies: an id
 * outside this project's list is not looked up at all, which is what keeps the
 * parameter from being a way to ask whether somebody else's run exists.
 */
export function parseCompareIds(raw: string | undefined, runs: { id: string }[]): string[] {
  if (!raw) return [];
  const picked: string[] = [];
  for (const id of raw.split(",")) {
    const candidate = id.trim();
    if (!candidate || picked.includes(candidate)) continue;
    if (runs.some((run) => run.id === candidate)) picked.push(candidate);
    if (picked.length === 2) break;
  }
  return picked;
}

/** The type the page hands the comparison view, two whole runs. */
export type ComparedRuns = { a: Run; b: Run };
