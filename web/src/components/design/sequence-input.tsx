"use client";

/**
 * The three ways a sequence actually arrives:
 * Pasted, in a file, or as an accession somebody read in a paper.
 *
 * Enhanced with 1-click biotech sample library, live nucleotide stats (Length, GC%, MW),
 * format auto-detection, reverse-complement, and IUPAC cleaner.
 */

import {
  AlertCircle,
  AlignLeft,
  ArrowLeftRight,
  Check,
  Dna,
  FileUp,
  FlaskConical,
  Layers,
  Link2,
  Loader2,
  Sparkles,
  Type,
} from "lucide-react";
import { useMemo, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  approximateBases,
  normalizeSequenceFormatting,
  nucleotideSequenceForMetrics,
  suspiciousNucleotideCharacters,
} from "@/components/design/approximate-bases";
import { count } from "@/lib/numbers";
import { MAX_SEQUENCE_BYTES } from "@/lib/limits";
import { cn } from "@/lib/utils";
import { alignAction, consensusAction, fetchAccessionAction } from "@/lib/sequences/actions";

/** Verified examples share the same accession/checksum contract as the regression corpus. */
import { VERIFIED_SAMPLE_TEMPLATES } from "@/components/design/verified-samples";
export const SAMPLE_TEMPLATES = VERIFIED_SAMPLE_TEMPLATES;

/** Files a sequence plausibly arrives in. */
const ACCEPTED = ".fa,.fasta,.fna,.ffn,.frn,.seq,.txt,.gb,.gbk,.genbank,.embl";

const MAX_FILE_BYTES = MAX_SEQUENCE_BYTES;

type Door = "paste" | "upload" | "accession";

/** How many records the text holds, without parsing it properly. */
function recordCount(text: string): number {
  return text.split("\n").filter((line) => line.startsWith(">")).length;
}

/**
 * Roughly how many bases a pasted sequence holds, whatever it arrived as.
 *
 * The counting itself lives in `approximate-bases.ts` — this module imports the
 * server actions, so a test of the counting would have to pretend to be a
 * browser to reach it here.
 */
export { approximateBases };

/** IUPAC DNA Reverse Complement mapping */
const COMPLEMENT_MAP: Record<string, string> = {
  A: "T",
  a: "t",
  T: "A",
  t: "a",
  U: "A",
  u: "a",
  C: "G",
  c: "g",
  G: "C",
  g: "c",
  R: "Y",
  r: "y",
  Y: "R",
  y: "r",
  S: "S",
  s: "s",
  W: "W",
  w: "w",
  K: "M",
  k: "m",
  M: "K",
  m: "k",
  B: "V",
  b: "v",
  V: "B",
  v: "b",
  D: "H",
  d: "h",
  H: "D",
  h: "d",
  N: "N",
  n: "n",
};

/** Compute reverse complement of FASTA or bare sequence */
function computeReverseComplement(text: string): string {
  const lines = text.split("\n");
  const isFasta = lines.some((l) => l.startsWith(">"));

  if (!isFasta) {
    return text
      .split("")
      .reverse()
      .map((c) => COMPLEMENT_MAP[c] ?? c)
      .join("");
  }

  const resultLines: string[] = [];
  let currentHeader: string | null = null;
  let currentBases: string[] = [];

  const flush = () => {
    if (currentHeader !== null) {
      const revHeader = currentHeader.endsWith("_revcomp")
        ? currentHeader
        : `${currentHeader}_revcomp`;
      resultLines.push(revHeader);
      const combined = currentBases.join("").replace(/\s/g, "");
      const rev = combined
        .split("")
        .reverse()
        .map((c) => COMPLEMENT_MAP[c] ?? c)
        .join("");
      for (let i = 0; i < rev.length; i += 70) {
        resultLines.push(rev.slice(i, i + 70));
      }
      currentHeader = null;
      currentBases = [];
    }
  };

  for (const line of lines) {
    if (line.startsWith(">")) {
      flush();
      currentHeader = line;
    } else {
      currentBases.push(line);
    }
  }
  flush();

  return resultLines.join("\n");
}

