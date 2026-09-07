import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DIGITAL_CONSUMABLE_PLATFORMS,
  DIGITAL_PLATFORM_LABELS,
  DIGITAL_PROTOCOL_PLATFORMS,
  FLANKING_PROTOCOL_GROUPS,
} from "@/lib/flanking-protocol-authority.generated";
import { FlankingNumericRecipeFields, SearchableFlankingProtocolSelect } from "./flanking-fields";
import { DigitalMultiplexEditor } from "./digital-multiplex-editor";
import multiplexCapabilities from "@/lib/multiplex-capabilities.generated.json";

type PlatformAuthority =
  (typeof multiplexCapabilities.platform_authorities)[keyof typeof multiplexCapabilities.platform_authorities];
const PLATFORM_AUTHORITIES: Readonly<Record<string, PlatformAuthority>> =
  multiplexCapabilities.platform_authorities;

export function DigitalFragmentationFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Template fragmentation state</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Fragmentation is pre-analytical template provenance. Record whether it is required,
          planned or already performed; platform/partition and named chemistry stay on Reaction.
        </p>
      </div>
      <div>
        <Label htmlFor="digitalFragmentationState" className="text-xs">
          Template fragmentation
        </Label>
        <select
          id="digitalFragmentationState"
          required
          value={value("digitalFragmentationState")}
          onChange={(event) => onChange("digitalFragmentationState", event.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
        >
          <option value="">Choose explicit state</option>
          <option value="not-assessed">Not assessed yet</option>
          <option value="not-required">Not required by current platform/template SOP</option>
          <option value="planned">Planned</option>
          <option value="performed">Performed</option>
        </select>
      </div>
      {value("digitalFragmentationState") === "planned" ||
      value("digitalFragmentationState") === "performed" ? (
        <div>
          <Label htmlFor="digitalFragmentationEnzyme" className="text-xs">
            Fragmentation enzyme / SOP identity
          </Label>
          <Input
            id="digitalFragmentationEnzyme"
            value={value("digitalFragmentationEnzyme")}
            onChange={(e) => onChange("digitalFragmentationEnzyme", e.target.value)}
            placeholder="Exact enzyme and source-backed SOP; never inferred"
            className="mt-1"
          />
        </div>
      ) : null}
    </div>
  );
}

