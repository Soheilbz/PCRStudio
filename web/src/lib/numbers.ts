/**
 * Numbers that read the same everywhere.
 *
 * Every quantity in this application is a scientific one: a base position, a
 * product size, a count of candidates that survived a filter. They were being
 * written with a bare `toLocaleString()`, which has two problems and only one
 * of them is obvious.
 *
 * The obvious one is that a bare call takes the locale of whatever machine
 * makes it. On the server that is the server's — so a page rendered in a
 * container set to `C` and hydrated in a browser set to `de-DE` produces
 * `1,200` and then `1.200` for the same number, which React reports as a
 * hydration mismatch and repaints.
 *
 * The less obvious one is that following the reader's locale is the wrong
 * answer here even when it works. A sequence coordinate is written with Western
 * digits and a comma in every journal, in every language; rendering base 1,200
 * as ۱٬۲۰۰ for a Persian reader would not be a translation of the convention,
 * it would be a departure from it. So the locale is fixed, deliberately, and
 * this comment is the record of that being a decision rather than a default.
 *
 * Prose around the number is a different question, and belongs in the interface
 * language, not here.
 */

const GROUPED = new Intl.NumberFormat("en-US");

/** A count or a coordinate, grouped in thousands. */
export function count(value: number): string {
  return GROUPED.format(value);
}

/** A count with its unit, where the unit is the same word in every language. */
export function bases(value: number): string {
  return `${GROUPED.format(value)} bp`;
}

/**
 * The same, for a number that might not be there.
 *
 * These turn up wherever a position is optional — a primer that was never
 * placed has no coordinate, and the honest rendering of that is a dash rather
 * than a zero.
 */
export function maybeCount(value: number | null | undefined, fallback = "—"): string {
  return value === null || value === undefined ? fallback : GROUPED.format(value);
}
