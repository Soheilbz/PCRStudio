/**
 * Dates, in the reader's locale rather than the server's.
 *
 * The subtlety this module exists for: `toLocaleDateString` formats using the
 * locale of whatever machine calls it. In a server component that is the
 * server, so a page rendered in Frankfurt shows German month names to a reader
 * in Tehran, and one rendered on a machine set to `C` shows none at all. The
 * reader's locale is only knowable in the browser.
 *
 * So the functions here are deliberately callable from both sides, and the
 * component that uses them (`<LocalTime>`) renders a stable, locale-free form
 * on the server and upgrades it after mount. That ordering also avoids the
 * hydration mismatch that any `Date.now()`-relative string otherwise causes:
 * the server computes "3 hours ago", the client computes "4 hours ago", and
 * React replaces the whole subtree complaining about it.
 */

/** The day something happened. */
export function onDay(iso: string, locale?: string): string {
  return new Date(iso).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** The full timestamp, for the tooltip where precision belongs. */
export function exactly(iso: string, locale?: string): string {
  return new Date(iso).toLocaleString(locale);
}

/** The locale-free form: the same characters everywhere, including on a server. */
export function isoDay(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["second", 60],
  ["minute", 60],
  ["hour", 24],
  ["day", 7],
  ["week", 4.348],
  ["month", 12],
  ["year", Number.POSITIVE_INFINITY],
];

/**
 * How long ago, in the reader's language.
 *
 * `Intl.RelativeTimeFormat` rather than hand-built strings, because the
 * previous version appended "s" for anything that was not one — which is the
 * plural rule for English and for very little else. Persian has one form,
 * Arabic has six, Russian picks between three by the last digit.
 */
export function when(iso: string, now: number, locale?: string): string {
  const format = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  let value = (new Date(iso).getTime() - now) / 1000;

  for (const [unit, step] of UNITS) {
    if (Math.abs(value) < step) return format.format(Math.round(value), unit);
    value /= step;
  }
  return format.format(Math.round(value), "year");
}