export function DigitalPcrFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const authorityKey =
    value("digitalPlatformId") === "qiagen-qiacuity"
      ? value("digitalInstrumentModel")
      : value("digitalPlatformId");
  const platformAuthority = PLATFORM_AUTHORITIES[authorityKey];
  const allowedMultiplexModes = new Set<string>((platformAuthority?.modes || []).map(String));
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Digital PCR run handoff</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Partition format, platform and named chemistry are run provenance. Template fragmentation
          is recorded with the biological input; PCRStudio does not infer threshold, rain or Poisson
          concentration from sequence design.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="digitalPartitionFormat" className="text-xs">
            Partition format
          </Label>
          <select
            id="digitalPartitionFormat"
            required
            value={value("digitalPartitionFormat")}
            onChange={(event) => onChange("digitalPartitionFormat", event.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="">Choose format</option>
            <option value="droplet">Droplet</option>
            <option value="chip">Chip</option>
            <option value="chamber">Chamber</option>
            <option value="other">Other validated partition format</option>
          </select>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="digitalPlatformId" className="text-xs">
            Platform identity
          </Label>
          <select
            id="digitalPlatformId"
            required
            value={value("digitalPlatformId")}
            onChange={(event) => {
              const next = event.target.value;
              onChange("digitalPlatformId", next);
              const currentConsumable = value("digitalConsumableId");
              const allowedForCurrent = currentConsumable
                ? ((DIGITAL_CONSUMABLE_PLATFORMS as Record<string, readonly string[]>)[
                    currentConsumable
                  ] ?? [])
                : [];
              if (currentConsumable && !allowedForCurrent.includes(next))
                onChange("digitalConsumableId", "");
              onChange(
                "digitalPlatformName",
                next === "other-validated"
                  ? ""
                  : ((DIGITAL_PLATFORM_LABELS as Record<string, string>)[next] ?? ""),
              );
            }}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="">Choose validated platform identity</option>
            {FLANKING_PROTOCOL_GROUPS.digital_platform_ids.map((id) => {
              const base =
                id === "other-validated"
                  ? "Other validated platform / instrument"
                  : ((DIGITAL_PLATFORM_LABELS as Record<string, string>)[id] ?? id);
              const suffix = ["thermo-absolute-q", "roche-digital-lightcycler"].includes(id)
                ? " · probe chemistry → Pair+Probe"
                : "";
              return (
                <option key={id} value={id}>
                  {base}
                  {suffix}
                </option>
              );
            })}
          </select>
        </div>
        <div>
          <Label htmlFor="digitalPlatformName" className="text-xs">
            Platform / instrument name
          </Label>
          <Input
            id="digitalPlatformName"
            required={value("digitalPlatformId") === "other-validated"}
            readOnly={
              Boolean(value("digitalPlatformId")) &&
              value("digitalPlatformId") !== "other-validated"
            }
            value={value("digitalPlatformName")}
            onChange={(event) => onChange("digitalPlatformName", event.target.value)}
            placeholder={
              value("digitalPlatformId") === "other-validated"
                ? "Validated platform / instrument name"
                : "Resolved from platform identity"
            }
            className="mt-1"
          />
        </div>
      </div>
      {["qiagen-qiacuity", "bio-rad-qx600"].includes(value("digitalPlatformId")) ? (
        <div>
          <Label htmlFor="digitalInstrumentModel" className="text-xs">
            Exact multiplex instrument model
          </Label>
          <select
            id="digitalInstrumentModel"
            value={value("digitalInstrumentModel")}
            onChange={(e) => onChange("digitalInstrumentModel", e.target.value)}
            className="mt-1 h-9 w-full rounded-md border border-border/70 bg-surface-wash/35 px-2 text-sm sm:max-w-md"
          >
            <option value="">Choose exact model</option>
            {value("digitalPlatformId") === "qiagen-qiacuity" ? (
              <>
                <option value="qiacuity-one-2plex">
                  QIAcuity One 2plex · 2 channels / up to 4 targets
                </option>
                <option value="qiacuity-one-5plex">
                  QIAcuity One 5plex · 8 channels / up to 12 targets
                </option>
                <option value="qiacuity-four">QIAcuity Four · 8 channels / up to 12 targets</option>
                <option value="qiacuity-eight">
                  QIAcuity Eight · 8 channels / up to 12 targets
                </option>
              </>
            ) : (
              <option value="bio-rad-qx600">Bio-Rad QX600 · 6 colors / up to 12 targets</option>
            )}
          </select>
          <p className="mt-1 text-xs text-muted-foreground">
            Model-specific limits are vendor-authority planning bounds. They are not PCRStudio
            wet-lab qualification.
          </p>
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="digitalConsumableId" className="text-xs">
            Platform consumable / partition carrier
          </Label>
          <select
            id="digitalConsumableId"
            value={value("digitalConsumableId")}
            onChange={(e) => onChange("digitalConsumableId", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose when platform contract requires it</option>
            {FLANKING_PROTOCOL_GROUPS.digital_consumable_ids
              .filter(
                (id) =>
                  id !== "not-specified" &&
                  (DIGITAL_CONSUMABLE_PLATFORMS as Record<string, readonly string[]>)[id]?.includes(
                    value("digitalPlatformId"),
                  ),
              )
              .map((id) => (
                <option key={id} value={id}>
                  {(
                    {
                      "qx700-rdg16": "RDG16 cartridge · QX700 / Nio / naica",
                      "naica-sapphire-chip": "naica Sapphire Chip",
                      "qx-continuum-96well": "QX Continuum 96-well consumable",
                      "qiacuity-8.5k": "QIAcuity 8.5k Nanoplate",
                      "qiacuity-26k": "QIAcuity 26k Nanoplate",
                      "absolute-q-map16": "Absolute Q MAP16 plate",
                      "roche-universal": "Digital LightCycler Universal plate · 30 µL / 28k",
                      "roche-high-sensitivity":
                        "Digital LightCycler High Sensitivity plate · 45 µL / 20k",
                      "roche-high-resolution":
                        "Digital LightCycler High Resolution plate · 15 µL / 100k",
                      "other-validated": "Other validated consumable",
                    } as Record<string, string>
                  )[id] ?? id}
                </option>
              ))}
          </select>
        </div>
        <div>
          <Label htmlFor="digitalEffectivePartitionVolumeNl" className="text-xs">
            Effective partition volume (nL) · measured/authority
          </Label>
          <Input
            id="digitalEffectivePartitionVolumeNl"
            inputMode="decimal"
            value={value("digitalEffectivePartitionVolumeNl")}
            onChange={(e) => onChange("digitalEffectivePartitionVolumeNl", e.target.value)}
            placeholder="Only when run/IFU authority provides it"
            className="mt-1"
          />
        </div>
      </div>
      {["thermo-absolute-q", "roche-digital-lightcycler", "bio-rad-qx-continuum"].includes(
        value("digitalPlatformId"),
      ) ? (
        <p className="rounded-md border border-warning/35 bg-warning/5 p-2 text-xs text-warning">
          This platform is recognized for routing, but its current validated chemistry is
          probe-oriented. Flanking dye-dPCR intentionally refuses execution; use the Pair+Probe
          digital module.
        </p>
      ) : null}
      <div>
        <Label htmlFor="digitalProtocol" className="text-xs">
          Named chemistry overlay
        </Label>
        <SearchableFlankingProtocolSelect
          id="digitalProtocol"
          moduleId="digital-pcr"
          value={value("digitalProtocol")}
          onChange={(next) => {
            onChange("digitalProtocol", next);
            if (next === "bio-rad-qx200-evagreen") {
              const allowed =
                (DIGITAL_PROTOCOL_PLATFORMS as Record<string, readonly string[]>)[next] ?? [];
              const current = value("digitalPlatformId");
              const platformId = allowed.includes(current) ? current : "bio-rad-qx200";
              onChange("digitalPlatformId", platformId);
              onChange(
                "digitalPlatformName",
                (DIGITAL_PLATFORM_LABELS as Record<string, string>)[platformId] ?? "",
              );
              onChange("digitalPartitionFormat", "droplet");
            }
            if (next === "bio-rad-qx700-naica-evagreen") {
              const allowed =
                (DIGITAL_PROTOCOL_PLATFORMS as Record<string, readonly string[]>)[next] ?? [];
              const current = value("digitalPlatformId");
              const platformId = allowed.includes(current) ? current : "bio-rad-qx700";
              onChange("digitalPlatformId", platformId);
              onChange(
                "digitalPlatformName",
                (DIGITAL_PLATFORM_LABELS as Record<string, string>)[platformId] ?? "",
              );
              onChange("digitalPartitionFormat", "droplet");
            }
            if (next === "bio-rad-qx700-evagreen-supermix") {
              onChange("digitalPlatformId", "bio-rad-qx700");
              onChange("digitalPlatformName", "Bio-Rad QX700");
              onChange("digitalPartitionFormat", "droplet");
            }
            if (["qiagen-qiacuity-eg", "qiagen-qiacuity-onestep-advanced-eg"].includes(next)) {
              onChange("digitalPlatformId", "qiagen-qiacuity");
              onChange("digitalPlatformName", "QIAGEN QIAcuity");
              onChange("digitalPartitionFormat", "chamber");
            }
          }}
        />
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          The QX200 EvaGreen chemistry is source-backed for QX200/QX600/QX ONE; naica ddPCR Mix
          (QX700/Nio/naica) and the dedicated QX700 5X EvaGreen Supermix are distinct droplet
          chemistries; QIAcuity EG and OneStep Advanced EG use fixed Nanoplate microchambers. The
          OneStep branch can carry a named RT-dPCR hold for RNA. Choosing a named chemistry binds
          its matching platform/partition identity, while accepted partitions, thresholds and
          concentration still come from the measured run.
        </p>
      </div>
      <div className="space-y-2 rounded-lg border border-border/60 p-3">
        <Label htmlFor="digitalMultiplexMode" className="text-xs">
          Multiplex architecture
        </Label>
        <select
          id="digitalMultiplexMode"
          value={value("digitalMultiplexMode") || "none"}
          onChange={(e) => onChange("digitalMultiplexMode", e.target.value)}
          className="h-9 w-full rounded-md border border-border/70 bg-surface-wash/35 px-2 text-sm sm:max-w-sm"
        >
          <option value="none">Simplex / no digital multiplex panel</option>
          <option
            value="channel"
            disabled={Boolean(platformAuthority) && !allowedMultiplexModes.has("channel")}
          >
            Channel-per-target multiplex
          </option>
          <option
            value="amplitude"
            disabled={Boolean(platformAuthority) && !allowedMultiplexModes.has("amplitude")}
          >
            Amplitude multiplex
          </option>
          <option
            value="hybrid"
            disabled={Boolean(platformAuthority) && !allowedMultiplexModes.has("hybrid")}
          >
            Channel + amplitude hybrid
          </option>
          <option
            value="probe-mix"
            disabled={Boolean(platformAuthority) && !allowedMultiplexModes.has("probe-mix")}
          >
            Probe-mix / externally classified panel
          </option>
        </select>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {platformAuthority
            ? `${platformAuthority.family}: ${platformAuthority.detection_channels} source-backed channels, planning bound ${platformAuthority.multiplex_target_bound}; allowed modes ${platformAuthority.modes.join(", ")}. `
            : "No built-in multiplex capacity authority is selected; exact capacity must come from an external validated platform authority. "}
          A software/vendor planning bound is never reported as PCRStudio wet-lab qualification.
        </p>
      </div>
      <DigitalMultiplexEditor
        mode={value("digitalMultiplexMode") || "none"}
        rawValue={value("digitalMultiplexPanel")}
        onChange={(next) => onChange("digitalMultiplexPanel", next)}
      />
      {value("digitalMultiplexMode") && value("digitalMultiplexMode") !== "none" ? (
        <div>
          <Label htmlFor="digitalRunEvidence" className="text-xs">
            Measured-run evidence JSON (optional until qualification)
          </Label>
          <textarea
            id="digitalRunEvidence"
            value={value("digitalRunEvidence")}
            onChange={(e) => onChange("digitalRunEvidence", e.target.value)}
            placeholder='{"analysisSoftware":"...","acceptedPartitions":...,"thresholdPolicy":"...","rainReview":"..."}'
            className="mt-1 min-h-24 w-full rounded-lg border border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Imported evidence is provenance only. It never changes primer ranking.
          </p>
        </div>
      ) : null}
      <FlankingNumericRecipeFields
        moduleId="digital-pcr"
        protocol={value("digitalProtocol")}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}
