/**
 * Reading a list of variant positions out of whatever somebody pasted.
 *
 * Deliberately not in the component that renders the box. The box is a client
 * component and the request builder that sends these to the engine runs on the
 * server; a function shared between the two cannot carry `"use client"` with
 * it, or the server import fails at render time with "attempted to call
 * parseVariants() from the server". That was found by running it rather than
 * by reading it, which is the argument for this file existing.
 *
 * Positions come out counted from one, because that is how they were typed.
 * The conversion into the frame the engines use happens in `request.ts`,
 * through the same `zeroBased` every other coordinate goes through.
 */

/** Every position in the pasted text, in the order it was written. */
export function parseVariants(raw: string): number[] {
  const positions: number[] = [];

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    // `#` opens a comment in VCF, and its header block is all comments.
    if (!trimmed || trimmed.startsWith("#")) continue;

    // A VCF data line is `chrom pos id ref alt …` separated by tabs, so the
    // position is the second field. Anything without tabs is treated as a
    // plain list, which covers a comma list, a space-separated line and a
    // column pasted out of a spreadsheet.
    const columns = trimmed.split(/\t/);
    const source = columns.length > 2 ? (columns[1] ?? "") : trimmed;

    for (const token of source.split(/[\s,;]+/)) {
      const value = Number(token);
      // Integers only, and at least one: a coordinate of zero is somebody
      // already counting from zero, and silently accepting it would shift
      // every one of their positions by a base.
      if (Number.isFinite(value) && Number.isInteger(value) && value >= 1) {
        positions.push(value);
      }
    }
  }

  return positions;
}
