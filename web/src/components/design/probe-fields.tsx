"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PROBE_AUTHORITY } from "@/lib/engine-authorities.generated";
import multiplexCapabilities from "@/lib/multiplex-capabilities.generated.json";
import { EvidenceInput } from "./evidence-input";
import { ProbeMultiplexEditor } from "./probe-multiplex-editor";

type ProbeAuthorityRecord = {
  execution_status?: string;
  chemistry?: string;
  reporter_options?: readonly string[];
  quencher_options?: readonly string[];
  kind?: string;
  selection?: string;
};
type QpcrOpticalProfile =
  (typeof multiplexCapabilities.qpcr_optical_profiles)[keyof typeof multiplexCapabilities.qpcr_optical_profiles];

const PROBE_RECORDS: Readonly<Record<string, ProbeAuthorityRecord>> =
  PROBE_AUTHORITY.records as unknown as Readonly<Record<string, ProbeAuthorityRecord>>;
const QPCR_OPTICAL_PROFILES: Readonly<Record<string, QpcrOpticalProfile>> =
  multiplexCapabilities.qpcr_optical_profiles;

export function ProbeFields({
  section,
  value,
  onChange,
}: {
  section: "design" | "reaction";
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const records = PROBE_RECORDS;
  const protocol = value("probeProtocol") || "thermofisher-taqman-conventional";
  const selected = records[protocol];
  const executionStatus = String(selected?.execution_status || "unresolved");
  const chemistry = value("probeChemistry") || String(selected?.chemistry || "");
  const reporters = Array.isArray(selected?.reporter_options)
    ? selected.reporter_options.map(String)
    : [];
  const quenchers = Array.isArray(selected?.quencher_options)
    ? selected.quencher_options.map(String)
    : [];
  const internalQuenchers = chemistry === "double-quenched-hydrolysis" ? ["ZEN", "TAO"] : [];

  if (section === "reaction") {
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">
            Probe optics, multiplex context & MIQE evidence
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Reporter/quencher choices belong to the selected probe chemistry. A versioned
            optical-authority JSON can validate reporter/channel assignments; measured qPCR evidence
            is stored with the run but never rewrites the original sequence ranking.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="probeReporter" className="text-xs">
              Reporter
            </Label>
            <select
              id="probeReporter"
              required
              value={value("probeReporter")}
              onChange={(e) => onChange("probeReporter", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="">Choose reporter</option>
              {reporters.map((reporter) => (
                <option key={reporter} value={reporter}>
                  {reporter}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="probeQuencher" className="text-xs">
              Terminal quencher
            </Label>
            <select
              id="probeQuencher"
              required
              value={value("probeQuencher")}
              onChange={(e) => onChange("probeQuencher", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="">Choose quencher</option>
              {quenchers.map((quencher) => (
                <option key={quencher} value={quencher}>
                  {quencher}
                </option>
              ))}
            </select>
          </div>
          {chemistry === "double-quenched-hydrolysis" ? (
            <div>
              <Label htmlFor="probeInternalQuencher" className="text-xs">
                Internal quencher
              </Label>
              <select
                id="probeInternalQuencher"
                required
                value={value("probeInternalQuencher") || "ZEN"}
                onChange={(e) => onChange("probeInternalQuencher", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="ZEN">ZEN</option>
                <option value="TAO">TAO</option>
              </select>
            </div>
          ) : null}
          <EvidenceInput
            id="probeInstrumentProfile"
            label="Instrument / optical profile"
            value={value}
            onChange={onChange}
            placeholder="Instrument model or validated channel profile"
          />
        </div>
        <ProbeMultiplexEditor
          rawValue={value("probeMultiplexPanel")}
          reporters={reporters}
          quenchers={quenchers}
          internalQuenchers={internalQuenchers}
          onChange={(next) => onChange("probeMultiplexPanel", next)}
        />
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">
            Versioned optical authority
          </summary>
          <div className="mt-3 space-y-3">
            <div>
              <Label htmlFor="probeOpticalAuthorityProfile" className="text-xs">
                Reviewed instrument profile
              </Label>
              <select
                id="probeOpticalAuthorityProfile"
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-background px-2 text-sm"
                defaultValue=""
                onChange={(event) => {
                  const profile = QPCR_OPTICAL_PROFILES[event.target.value];
                  if (profile) {
                    onChange(
                      "probeOpticalAuthorityPayload",
                      JSON.stringify(
                        {
                          schema: profile.schema,
                          authority_id: profile.authority_id,
                          instrument: profile.instrument,
                          version: profile.version,
                          channels: profile.channels,
                        },
                        null,
                        2,
                      ),
                    );
                    onChange(
                      "probeInstrumentProfile",
                      `${profile.instrument} · ${profile.version}`,
                    );
                  }
                }}
              >
                <option value="">Custom / paste authority below</option>
                {Object.entries(QPCR_OPTICAL_PROFILES).map(([id, profile]) => (
                  <option key={id} value={id}>
                    {profile.instrument} · up to {profile.max_targets} channels/targets
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted-foreground">
                Built-in profiles reproduce reviewed manufacturer channel/reporter maps. They do not
                claim your instrument has current spectral calibration or color compensation; that
                remains run/instrument evidence.
              </p>
            </div>
            <div>
              <Label htmlFor="probeOpticalAuthorityPayload" className="text-xs">
                Channel/reporter authority JSON
              </Label>
              <textarea
                id="probeOpticalAuthorityPayload"
                value={value("probeOpticalAuthorityPayload")}
                onChange={(e) => onChange("probeOpticalAuthorityPayload", e.target.value)}
                rows={8}
                spellCheck={false}
                placeholder={
                  '{"schema":"pcrstudio.qpcr-optical-profile.v1","authority_id":"instrument-profile-id","instrument":"model","version":"1","channels":[{"channel":"FAM","reporters":["FAM"]}]}'
                }
                className="mt-1 w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Instrument identity alone is not treated as spectral authority. PCRStudio validates
                only against this explicit versioned map and does not infer calibration or
                compensation.
              </p>
            </div>
          </div>
        </details>
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">MIQE 2.0 run evidence</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="probeEfficiencyPercent"
              label="Efficiency (%)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeStandardCurveR2"
              label="Standard-curve R²"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeLod"
              label="LoD"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeLloq"
              label="LLOQ"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeUloq"
              label="ULOQ"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeReplicates"
              label="Replicates"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeCqMean"
              label="Mean Cq"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeDynamicRangeLogs"
              label="Dynamic range (logs)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeNtcStatus"
              label="NTC status"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeNoRtStatus"
              label="No-RT status"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probePositiveControlStatus"
              label="Positive control"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeBaselineMethod"
              label="Baseline method"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeThresholdMethod"
              label="Threshold/Cq method"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeRawDataReference"
              label="RDML/RDES/raw-data reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeReferenceGenes"
              label="Reference genes"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeNormalizationMethod"
              label="Normalization"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeInhibitionAssessment"
              label="Inhibition assessment"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="probeValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Measured evidence is stored with <code>decision_impact = none</code>; a validation run
            never silently re-ranks the original assay.
          </p>
        </details>
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div>
        <h3 className="font-serif text-base font-semibold">
          Chemistry-aware hydrolysis-probe design
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Thermo Fisher conventional and IDT PrimeTime conventional/double-quenched profiles are
          independent executable authorities. MGB uses an external-authority round-trip: PCRStudio
          exports stable candidates and imports MGB-aware Tm values with candidate-set hash and
          tool/version/date provenance; it never substitutes ordinary-DNA Tm.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="probeProtocol" className="text-xs">
            Named probe authority
          </Label>
          <select
            id="probeProtocol"
            required
            value={protocol}
            onChange={(event) => {
              const next = event.target.value;
              const rec = records[next];
              onChange("probeProtocol", next);
              onChange("probeChemistry", String(rec?.chemistry || ""));
              onChange("probeReporter", "");
              onChange("probeQuencher", "");
              onChange(
                "probeInternalQuencher",
                String(rec?.chemistry || "") === "double-quenched-hydrolysis" ? "ZEN" : "",
              );
            }}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            {Object.entries(records)
              .filter(([, record]) => String(record.kind || "").includes("probe"))
              .map(([id, record]) => (
                <option
                  key={id}
                  value={id}
                  disabled={
                    !(["executable", "external-authority-required"] as string[]).includes(
                      String(record.execution_status),
                    )
                  }
                >
                  {String(record.selection || id)}
                  {String(record.execution_status) === "external-authority-required"
                    ? " · external Tm authority"
                    : String(record.execution_status) !== "executable"
                      ? " · reference only"
                      : ""}
                </option>
              ))}
          </select>
        </div>
        <div>
          <Label htmlFor="probeChemistry" className="text-xs">
            Resolved chemistry
          </Label>
          <Input
            id="probeChemistry"
            readOnly
            value={chemistry}
            onChange={() => undefined}
            className="mt-1"
          />
        </div>
      </div>
      <div>
        <Label htmlFor="probeTranscriptMode" className="text-xs">
          Transcript geometry
        </Label>
        <select
          id="probeTranscriptMode"
          value={value("probeTranscriptMode") || "generic"}
          onChange={(e) => onChange("probeTranscriptMode", e.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
        >
          <option value="generic">Generic sequence / no transcript claim</option>
          <option value="exon-junction">Probe/assay targets an exon junction</option>
          <option value="exon-spanning">Amplicon spans exon boundary</option>
          <option value="transcript-specific">Transcript/isoform-specific assay</option>
        </select>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="probeTranscriptJunctions" className="text-xs">
            Transcript junction coordinates (0-based)
          </Label>
          <Input
            id="probeTranscriptJunctions"
            value={value("probeTranscriptJunctions")}
            onChange={(e) => onChange("probeTranscriptJunctions", e.target.value)}
            placeholder="152, 308"
          />
        </div>
        <div>
          <Label htmlFor="probeVariantPositions" className="text-xs">
            Probe-site variant mask (0-based)
          </Label>
          <Input
            id="probeVariantPositions"
            value={value("probeVariantPositions")}
            onChange={(e) => onChange("probeVariantPositions", e.target.value)}
            placeholder="171, 173"
          />
        </div>
      </div>
      {executionStatus === "external-authority-required" ? (
        <div className="space-y-3 rounded-md border border-warning/35 bg-warning/5 p-3 text-xs leading-relaxed">
          <p className="text-muted-foreground">
            MGB candidate geometry is executable, but exact MGB Tm ranking requires an external
            MGB-aware authority. Export candidates first; then import only a result bound to the
            same candidate-set SHA-256.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="probeMgbAuthorityMode" className="text-xs">
                MGB authority step
              </Label>
              <select
                id="probeMgbAuthorityMode"
                value={value("probeMgbAuthorityMode") || "export-candidates"}
                onChange={(e) => onChange("probeMgbAuthorityMode", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-background px-2 text-sm"
              >
                <option value="export-candidates">1 · Export candidates</option>
                <option value="import-results">2 · Import authority results</option>
              </select>
            </div>
            {value("probeMgbAuthorityMode") === "import-results" ? (
              <div>
                <Label htmlFor="probeMgbAuthorityPayload" className="text-xs">
                  Authority result JSON
                </Label>
                <textarea
                  id="probeMgbAuthorityPayload"
                  value={value("probeMgbAuthorityPayload")}
                  onChange={(e) => onChange("probeMgbAuthorityPayload", e.target.value)}
                  rows={5}
                  spellCheck={false}
                  placeholder={'{"schema":"pcrstudio.mgb-authority-result.v1", ...}'}
                  className="mt-1 w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs"
                />
              </div>
            ) : null}
          </div>
        </div>
      ) : executionStatus !== "executable" ? (
        <div className="rounded-md border border-warning/35 bg-warning/5 p-3 text-xs leading-relaxed text-muted-foreground">
          This profile is reference-only and remains non-executable.
        </div>
      ) : null}
      <details className="rounded-lg border border-border/60 bg-background/35 p-3">
        <summary className="cursor-pointer text-xs font-medium">
          Advanced probe-window override
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">
          Leave empty to use the selected authority. Numeric overrides are constrained inside that
          chemistry; they never convert one vendor profile into another.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {(
            [
              ["probe_tm_min", "Minimum Tm (°C)"],
              ["probe_tm_opt", "Ideal Tm (°C)"],
              ["probe_tm_max", "Maximum Tm (°C)"],
              ["probe_length_min", "Minimum length (nt)"],
              ["probe_length_opt", "Ideal length (nt)"],
              ["probe_length_max", "Maximum length (nt)"],
            ] as const
          ).map(([id, labelText]) => (
            <div key={id}>
              <Label htmlFor={id} className="text-xs text-muted-foreground">
                {labelText}
              </Label>
              <Input
                id={id}
                type="number"
                value={value(id)}
                onChange={(e) => onChange(id, e.target.value)}
                placeholder="authority"
              />
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
