"use client";

import { RpaMultiplexEditor } from "./rpa-multiplex-editor";
import { useMemo, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  flankingNumericLabel,
  flankingProtocolOptions,
  FLANKING_PROTOCOL_METADATA,
  resolveFlankingNumericPreview,
  type FlankingModuleId,
} from "@/lib/flanking-contract";

export function SearchableFlankingProtocolSelect({
  id,
  moduleId,
  value,
  onChange,
  required = false,
  allowNotSelected = true,
  disabledProtocols = new Set<string>(),
}: {
  id: string;
  moduleId: FlankingModuleId;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  allowNotSelected?: boolean;
  disabledProtocols?: ReadonlySet<string>;
}) {
  const [query, setQuery] = useState("");
  const [showHistorical, setShowHistorical] = useState(false);
  const selectRef = useRef<HTMLSelectElement>(null);
  const allOptions = useMemo(() => flankingProtocolOptions(moduleId), [moduleId]);
  const historicalCount = allOptions.filter(([, meta]) =>
    /historical|discontinued|superseded/.test(meta.status),
  ).length;
  const options = useMemo(
    () =>
      showHistorical
        ? allOptions
        : allOptions.filter(([, meta]) => !/historical|discontinued|superseded/.test(meta.status)),
    [allOptions, showHistorical],
  );
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return options
      .filter(([protocol, meta]) =>
        `${protocol} ${meta.vendor} ${meta.label} ${meta.status}`.toLowerCase().includes(q),
      )
      .slice(0, 10);
  }, [options, query]);

  return (
    <div className="space-y-2">
      <select
        ref={selectRef}
        id={id}
        required={required}
        value={value || (allowNotSelected ? "not-selected" : "")}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-xl"
      >
        {allowNotSelected ? (
          <option value="not-selected">Not selected · generic screening context only</option>
        ) : (
          <option value="">Choose reviewed executable chemistry</option>
        )}
        {options.map(([protocol, meta]) => {
          const recognizedNonExecutable = meta.status.includes("non-executable");
          return (
            <option
              key={protocol}
              value={protocol}
              disabled={disabledProtocols.has(protocol) || recognizedNonExecutable}
            >
              {meta.vendor} · {meta.label} · {meta.status}
            </option>
          );
        })}
      </select>
      {historicalCount ? (
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={showHistorical}
            onChange={(event) => setShowHistorical(event.target.checked)}
          />
          Show {historicalCount} historical / discontinued chemistry
          {historicalCount === 1 ? "" : "ies"}
        </label>
      ) : null}
      {options.length > 7 ? (
        <div className="space-y-1">
          <Label htmlFor={`${id}Search`} className="text-xs">
            Find chemistry
          </Label>
          <Input
            id={`${id}Search`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search vendor, product, catalogue or status"
            className="h-8 sm:max-w-xl"
          />
          {matches.length ? (
            <div
              className="flex flex-wrap gap-1.5"
              role="group"
              aria-label="Matching chemistry shortcuts"
            >
              {matches.map(([protocol, meta]) => {
                const disabled =
                  disabledProtocols.has(protocol) || meta.status.includes("non-executable");
                return (
                  <button
                    key={protocol}
                    type="button"
                    disabled={disabled}
                    onClick={() => {
                      onChange(protocol);
                      setQuery("");
                      selectRef.current?.focus();
                    }}
                    className="rounded-md border border-border/70 bg-background px-2 py-1 text-left text-xs leading-tight disabled:cursor-not-allowed disabled:opacity-45"
                    title={meta.source}
                  >
                    <span className="font-medium">{meta.vendor}</span> · {meta.label}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function valueOrEmpty(value: (key: string) => string, key: string): string | undefined {
  const raw = value(key).trim();
  return raw || undefined;
}

export function FlankingNumericRecipeFields({
  moduleId,
  protocol,
  value,
  onChange,
}: {
  moduleId: FlankingModuleId;
  protocol: string;
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const state = {
    moduleId,
    protocol: protocol || "not-selected",
    reactionVolumeUl: valueOrEmpty(value, "flankingReactionVolumeUl"),
    primerEachUm: valueOrEmpty(value, "flankingPrimerEachUm"),
    primerEachNm: valueOrEmpty(value, "flankingPrimerEachNm"),
    gcEnhancerPercent: valueOrEmpty(value, "flankingGcEnhancerPercent"),
    additive: valueOrEmpty(value, "flankingAdditive"),
    cyclingProfile: valueOrEmpty(value, "qpcrCyclingProfile"),
    templateFractionPercent: valueOrEmpty(value, "flankingTemplateFractionPercent"),
    targetLengthKb: valueOrEmpty(value, "longRangeTargetLengthKb"),
    partitionFormatDetail: valueOrEmpty(value, "digitalPartitionFormatDetail"),
    preparation:
      moduleId === "colony-pcr"
        ? valueOrEmpty(value, "colonyPreparation")
        : valueOrEmpty(value, "flankingPreparation"),
    initialDenaturationTimeMin: valueOrEmpty(value, "colonyInitialDenaturationMin"),
    rpaTemperatureC: valueOrEmpty(value, "rpaTemperatureC"),
    rpaTimeMin: valueOrEmpty(value, "rpaTimeMin"),
    rpaBstUnitsPerUl: valueOrEmpty(value, "rpaBstUnitsPerUl"),
    rpaMultiplex: value("rpaMultiplex") === "true",
    templateInputNg: valueOrEmpty(value, "flankingTemplateInputNg"),
    templateInputUl: valueOrEmpty(value, "flankingTemplateInputUl"),
    templateClass: valueOrEmpty(value, "flankingTemplateClass"),
    hmwTemplateVerified: value("longRangeHmwTemplateVerified") === "true",
    qpcrInstrumentProfile: valueOrEmpty(value, "qpcrInstrumentProfile"),
    digitalPlatformId: valueOrEmpty(value, "digitalPlatformId"),
    digitalConsumableId: valueOrEmpty(value, "digitalConsumableId"),
    effectivePartitionVolumeNl: valueOrEmpty(value, "digitalEffectivePartitionVolumeNl"),
    fragmentationEnzyme: valueOrEmpty(value, "digitalFragmentationEnzyme"),
    colonySampleInputUl: valueOrEmpty(value, "colonySampleInputUl"),
    fromRna: value("fromRna") === "true",
  } as const;
  const preview = resolveFlankingNumericPreview(state);

  if (!protocol || protocol === "not-selected") {
    return (
      <p className="text-xs text-muted-foreground">
        Select an exact reviewed chemistry to resolve source-conditioned numeric reaction values.
      </p>
    );
  }

  const usesNmPrimer =
    moduleId === "qpcr-sybr" || moduleId === "rpa" || preview.values.primer_each_nM !== undefined;
  const primerRange = preview.ranges[usesNmPrimer ? "primer_each_nM" : "primer_each_uM"];
  const volume = preview.values.reaction_volume_uL;

  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-3">
      <div>
        <h4 className="text-sm font-semibold">Resolved numeric recipe · source-conditioned</h4>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Bench chemistry only. Every editable value is bounded by the exact-product authority and
          sequence ranking remains unchanged.
        </p>
        {FLANKING_PROTOCOL_METADATA[protocol]?.source ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Authority: {FLANKING_PROTOCOL_METADATA[protocol].source}
            {FLANKING_PROTOCOL_METADATA[protocol].source_revision
              ? ` · ${FLANKING_PROTOCOL_METADATA[protocol].source_revision}`
              : ""}
            {FLANKING_PROTOCOL_METADATA[protocol].source_url ? (
              <>
                {" "}
                ·{" "}
                <a
                  className="underline"
                  href={FLANKING_PROTOCOL_METADATA[protocol].source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  source
                </a>
              </>
            ) : null}
          </p>
        ) : null}
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <Label htmlFor="flankingReactionVolumeUl" className="text-xs">
            Reaction volume (µL)
          </Label>
          <Input
            id="flankingReactionVolumeUl"
            inputMode="decimal"
            value={value("flankingReactionVolumeUl") || (volume ? String(volume) : "")}
            onChange={(e) => onChange("flankingReactionVolumeUl", e.target.value)}
            placeholder="Exact reviewed format"
            className="mt-1 h-8"
          />
        </div>
        {moduleId !== "colony-pcr" ? (
          <>
            <div>
              <Label htmlFor="flankingTemplateInputNg" className="text-xs">
                Template input (ng/reaction)
              </Label>
              <Input
                id="flankingTemplateInputNg"
                inputMode="decimal"
                value={value("flankingTemplateInputNg")}
                onChange={(e) => onChange("flankingTemplateInputNg", e.target.value)}
                placeholder="Measured / source-bounded when known"
                className="mt-1 h-8"
              />
            </div>
            <div>
              <Label htmlFor="flankingTemplateInputUl" className="text-xs">
                Template volume (µL/reaction)
              </Label>
              <Input
                id="flankingTemplateInputUl"
                inputMode="decimal"
                value={value("flankingTemplateInputUl")}
                onChange={(e) => onChange("flankingTemplateInputUl", e.target.value)}
                placeholder="Measured volume"
                className="mt-1 h-8"
              />
            </div>
          </>
        ) : null}
        {usesNmPrimer ? (
          <div>
            <Label htmlFor="flankingPrimerEachNm" className="text-xs">
              Each primer (nM)
            </Label>
            <Input
              id="flankingPrimerEachNm"
              inputMode="decimal"
              value={value("flankingPrimerEachNm")}
              onChange={(e) => onChange("flankingPrimerEachNm", e.target.value)}
              placeholder={
                preview.values.primer_each_nM
                  ? String(preview.values.primer_each_nM)
                  : "Source baseline"
              }
              className="mt-1 h-8"
            />
            {primerRange ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Editable range {primerRange[0]}–{primerRange[1]} nM.
              </p>
            ) : null}
          </div>
        ) : (
          <div>
            <Label htmlFor="flankingPrimerEachUm" className="text-xs">
              Each primer (µM)
            </Label>
            <Input
              id="flankingPrimerEachUm"
              inputMode="decimal"
              value={value("flankingPrimerEachUm")}
              onChange={(e) => onChange("flankingPrimerEachUm", e.target.value)}
              placeholder={
                preview.values.primer_each_uM
                  ? String(preview.values.primer_each_uM)
                  : "Source baseline"
              }
              className="mt-1 h-8"
            />
            {primerRange ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Editable range {primerRange[0]}–{primerRange[1]} µM.
              </p>
            ) : null}
          </div>
        )}

        {moduleId === "standard-pcr" &&
        ["neb-onetaq-hot-start-gc-m0485", "neb-onetaq-hot-start-quickload-gc-m0489"].includes(
          protocol,
        ) ? (
          <>
            <div>
              <Label htmlFor="flankingAdditive" className="text-xs">
                High-GC additive
              </Label>
              <select
                id="flankingAdditive"
                value={value("flankingAdditive") || "none"}
                onChange={(e) => onChange("flankingAdditive", e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs"
              >
                <option value="none">None</option>
                <option value="high-gc-enhancer">NEB High GC Enhancer</option>
              </select>
            </div>
            {value("flankingAdditive") === "high-gc-enhancer" ? (
              <div>
                <Label htmlFor="flankingGcEnhancerPercent" className="text-xs">
                  Enhancer final (%)
                </Label>
                <Input
                  id="flankingGcEnhancerPercent"
                  inputMode="decimal"
                  value={value("flankingGcEnhancerPercent")}
                  onChange={(e) => onChange("flankingGcEnhancerPercent", e.target.value)}
                  placeholder="10"
                  className="mt-1 h-8"
                />
              </div>
            ) : null}
          </>
        ) : null}

        {moduleId === "colony-pcr" && protocol === "neb-onetaq-hotstart-m0488-colony" ? (
          <div>
            <Label htmlFor="colonyInitialDenaturationMin" className="text-xs">
              Initial denaturation / lysis (min)
            </Label>
            <Input
              id="colonyInitialDenaturationMin"
              inputMode="decimal"
              value={value("colonyInitialDenaturationMin")}
              onChange={(e) => onChange("colonyInitialDenaturationMin", e.target.value)}
              placeholder="2–5"
              className="mt-1 h-8"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              M0488 publishes a 2–5 minute colony-PCR lysis range; choose the actual SOP value
              rather than silently taking an endpoint.
            </p>
          </div>
        ) : null}

        {moduleId === "qpcr-sybr" && protocol === "thermo-powertrack-sybr-a46xxx" ? (
          <>
            <div>
              <Label htmlFor="qpcrCyclingProfile" className="text-xs">
                Cycling branch
              </Label>
              <select
                id="qpcrCyclingProfile"
                value={value("qpcrCyclingProfile") || "protocol-default"}
                onChange={(e) => onChange("qpcrCyclingProfile", e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs"
              >
                <option value="protocol-default">Choose source branch</option>
                <option value="fast">Fast · 95°C/5 s + 60°C/30 s</option>
                <option value="standard">Standard · 95°C/15 s + 60°C/60 s</option>
              </select>
            </div>
            <div>
              <Label htmlFor="flankingTemplateFractionPercent" className="text-xs">
                Template fraction (%)
              </Label>
              <Input
                id="flankingTemplateFractionPercent"
                inputMode="decimal"
                value={value("flankingTemplateFractionPercent")}
                onChange={(e) => onChange("flankingTemplateFractionPercent", e.target.value)}
                placeholder="10–20"
                className="mt-1 h-8"
              />
            </div>
            <div>
              <Label htmlFor="flankingAdditive" className="text-xs">
                Optional sample buffer
              </Label>
              <select
                id="flankingAdditive"
                value={value("flankingAdditive") || "none"}
                onChange={(e) => onChange("flankingAdditive", e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs"
              >
                <option value="none">None</option>
                <option value="yellow-sample-buffer">40X Yellow Sample Buffer → 1X</option>
              </select>
              <p className="mt-1 text-xs text-muted-foreground">
                Optional in MAN0018825; it is not silently added to the PowerTrack baseline.
              </p>
            </div>
          </>
        ) : null}

        {moduleId === "rpa" && protocol === "thermo-lyo-ready-rpa" ? (
          <>
            <div>
              <Label htmlFor="rpaMultiplex" className="text-xs">
                RPA primer context
              </Label>
              <select
                id="rpaMultiplex"
                value={value("rpaMultiplex") || "false"}
                onChange={(e) => onChange("rpaMultiplex", e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs"
              >
                <option value="false">Singleplex · 300 nM starting point</option>
                <option value="true">Multiplex · 100 nM starting point</option>
              </select>
            </div>
            {value("rpaMultiplex") === "true" ? (
              <div className="sm:col-span-2">
                <RpaMultiplexEditor
                  rawValue={value("rpaMultiplexPanel")}
                  onChange={(next) => onChange("rpaMultiplexPanel", next)}
                />
              </div>
            ) : null}
            <div>
              <Label htmlFor="rpaTemperatureC" className="text-xs">
                Incubation temperature (°C)
              </Label>
              <Input
                id="rpaTemperatureC"
                inputMode="decimal"
                value={value("rpaTemperatureC")}
                onChange={(e) => onChange("rpaTemperatureC", e.target.value)}
                placeholder="42 · reviewed 34–45"
                className="mt-1 h-8"
              />
            </div>
            <div>
              <Label htmlFor="rpaTimeMin" className="text-xs">
                Incubation time (min)
              </Label>
              <Input
                id="rpaTimeMin"
                inputMode="decimal"
                value={value("rpaTimeMin")}
                onChange={(e) => onChange("rpaTimeMin", e.target.value)}
                placeholder="20 · reviewed 10–25"
                className="mt-1 h-8"
              />
            </div>
            <div>
              <Label htmlFor="rpaBstUnitsPerUl" className="text-xs">
                Bst polymerase (U/µL)
              </Label>
              <Input
                id="rpaBstUnitsPerUl"
                inputMode="decimal"
                value={value("rpaBstUnitsPerUl")}
                onChange={(e) => onChange("rpaBstUnitsPerUl", e.target.value)}
                placeholder="0.15 · reviewed 0.015–0.15"
                className="mt-1 h-8"
              />
            </div>
          </>
        ) : null}

        {moduleId === "long-range-pcr" && protocol === "toyobo-kod-long-kml101" ? (
          <div>
            <Label htmlFor="longRangeTargetLengthKb" className="text-xs">
              Target length (kb)
            </Label>
            <Input
              id="longRangeTargetLengthKb"
              inputMode="decimal"
              value={value("longRangeTargetLengthKb")}
              onChange={(e) => onChange("longRangeTargetLengthKb", e.target.value)}
              placeholder="Required for 5 vs 10 s/kb"
              className="mt-1 h-8"
            />
          </div>
        ) : null}

        {moduleId === "digital-pcr" &&
        ["qiagen-qiacuity-eg", "qiagen-qiacuity-onestep-advanced-eg"].includes(protocol) ? (
          <div>
            <Label htmlFor="digitalPartitionFormatDetail" className="text-xs">
              QIAcuity Nanoplate format
            </Label>
            <select
              id="digitalPartitionFormatDetail"
              value={value("digitalPartitionFormatDetail") || "not-specified"}
              onChange={(e) => onChange("digitalPartitionFormatDetail", e.target.value)}
              className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs"
            >
              <option value="not-specified">Choose format</option>
              <option value="8.5k">8.5k · 12 µL branch</option>
              <option value="26k">26k · 40 µL branch</option>
            </select>
          </div>
        ) : null}
      </div>

      {preview.issues.length ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
          {preview.issues.map((issue) => (
            <p key={`${issue.field}:${issue.message}`}>{issue.message}</p>
          ))}
        </div>
      ) : null}

      <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(preview.values)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, numeric]) => (
            <div
              key={key}
              className="flex items-start justify-between gap-2 border-b border-border/40 py-1"
            >
              <dt className="text-muted-foreground">{flankingNumericLabel(key)}</dt>
              <dd className="text-right font-medium">
                {Number.isInteger(numeric) ? numeric : Number(numeric.toFixed(4))}
                <span className="block text-xs font-normal text-muted-foreground">
                  {preview.origins[key]}
                </span>
              </dd>
            </div>
          ))}
      </dl>

      {preview.unresolved.length ? (
        <div className="rounded-md border border-warning/35 bg-warning/5 p-2">
          <p className="text-xs font-semibold">Unresolved numeric dependencies</p>
          {preview.unresolved.map((item) => (
            <p key={item.id} className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {item.note}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