export function SequenceInput({
  value,
  onChange,
  label,
  hint,
  rows = 10,
  placeholder,
  allowConsensus = true,
  canFetch,
  canAlign = false,
}: {
  value: string;
  onChange: (next: string) => void;
  label: string;
  hint: string;
  rows?: number;
  placeholder?: string;
  allowConsensus?: boolean;
  canFetch: boolean;
  canAlign?: boolean;
}) {
  const [door, setDoor] = useState<Door>("paste");
  const [accession, setAccession] = useState("");
  const [message, setMessage] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);
  const [pending, start] = useTransition();
  const fileInput = useRef<HTMLInputElement>(null);

  const records = recordCount(value);

  // Live Sequence Metrics
  const stats = useMemo(() => {
    if (!value.trim()) return null;
    const rawBases = nucleotideSequenceForMetrics(value);
    const len = rawBases.length;
    if (len === 0) return null;

    let gc = 0;
    for (let i = 0; i < len; i++) {
      if (rawBases[i] === "G" || rawBases[i] === "C" || rawBases[i] === "S") gc++;
    }
    const gcPct = ((gc / len) * 100).toFixed(1);
    const mwKDa = ((len * 330) / 1000).toFixed(1); // approximate average single-stranded DNA MW

    const isFasta = value.split("\n").some((line) => line.trimStart().startsWith(">"));
    const isGenBank = /^(?:LOCUS|ORIGIN)\b/im.test(value);
    const format = isFasta ? "FASTA" : isGenBank ? "GenBank" : "Raw Nucleotides";

    return { len, gcPct: Number(gcPct), mwKDa, format };
  }, [value]);

  // Check for suspicious non-IUPAC characters
  const suspiciousChars = useMemo(() => {
    if (!value) return [];
    return suspiciousNucleotideCharacters(value);
  }, [value]);

  const lookUp = () => {
    start(async () => {
      const state = await fetchAccessionAction(accession);
      if (state.error || !state.answer) {
        setMessage({ kind: "bad", text: state.error ?? "Nothing came back." });
        return;
      }
      const { records, fasta } = state.answer;
      onChange(fasta);
      const first = records[0];
      setMessage({
        kind: "ok",
        text:
          records.length === 1 && first
            ? `${first.id}: ${count(first.length)} bases. ${first.description}`
            : `${records.length} records, ${count(
                records.reduce((total, record) => total + record.length, 0),
              )} bases in all.`,
      });
      setDoor("paste");
    });
  };

  const looksAligned = (() => {
    const lengths = value
      .split(">")
      .slice(1)
      .map((block) => block.split("\n").slice(1).join("").replace(/\s/g, "").length)
      .filter(Boolean);
    return lengths.length > 1 && new Set(lengths).size === 1;
  })();

  const alignThem = () => {
    start(async () => {
      const state = await alignAction(value);
      if (state.error || !state.aligned) {
        setMessage({ kind: "bad", text: state.error ?? "Nothing came back." });
        return;
      }
      const { aligned } = state;
      onChange(aligned.fasta);
      setMessage({
        kind: "ok",
        text: `${aligned.depth} sequences aligned by ${aligned.tool_version} into ${aligned.width} columns.`,
      });
    });
  };

  const collapse = () => {
    start(async () => {
      const state = await consensusAction(value);
      if (state.error || !state.result) {
        setMessage({ kind: "bad", text: state.error ?? "Nothing came back." });
        return;
      }
      const { result } = state;
      onChange(`>consensus_of_${result.from_count}\n${result.sequence}`);
      setMessage({
        kind: "ok",
        text: `${result.from_count} sequences collapsed. ${result.identity}% of columns agreed; ${result.varied} carry an ambiguity code.`,
      });
    });
  };

  const handleReverseComplement = () => {
    if (!value.trim()) return;
    const rev = computeReverseComplement(value);
    onChange(rev);
    setMessage({
      kind: "ok",
      text: "Converted sequence to 5′→3′ reverse complement.",
    });
  };

  const handleCleanSequence = () => {
    if (!value.trim()) return;
    const cleaned = normalizeSequenceFormatting(value);
    onChange(cleaned);
    setMessage({
      kind: "ok",
      text: "Removed whitespace and recognised GenBank ORIGIN coordinates. Digits, gaps, punctuation, and unknown letters remain visible for correction.",
    });
  };

  const handleToUpperCase = () => {
    if (!value.trim()) return;
    const lines = value.split("\n");
    const upper = lines.map((l) => (l.startsWith(">") ? l : l.toUpperCase())).join("\n");
    onChange(upper);
  };

  const loadSample = (sample: (typeof SAMPLE_TEMPLATES)[0]) => {
    onChange(sample.sequence);
    setMessage({
      kind: "ok",
      text: `Loaded verified sample: ${sample.name} · ${sample.accession} (${sample.length.toLocaleString()} bp)`,
    });
    setDoor("paste");
  };

  const readFile = (file: File) => {
    if (file.size > MAX_FILE_BYTES) {
      setMessage({
        kind: "bad",
        text: `${file.name} is ${(file.size / 1024 / 1024).toFixed(1)} MB, and this takes up to ${MAX_FILE_BYTES / 1024 / 1024} MB. A whole genome belongs in the background, not the target.`,
      });
      return;
    }
    void file.text().then((text) => {
      onChange(text);
      setMessage({
        kind: "ok",
        text: `${file.name}: ${count(approximateBases(text))} bases read.`,
      });
      setDoor("paste");
    });
  };

  return (
    <div className="space-y-3">
      {/* Header and Intake Modes */}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-foreground">{label}</span>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>

        <div
          className="flex flex-wrap gap-1 rounded-lg border border-border/60 bg-surface-wash/30 p-1"
          role="group"
          aria-label={`How to give the ${label}`}
        >
          <Door id="paste" current={door} onSelect={setDoor} icon={Type}>
            Paste
          </Door>
          <Door id="upload" current={door} onSelect={setDoor} icon={FileUp}>
            File
          </Door>
          {canFetch ? (
            <Door id="accession" current={door} onSelect={setDoor} icon={Link2}>
              Accession
            </Door>
          ) : null}
        </div>
      </div>

      {/* 1-Click Sample Library Quick Chips */}
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-dashed border-border/60 bg-surface-warm/15 px-3 py-2 text-xs">
        <span className="flex shrink-0 items-center gap-1 font-medium text-muted-foreground">
          <FlaskConical className="size-3 text-primary" />
          <span>Verified examples:</span>
        </span>
        <div className="flex flex-wrap gap-1">
          {SAMPLE_TEMPLATES.map((sample) => (
            <button
              key={sample.id}
              type="button"
              onClick={() => loadSample(sample)}
              className="min-h-6 cursor-pointer rounded-lg border border-border/70 bg-surface-wash/35 px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              title={`${sample.name} · ${sample.accession}: ${sample.description}`}
            >
              {sample.name}
            </button>
          ))}
        </div>
      </div>

      {/* Input Door Renderings */}
      {door === "accession" ? (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={accession}
            onChange={(event) => setAccession(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                lookUp();
              }
            }}
            placeholder="NM_000546.6 — or several, separated by commas"
            aria-label={`${label} accession`}
            className="min-w-0 flex-1 font-mono text-xs sm:min-w-[16rem]"
          />
          <Button type="button" size="sm" onClick={lookUp} disabled={pending}>
            {pending ? <Loader2 className="animate-spin" /> : <Link2 />}
            Look up
          </Button>
        </div>
      ) : door === "upload" ? (
        <div
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const file = event.dataTransfer.files[0];
            if (file) readFile(file);
          }}
          className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border/60 bg-surface-wash/25 p-6 text-center"
        >
          <FileUp className="size-5 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            Drop a FASTA, GenBank or plain sequence file here, or
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => fileInput.current?.click()}
          >
            Choose a file
          </Button>
          <input
            ref={fileInput}
            type="file"
            aria-label={`${label} file`}
            accept={ACCEPTED}
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) readFile(file);
              event.target.value = "";
            }}
          />
          <p className="text-xs text-muted-foreground">
            It is read in your browser and lands in the box below, where you can see it before
            anything is designed.
          </p>
        </div>
      ) : (
        <Textarea
          rows={rows}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onInput={(event) => onChange(event.currentTarget.value)}
          aria-label={label}
          placeholder={placeholder}
          className="font-mono text-xs leading-relaxed"
        />
      )}

      {/* Live Sequence Statistics Strip */}
      {stats ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/70 bg-surface-wash/55 p-2.5 text-xs shadow-2xs">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-1 font-medium text-foreground">
              <Dna className="size-3.5 text-primary" />
              <span>{count(stats.len)} bp</span>
            </span>

            <span className="flex items-center gap-1.5 border-l pl-3">
              <span className="text-muted-foreground">GC Content:</span>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-xs font-medium tabular-nums",
                  stats.gcPct >= 40 && stats.gcPct <= 60
                    ? "bg-success/15 text-success"
                    : "bg-warning/15 text-warning",
                )}
              >
                {stats.gcPct}%
              </span>
            </span>

            <span className="border-l pl-3 text-muted-foreground">
              Approx. MW:{" "}
              <strong className="font-medium text-foreground tabular-nums">
                {stats.mwKDa} kDa
              </strong>
            </span>

            <span className="border-l pl-3 text-muted-foreground">
              Format: <strong className="font-medium text-foreground">{stats.format}</strong>
            </span>
          </div>

          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 text-xs text-muted-foreground hover:text-foreground"
              onClick={handleToUpperCase}
              title="Convert bases to uppercase"
            >
              A/a
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 text-xs text-muted-foreground hover:text-foreground"
              onClick={handleReverseComplement}
              title="Convert to reverse complement"
            >
              <ArrowLeftRight className="size-3" />
              Rev-Comp
            </Button>
            {suspiciousChars.length > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 px-1.5 text-xs text-warning hover:text-foreground"
                onClick={handleCleanSequence}
                title="Remove only safe whitespace and coordinate formatting"
              >
                <Sparkles className="size-3" />
                Normalize
              </Button>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 text-xs text-muted-foreground hover:text-destructive"
              onClick={() => {
                onChange("");
                setMessage(null);
              }}
            >
              Clear
            </Button>
          </div>
        </div>
      ) : null}

      {/* Suspicious Characters Alert */}
      {suspiciousChars.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/30 bg-warning/5 px-2.5 py-1.5 text-xs text-warning">
          <span className="flex items-center gap-1.5">
            <AlertCircle className="size-3.5 shrink-0" />
            Contains non-nucleotide characters:{" "}
            <code className="font-mono font-semibold">{suspiciousChars.join(" ")}</code>
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={handleCleanSequence}
          >
            Normalize formatting
          </Button>
        </div>
      ) : null}

      {records > 1 ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/60 bg-surface-sage/20 p-3">
          <p className="min-w-0 flex-1 basis-full text-xs leading-relaxed text-muted-foreground sm:min-w-[16rem] sm:basis-auto">
            {records} sequences are in the box.{" "}
            {looksAligned
              ? "Every row is the same length, so they look aligned already."
              : "The rows are different lengths, so they have not been aligned — and anything that reads a column of them needs an alignment first."}
          </p>
          <div className="flex gap-2">
            {canAlign && !looksAligned ? (
              <Button type="button" size="sm" onClick={alignThem} disabled={pending}>
                {pending ? <Loader2 className="animate-spin" /> : <AlignLeft />}
                Align them
              </Button>
            ) : null}
            {allowConsensus ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={collapse}
                disabled={pending || !looksAligned}
                title={looksAligned ? undefined : "They have to be aligned first"}
              >
                {pending ? <Loader2 className="animate-spin" /> : <Layers />}
                Build a consensus
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {message ? (
        <p
          role="status"
          className={cn(
            "flex items-start gap-1.5 text-xs leading-relaxed",
            message.kind === "ok" ? "text-success" : "text-destructive",
          )}
        >
          {message.kind === "ok" ? (
            <Check className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          )}
          {message.text}
        </p>
      ) : null}
    </div>
  );
}

function Door({
  id,
  current,
  onSelect,
  icon: Icon,
  children,
}: {
  id: Door;
  current: Door;
  onSelect: (door: Door) => void;
  icon: typeof Type;
  children: React.ReactNode;
}) {
  const active = current === id;
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => onSelect(id)}
      className={cn(
        "flex min-h-9 min-w-9 cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:min-h-0 sm:min-w-0",
        active
          ? "bg-surface-warm/45 font-medium text-foreground shadow-2xs"
          : "text-muted-foreground hover:bg-surface-warm/35 hover:text-foreground",
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <span>{children}</span>
    </button>
  );
}
