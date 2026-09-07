/**
 * Roughly how many bases a pasted sequence holds.
 *
 * Its own module rather than beside the component that displays it, so it can
 * be counted against directly: the component drags in the server actions, and
 * a test that wanted both would have to pretend to be a browser.
 */

/**
 * Roughly how many bases, ignoring everything that is not one.
 *
 * A GenBank paste is not a sequence with headers on it but a record around one:
 * the LOCUS line and the feature table are full of letters that belong to words,
 * so when the text has an ORIGIN section only the lines after it are read —
 * that is where the bases live, up to the `//` terminator.
 *
 * Alignment gaps count as nothing: a `-` marks a column where this sequence has
 * no base, and counting it would measure the alignment rather than the
 * sequence. Whitespace and the position numbers GenBank writes down its ORIGIN
 * lines go the same way. U counts, as the T it behaves as.
 */
export function approximateBases(text: string): number {
  return nucleotideSequenceForMetrics(text).length;
}

function sequenceLinesForMetrics(text: string): string[] {
  const lines = text.split("\n");
  const originAt = lines.findIndex((line) => /^ORIGIN\b/i.test(line.trimStart()));
  const counted =
    originAt >= 0
      ? lines.slice(originAt + 1)
      : lines.filter((line) => !line.trimStart().startsWith(">"));
  const originEnd = counted.findIndex((line) => line.trim() === "//");
  return originEnd >= 0 ? counted.slice(0, originEnd) : counted;
}

/**
 * Extract nucleotide letters while preserving case.
 *
 * FASTA headers and GenBank metadata are deliberately excluded so lowercase
 * semantics are derived from the molecule, never from descriptive text.
 */
export function nucleotideSequenceForCase(text: string): string {
  return sequenceLinesForMetrics(text)
    .join("")
    .replace(/[^ATCGURYSWKMBDHVNatcguryswkmbdhvn]/g, "");
}

/**
 * Extract only nucleotide letters for the preview metrics.
 *
 * This intentionally follows the intake boundaries (FASTA headers and a
 * GenBank record's ORIGIN block) and excludes invalid symbols. The warning
 * layer still reports those symbols; metrics must never make them look like
 * real bases.
 */
export function nucleotideSequenceForMetrics(text: string): string {
  return nucleotideSequenceForCase(text).toUpperCase();
}

const NUCLEOTIDE_LETTERS = "ATCGURYSWKMBDHVNatcguryswkmbdhvn";

/**
 * Find characters that are not bases or safe sequence formatting.
 *
 * Alignment gaps are deliberately reported rather than silently removed:
 * deleting one changes every coordinate after the gap. This mirrors the
 * backend intake contract.
 */
export function suspiciousNucleotideCharacters(text: string): string[] {
  const lines = text.split("\n");
  const genbank = /^(?:LOCUS|ORIGIN)\b/im.test(text);
  const found: string[] = [];
  let inOrigin = false;

  for (const line of lines) {
    const trimmed = line.trimStart();
    if (trimmed.startsWith(">")) continue;
    if (genbank && trimmed.toUpperCase() === "ORIGIN") {
      inOrigin = true;
      continue;
    }
    if (genbank && inOrigin && trimmed === "//") {
      inOrigin = false;
      continue;
    }
    // GenBank feature/metadata lines are not sequence. In its ORIGIN block,
    // only a leading coordinate is formatting; a digit elsewhere is still a
    // malformed molecule and must remain visible to the user.
    if (genbank && !inOrigin) continue;
    const sequenceLine = genbank && inOrigin ? line.replace(/^\s*\d+\s+/u, "") : line;
    const matches = sequenceLine.match(new RegExp(`[^${NUCLEOTIDE_LETTERS}\\s]`, "gu"));
    if (matches) found.push(...matches);
  }

  return Array.from(new Set(found));
}

/** Remove only safe layout characters; never delete a scientific symbol. */
export function normalizeSequenceFormatting(text: string): string {
  const lines = text.split("\n");
  const cleaned: string[] = [];
  const genbank = /^(?:LOCUS|ORIGIN)\b/im.test(text);
  let inOrigin = false;

  for (const line of lines) {
    const trimmed = line.trimStart();
    if (trimmed.startsWith(">")) {
      cleaned.push(line);
    } else if (genbank && trimmed.toUpperCase() === "ORIGIN") {
      cleaned.push(line);
      inOrigin = true;
    } else if (genbank && inOrigin && trimmed === "//") {
      cleaned.push(line);
      inOrigin = false;
    } else if (genbank && inOrigin) {
      // Only a leading GenBank ORIGIN coordinate is formatting. Gaps,
      // punctuation, digits elsewhere and unknown letters intentionally remain
      // visible so the backend can reject rather than change the molecule.
      cleaned.push(line.replace(/^\s*\d+\s+/u, "").replace(/\s/gu, ""));
    } else if (!genbank) {
      // Raw/FASTA input has no coordinate grammar. Remove whitespace only;
      // digits and every other non-nucleotide symbol stay visible for repair.
      cleaned.push(line.replace(/\s/gu, ""));
    } else {
      cleaned.push(line);
    }
  }
  return cleaned.join("\n");
}
