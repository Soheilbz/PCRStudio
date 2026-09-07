"use client";

/**
 * Asking for several targets that will share a tube.
 *
 * The form is a list rather than the stepped single-target one, because the
 * thing being described is a relationship between targets and there is no
 * order to walk through: every target is on the same footing and the answer
 * depends on all of them at once.
 *
 * The readout has no default and the form will not submit without it. That is
 * deliberate and it is the one place this form is stricter than it looks:
 * two products thirty bases apart are one band on a gel, two peaks on a
 * capillary, and not a question at all for sequencing, so guessing it would be
 * guessing the answer.
 */

import { Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";

import { MultiplexResultView } from "@/components/design/multiplex-result";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { count } from "@/lib/numbers";
import type { MultiplexResult } from "@/lib/api/types";
import { runMultiplexAction, type MultiplexState } from "@/lib/projects/actions";

const READOUTS = [
  {
    id: "agarose",
    title: "A gel",
    detail: "Bands are told apart by size, and how far apart they must be depends on the largest.",
  },
  {
    id: "capillary",
    title: "Capillary electrophoresis",
    detail:
      "Resolution depends on the instrument/cartridge. Scientific-Strict asks for a named QIAxcel reference instead of assuming one number.",
  },
  {
    id: "ngs",
    title: "Sequencing",
    detail: "Reads are assigned by sequence, so two products of the same length are not a problem.",
  },
] as const;

interface Target {
  name: string;
  template: string;
  background: string;
  inclusivity: string;
  inclusivityPanelProvenance: string;
  backgroundPanelProvenance: string;
  speciesPanelSelectionRationale: string;
  speciesTargetTaxid: string;
  speciesTaxonomySnapshot: string;
  speciesDatabaseSnapshot: string;
  speciesPanelAccessionManifest: string;
  speciesPanelRecordMetadataManifest: string;
  speciesPanelRetrievedDate: string;
  min: string;
  max: string;
  tube: string;
  primerConcentrationNm: string;
  empiricalEvidenceRef: string;
}

const BLANK: Target = {
  name: "",
  template: "",
  background: "",
  inclusivity: "",
  inclusivityPanelProvenance: "",
  backgroundPanelProvenance: "",
  speciesPanelSelectionRationale: "",
  speciesTargetTaxid: "",
  speciesTaxonomySnapshot: "",
  speciesDatabaseSnapshot: "",
  speciesPanelAccessionManifest: "",
  speciesPanelRecordMetadataManifest: "",
  speciesPanelRetrievedDate: "",
  min: "",
  max: "",
  tube: "",
  primerConcentrationNm: "",
  empiricalEvidenceRef: "",
};
const MAX_TARGETS = 32;
const MAX_TOTAL_INPUT_CHARS = 2_000_000;

export function MultiplexForm({ moduleId }: { moduleId: string }) {
  // Multiplex is advertised only for assays whose complete panel semantics
  // are implemented. qPCR/dPCR/ARMS need probe/channel/cluster-aware engines
  // before they can share this primer-pair/readout-size form honestly.
  const supportsReverseTranscription = moduleId === "standard-pcr";
  const [readout, setReadout] = useState("");
  const [readoutProfile, setReadoutProfile] = useState("");
  const [perTube, setPerTube] = useState("");
  const [optimizerMode, setOptimizerMode] = useState<"exact" | "local">("exact");
  const [targets, setTargets] = useState<Target[]>([{ ...BLANK }, { ...BLANK }]);
  const [fromRna, setFromRna] = useState(false);
  const [standardPcrProtocol, setStandardPcrProtocol] = useState("not-selected");
  const [colonyHostClass, setColonyHostClass] = useState("");
  const [colonyPreparation, setColonyPreparation] = useState("");
  const [colonyProtocolId, setColonyProtocolId] = useState("");
  const [colonyProtocolName, setColonyProtocolName] = useState("");
  const [colonyProtocolProvenance, setColonyProtocolProvenance] = useState("");
  const [state, setState] = useState<MultiplexState>({});
  const [pending, start] = useTransition();

  const populatedTargets = targets.filter((target) => target.template.trim());
  const totalInputChars = targets.reduce(
    (total, target) =>
      total +
      target.template.length +
      target.background.length +
      target.inclusivity.length +
      target.inclusivityPanelProvenance.length +
      target.backgroundPanelProvenance.length +
      target.speciesPanelSelectionRationale.length +
      target.speciesTaxonomySnapshot.length +
      target.speciesDatabaseSnapshot.length +
      target.speciesPanelAccessionManifest.length +
      target.speciesPanelRecordMetadataManifest.length +
      target.speciesPanelRetrievedDate.length +
      target.speciesTargetTaxid.length,
    0,
  );
  const inputTooLarge = totalInputChars > MAX_TOTAL_INPUT_CHARS;
  const speciesSpecificContextComplete =
    moduleId !== "species-specific-pcr" ||
    populatedTargets.every(
      (target) =>
        target.background.trim() &&
        target.inclusivity.trim() &&
        target.inclusivityPanelProvenance.trim() &&
        target.backgroundPanelProvenance.trim() &&
        target.speciesPanelSelectionRationale.trim() &&
        Number(target.speciesTargetTaxid) > 0 &&
        target.speciesTaxonomySnapshot.trim() &&
        target.speciesDatabaseSnapshot.trim() &&
        target.speciesPanelAccessionManifest.trim() &&
        target.speciesPanelRecordMetadataManifest.trim() &&
        target.speciesPanelRetrievedDate.trim(),
    );
  const colonyContextComplete =
    moduleId !== "colony-pcr" ||
    Boolean(
      colonyHostClass &&
      colonyPreparation &&
      colonyProtocolId &&
      (colonyProtocolId !== "custom-sop" ||
        (colonyProtocolName.trim() && colonyProtocolProvenance.trim())),
    );
  const scientificContextComplete = speciesSpecificContextComplete && colonyContextComplete;
  const readoutReferenceReady =
    readout === "ngs" ||
    (readout === "agarose" && readoutProfile === "qiagen-multiplex-agarose-guideline") ||
    (readout === "capillary" && Boolean(readoutProfile));
  const perTubeNumber = perTube.trim() ? Number(perTube) : undefined;
  const perTubeValid =
    perTubeNumber === undefined ||
    (Number.isInteger(perTubeNumber) && perTubeNumber >= 1 && perTubeNumber <= MAX_TARGETS);
  const ready =
    Boolean(readout) &&
    readoutReferenceReady &&
    perTubeValid &&
    populatedTargets.length >= 2 &&
    !inputTooLarge &&
    scientificContextComplete;

  const update = (index: number, patch: Partial<Target>) =>
    setTargets((all) => all.map((target, at) => (at === index ? { ...target, ...patch } : target)));

  return (
    <div className="space-y-5">
      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-base font-semibold">
            How will you read the products?
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div
            className="grid gap-2 sm:grid-cols-3"
            role="group"
            aria-label="Multiplex readout method"
          >
            {READOUTS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setReadout(option.id)}
                aria-pressed={readout === option.id}
                className={
                  readout === option.id
                    ? "rounded-lg border border-primary bg-primary/5 p-3 text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    : "rounded-lg border border-border/70 p-3 text-left transition-colors hover:border-primary/30 hover:bg-surface-warm/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                }
              >
                <span className="block text-xs font-medium">{option.title}</span>
                <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                  {option.detail}
                </span>
              </button>
            ))}
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            No default, because it decides the answer rather than decorating it.
          </p>
        </CardContent>
      </Card>

      {readout === "agarose" ? (
        <Card className="workbench-card">
          <CardHeader>
            <CardTitle className="font-serif text-base font-semibold">
              Agarose reference profile
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <label className="flex items-start gap-2 text-xs">
              <input
                type="radio"
                name="agarose-profile-ui"
                checked={readoutProfile === "qiagen-multiplex-agarose-guideline"}
                onChange={() => setReadoutProfile("qiagen-multiplex-agarose-guideline")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">QIAGEN Multiplex PCR agarose guideline</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Uses the supplier fragment-size / gel-percentage spacing table as a conservative
                  selection reference. It is not a prediction of your actual gel resolution.
                </span>
              </span>
            </label>
          </CardContent>
        </Card>
      ) : null}

      {readout === "capillary" ? (
        <Card className="workbench-card">
          <CardHeader>
            <CardTitle className="font-serif text-base font-semibold">
              Capillary reference profile
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <label className="flex items-start gap-2 text-xs">
              <input
                type="radio"
                name="capillary-profile-ui"
                checked={readoutProfile === "qiagen-qiaxcel-high-resolution"}
                onChange={() => setReadoutProfile("qiagen-qiaxcel-high-resolution")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">QIAGEN QIAxcel High Resolution</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Uses the supplier resolution envelope (3–5 bp at 100–500 bp; wider at larger
                  fragments) as a reference-risk screen.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-xs">
              <input
                type="radio"
                name="capillary-profile-ui"
                checked={readoutProfile === "qiagen-qiaxcel-screening"}
                onChange={() => setReadoutProfile("qiagen-qiaxcel-screening")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">QIAGEN QIAxcel Screening</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Uses the supplier screening-cartridge resolution ranges. It is not extrapolated to
                  an unnamed capillary platform.
                </span>
              </span>
            </label>
          </CardContent>
        </Card>
      ) : null}

      {moduleId === "standard-pcr" ? (
        <Card className="workbench-card">
          <CardHeader>
            <CardTitle className="font-serif text-base font-semibold">
              Shared Standard-PCR chemistry
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Optional tube-level bench/provenance overlay. Every target in this physical multiplex
              reaction is designed against the same named polymerase protocol; PCRStudio does not
              mix per-target chemistries or reconstruct proprietary buffer thermodynamics.
            </p>
            <Label htmlFor="multiplex-standard-pcr-protocol" className="text-xs">
              Shared Standard-PCR protocol
            </Label>
            <select
              id="multiplex-standard-pcr-protocol"
              value={standardPcrProtocol}
              onChange={(event) => setStandardPcrProtocol(event.target.value)}
              className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-lg"
            >
              <option value="not-selected">Not selected · design/screening only</option>
              <option value="neb-taq-m0273">NEB Taq DNA Polymerase M0273</option>
              <option value="neb-q5-hot-start-m0493">NEB Q5 Hot Start High-Fidelity M0493</option>
              <option value="neb-q5u-hot-start-m0515">NEB Q5U Hot Start High-Fidelity M0515</option>
              <option value="thermo-dreamtaq-hot-start-ep170x">
                Thermo DreamTaq Hot Start EP1701–EP1704
              </option>
              <option value="thermo-phusion-plus">Thermo Phusion Plus DNA Polymerase</option>
              <option value="promega-gotaq-m300">Promega GoTaq DNA Polymerase M300</option>
              <option value="thermo-platinum-superfi-ii">
                Thermo Fisher Platinum SuperFi II PCR Master Mix
              </option>
              <option value="neb-onetaq-hot-start-m0484">
                NEB OneTaq Hot Start 2X · Standard Buffer M0484
              </option>
              <option value="neb-onetaq-hot-start-gc-m0485">
                NEB OneTaq Hot Start 2X · GC Buffer M0485
              </option>
              <option value="neb-onetaq-hot-start-quickload-m0488">
                NEB OneTaq Hot Start Quick-Load 2X · Standard M0488
              </option>
              <option value="neb-onetaq-hot-start-quickload-gc-m0489">
                NEB OneTaq Hot Start Quick-Load 2X · GC M0489
              </option>
              <option value="pcrbio-hs-taq-mix-pb10-22">
                PCR Biosystems PCRBIO HS Taq Mix PB10.22
              </option>
              <option value="qiagen-alltaq-master-mix-203144">QIAGEN AllTaq Master Mix</option>
              <option value="thermo-platinum-ii-taq-hot-start">
                Thermo Fisher Platinum II Taq Hot-Start
              </option>
              <option value="toyobo-kod-one-kmm101">TOYOBO KOD One PCR Master Mix KMM-101</option>
              <option value="neb-multiplex-pcr-m0284">
                NEB Multiplex PCR 5X Master Mix M0284 · dedicated multiplex chemistry
              </option>
            </select>
            <p className="text-xs leading-relaxed text-muted-foreground">
              “Not selected” intentionally emits no named bench protocol. A selected protocol is
              shared across all targets and remains separate from the generic Primer3 screening
              model.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {moduleId === "colony-pcr" ? (
        <Card className="workbench-card">
          <CardHeader>
            <CardTitle className="font-serif text-base font-semibold">
              Shared colony-PCR provenance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Every target in this multiplex tube uses the same crude-template preparation. Host
              class, preparation branch and the named vendor/laboratory SOP are required evidence;
              PCRStudio does not infer a universal lysis or cycling recipe.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="multiplex-colony-host" className="text-xs">
                  Host class
                </Label>
                <select
                  id="multiplex-colony-host"
                  required
                  value={colonyHostClass}
                  onChange={(event) => setColonyHostClass(event.target.value)}
                  className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <option value="">Choose host class</option>
                  <option value="bacterial">Bacterial</option>
                  <option value="yeast">Yeast</option>
                  <option value="filamentous-fungus">Filamentous fungus</option>
                  <option value="microalgae">Microalgae</option>
                  <option value="other">Other / validated SOP</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="multiplex-colony-preparation" className="text-xs">
                  Template preparation
                </Label>
                <select
                  id="multiplex-colony-preparation"
                  required
                  value={colonyPreparation}
                  onChange={(event) => setColonyPreparation(event.target.value)}
                  className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <option value="">Choose preparation</option>
                  <option value="direct-transfer">Direct colony transfer</option>
                  <option value="liquid-culture">Liquid / overnight culture</option>
                  <option value="water-lysate">Water lysate</option>
                  <option value="buffer-lysate">Buffer / TE lysate</option>
                  <option value="host-specific-lysis">Host-specific lysis</option>
                  <option value="other">Other validated preparation</option>
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="multiplex-colony-protocol" className="text-xs">
                Shared colony-PCR workflow
              </Label>
              <select
                id="multiplex-colony-protocol"
                required
                value={colonyProtocolId}
                onChange={(event) => setColonyProtocolId(event.target.value)}
                className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose exact workflow</option>
                <option value="neb-onetaq-m0482-colony">
                  NEB OneTaq M0482 · bacterial direct colony
                </option>
                <option value="neb-onetaq-hotstart-m0488-colony">
                  NEB OneTaq Hot Start Quick-Load M0488 · bacterial direct colony
                </option>
                <option value="neb-insert-screening-e1202">
                  NEB Insert Screening E1202 · bacterial direct colony
                </option>
                <option value="pcrbio-hs-taq-pb10-22-colony">
                  PCRBIO HS Taq PB10.22 · bacterial colony/culture
                </option>
                <option value="custom-sop">Custom / laboratory SOP</option>
              </select>
            </div>
            {colonyProtocolId === "custom-sop" ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="multiplex-colony-sop" className="text-xs">
                    Laboratory SOP identity
                  </Label>
                  <Input
                    id="multiplex-colony-sop"
                    required
                    value={colonyProtocolName}
                    onChange={(event) => setColonyProtocolName(event.target.value)}
                    placeholder="lab SOP identity / revision"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="multiplex-colony-sop-provenance" className="text-xs">
                    SOP source / revision provenance
                  </Label>
                  <Input
                    id="multiplex-colony-sop-provenance"
                    required
                    value={colonyProtocolProvenance}
                    onChange={(event) => setColonyProtocolProvenance(event.target.value)}
                    placeholder="owner/source + revision/date"
                  />
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {targets.map((target, index) => (
        <Card key={index} className="workbench-card">
          <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
            <CardTitle className="font-serif text-base font-semibold">
              Target {index + 1}
              {target.name ? ` — ${target.name}` : ""}
            </CardTitle>
            {targets.length > 2 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setTargets((all) => all.filter((_, at) => at !== index))}
                aria-label={`Remove target ${index + 1}`}
              >
                <Trash2 className="size-3.5" />
              </Button>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor={`target_${index}_name`} className="text-xs">
                  Call it
                </Label>
                <Input
                  id={`target_${index}_name`}
                  aria-label={`Target ${index + 1} name`}
                  value={target.name}
                  onChange={(event) => update(index, { name: event.target.value })}
                  placeholder={`target ${index + 1}`}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`target_${index}_tube`} className="text-xs">
                  Tube / pool identity
                </Label>
                <Input
                  id={`target_${index}_tube`}
                  aria-label={`Target ${index + 1} tube identity`}
                  value={target.tube}
                  onChange={(event) => update(index, { tube: event.target.value })}
                  placeholder="blank = same tube; e.g. pool-A"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`target_${index}_primer_concentration`} className="text-xs">
                  Primer concentration (nM)
                </Label>
                <Input
                  id={`target_${index}_primer_concentration`}
                  inputMode="decimal"
                  value={target.primerConcentrationNm}
                  onChange={(event) => update(index, { primerConcentrationNm: event.target.value })}
                  placeholder="optional; e.g. 200"
                />
                <p className="text-xs leading-relaxed text-muted-foreground">
                  Planned/measured formulation evidence only; never used to rank sequences.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`target_${index}_empirical_evidence`} className="text-xs">
                  Balancing evidence
                </Label>
                <Input
                  id={`target_${index}_empirical_evidence`}
                  value={target.empiricalEvidenceRef}
                  onChange={(event) => update(index, { empiricalEvidenceRef: event.target.value })}
                  placeholder="optional run/report/lot reference"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`target_${index}_min`} className="text-xs">
                  Shortest product
                </Label>
                <Input
                  id={`target_${index}_min`}
                  aria-label={`Target ${index + 1} shortest product`}
                  type="number"
                  min={50}
                  value={target.min}
                  onChange={(event) => update(index, { min: event.target.value })}
                  placeholder="150"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`target_${index}_max`} className="text-xs">
                  Longest product
                </Label>
                <Input
                  id={`target_${index}_max`}
                  aria-label={`Target ${index + 1} longest product`}
                  type="number"
                  min={50}
                  value={target.max}
                  onChange={(event) => update(index, { max: event.target.value })}
                  placeholder="300"
                />
              </div>
            </div>
            <Textarea
              aria-label={`Target ${index + 1} sequence`}
              value={target.template}
              onChange={(event) => update(index, { template: event.target.value })}
              placeholder=">exon 5&#10;ATGCGTACGATCGATCG…"
              className="min-h-28 font-mono text-xs"
            />
            {moduleId === "species-specific-pcr" ? (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`target_${index}_inclusivity`} className="text-xs">
                      Intended-target diversity (required)
                    </Label>
                    <Textarea
                      id={`target_${index}_inclusivity`}
                      aria-label={`Target ${index + 1} inclusivity panel`}
                      value={target.inclusivity}
                      onChange={(event) => update(index, { inclusivity: event.target.value })}
                      placeholder=">strain-a\nACGT…\n>strain-b\nACGT…"
                      className="min-h-24 font-mono text-xs"
                    />
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      Strict species-specific design needs an explicit target-diversity panel.
                      Preserve accession/version, isolate/strain and taxonomy context in FASTA
                      headers where available; the panel fingerprint proves submitted-content
                      identity, not taxonomic completeness.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`target_${index}_background`} className="text-xs">
                      Relatives to exclude (required)
                    </Label>
                    <Textarea
                      id={`target_${index}_background`}
                      aria-label={`Target ${index + 1} exclusion background`}
                      value={target.background}
                      onChange={(event) => update(index, { background: event.target.value })}
                      placeholder=">near-neighbour\nACGT…"
                      className="min-h-24 font-mono text-xs"
                    />
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      Include the sequences this target must not amplify. Inclusivity and exclusion
                      are separate claims; neither substitutes for the other.
                    </p>
                  </div>
                </div>
                <div className="grid gap-3 lg:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label
                      htmlFor={`target_${index}_inclusivity_panel_provenance`}
                      className="text-xs"
                    >
                      Inclusivity provenance (required)
                    </Label>
                    <Textarea
                      id={`target_${index}_inclusivity_panel_provenance`}
                      value={target.inclusivityPanelProvenance}
                      onChange={(event) =>
                        update(index, { inclusivityPanelProvenance: event.target.value })
                      }
                      placeholder="Database/release, accession.version, retrieval date, isolate/source…"
                      className="min-h-20 text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label
                      htmlFor={`target_${index}_background_panel_provenance`}
                      className="text-xs"
                    >
                      Exclusion provenance (required)
                    </Label>
                    <Textarea
                      id={`target_${index}_background_panel_provenance`}
                      value={target.backgroundPanelProvenance}
                      onChange={(event) =>
                        update(index, { backgroundPanelProvenance: event.target.value })
                      }
                      placeholder="Database/release, accession.version, retrieval date, near-neighbour source…"
                      className="min-h-20 text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label
                      htmlFor={`target_${index}_species_panel_selection_rationale`}
                      className="text-xs"
                    >
                      Panel-selection rationale (required)
                    </Label>
                    <Textarea
                      id={`target_${index}_species_panel_selection_rationale`}
                      value={target.speciesPanelSelectionRationale}
                      onChange={(event) =>
                        update(index, { speciesPanelSelectionRationale: event.target.value })
                      }
                      placeholder="Phylogenetic/geographic diversity and near-neighbour inclusion rationale…"
                      className="min-h-20 text-xs"
                    />
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`target_${index}_taxid`} className="text-xs">
                      Target TaxID
                    </Label>
                    <Input
                      id={`target_${index}_taxid`}
                      type="number"
                      min={1}
                      required
                      value={target.speciesTargetTaxid}
                      onChange={(event) =>
                        update(index, { speciesTargetTaxid: event.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`target_${index}_retrieved`} className="text-xs">
                      Panel retrieval date
                    </Label>
                    <Input
                      id={`target_${index}_retrieved`}
                      type="date"
                      required
                      value={target.speciesPanelRetrievedDate}
                      onChange={(event) =>
                        update(index, { speciesPanelRetrievedDate: event.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`target_${index}_taxonomy`} className="text-xs">
                      Taxonomy snapshot
                    </Label>
                    <Input
                      id={`target_${index}_taxonomy`}
                      required
                      value={target.speciesTaxonomySnapshot}
                      onChange={(event) =>
                        update(index, { speciesTaxonomySnapshot: event.target.value })
                      }
                      placeholder="NCBI Taxonomy snapshot/release"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`target_${index}_database`} className="text-xs">
                      Sequence database snapshot
                    </Label>
                    <Input
                      id={`target_${index}_database`}
                      required
                      value={target.speciesDatabaseSnapshot}
                      onChange={(event) =>
                        update(index, { speciesDatabaseSnapshot: event.target.value })
                      }
                      placeholder="RefSeq/database release + date"
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`target_${index}_accessions`} className="text-xs">
                    Accession.version manifest
                  </Label>
                  <Textarea
                    id={`target_${index}_accessions`}
                    required
                    value={target.speciesPanelAccessionManifest}
                    onChange={(event) =>
                      update(index, { speciesPanelAccessionManifest: event.target.value })
                    }
                    placeholder="Exact inclusivity/exclusivity accession.version list"
                    className="min-h-20 font-mono text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`target_${index}_record_metadata`} className="text-xs">
                    Record metadata manifest
                  </Label>
                  <Textarea
                    id={`target_${index}_record_metadata`}
                    required
                    value={target.speciesPanelRecordMetadataManifest}
                    onChange={(event) =>
                      update(index, { speciesPanelRecordMetadataManifest: event.target.value })
                    }
                    placeholder="record_id\taccession.version\trole\ttopology\toptional_weight\toptional_group"
                    className="min-h-20 font-mono text-xs"
                  />
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  PCRStudio records these declarations and fingerprints the submitted sequences; it
                  does not independently verify taxonomy, database completeness, or population
                  representativeness.
                </p>
              </div>
            ) : null}
            <p className="text-xs text-muted-foreground">
              {count(target.template.replace(/[^A-Za-z]/g, "").length)} bases
            </p>
          </CardContent>
        </Card>
      ))}

      {supportsReverseTranscription ? (
        <label className="flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            checked={fromRna}
            onChange={(event) => setFromRna(event.target.checked)}
            className="mt-0.5"
          />
          <span>
            <span className="font-medium">The templates start as RNA</span>
            <span className="mt-1 block leading-relaxed text-muted-foreground">
              Record that every target starts from RNA and therefore requires reverse transcription.
              PCRStudio does not infer one-step versus two-step placement, temperature or duration
              from this checkbox; those conditions require a separately named RT chemistry/SOP.
            </span>
          </span>
        </label>
      ) : null}

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-base font-semibold">
            Panel selection fidelity
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Label htmlFor="multiplex-optimizer" className="text-xs">
            Optimizer
          </Label>
          <select
            id="multiplex-optimizer"
            value={optimizerMode}
            onChange={(event) => setOptimizerMode(event.target.value as "exact" | "local")}
            className="h-9 rounded-lg border border-border/70 bg-background px-3 text-sm"
          >
            <option value="exact">Exact bounded search · Scientific-Strict</option>
            <option value="local">Local greedy/swap search · development only</option>
          </select>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Exact mode exhaustively optimizes the evaluated candidate pools using PCRStudio&apos;s
            declared lexicographic objective and fails closed if the bounded state budget is
            exceeded. Local mode is explicitly approximate and is never presented as SADDLE
            simulated annealing.
          </p>
        </CardContent>
      </Card>

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-base font-semibold">Tube architecture</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="max-w-xs space-y-1.5">
            <Label htmlFor="multiplex-per-tube" className="text-xs">
              Maximum targets per tube
            </Label>
            <Input
              id="multiplex-per-tube"
              type="number"
              min={1}
              max={MAX_TARGETS}
              value={perTube}
              onChange={(event) => setPerTube(event.target.value)}
              placeholder={`blank = all ${populatedTargets.length || "targets"} in one tube`}
            />
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Blank means one shared multiplex reaction. In Scientific-Strict, a multi-tube panel must
            give every target an explicit tube/pool identity above; automatic partitioning is a
            labelled development-only heuristic. PrimerPooler proposals can be reviewed externally
            and then entered as explicit tube identities.
          </p>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={targets.length >= MAX_TARGETS}
          onClick={() => setTargets((all) => [...all, { ...BLANK }])}
        >
          <Plus className="size-3.5" />
          Another target
        </Button>

        {targets.length >= MAX_TARGETS ? (
          <p className="text-xs text-muted-foreground">
            Multiplex design supports up to {MAX_TARGETS} targets per request. Split a larger panel
            into separate sets.
          </p>
        ) : null}

        <Button
          type="button"
          size="sm"
          disabled={!ready || pending}
          onClick={() =>
            start(async () => {
              const form = new FormData();
              form.set("readout", readout);
              if ((readout === "agarose" || readout === "capillary") && readoutProfile) {
                form.set("readoutProfile", readoutProfile);
              }
              if (perTube.trim()) form.set("perTube", perTube.trim());
              form.set("optimizerMode", optimizerMode);
              if (fromRna) form.set("fromRna", "true");
              if (moduleId === "standard-pcr") {
                form.set("standardPcrProtocol", standardPcrProtocol);
              }
              if (moduleId === "colony-pcr") {
                form.set("colonyHostClass", colonyHostClass);
                form.set("colonyPreparation", colonyPreparation);
                form.set("colonyProtocolId", colonyProtocolId);
                if (colonyProtocolId === "custom-sop") {
                  form.set("colonyProtocolName", colonyProtocolName.trim());
                  form.set("colonyProtocolProvenance", colonyProtocolProvenance.trim());
                }
              }
              // Indices are compacted here, before serialising: they key both
              // these fields and the collector that reads them back. Numbering
              // by position in the array instead once left a gap where a
              // removed row had been — and a collector walking upward from
              // zero stopped at that gap and submitted nothing.
              targets
                .filter((target) => target.template.trim())
                .forEach((target, index) => {
                  form.set(`target_${index}_template`, target.template);
                  form.set(`target_${index}_name`, target.name);
                  if (target.background.trim()) {
                    form.set(`target_${index}_background`, target.background);
                  }
                  if (target.inclusivity.trim()) {
                    form.set(`target_${index}_inclusivity`, target.inclusivity);
                  }
                  if (target.inclusivityPanelProvenance.trim()) {
                    form.set(
                      `target_${index}_inclusivity_panel_provenance`,
                      target.inclusivityPanelProvenance,
                    );
                  }
                  if (target.backgroundPanelProvenance.trim()) {
                    form.set(
                      `target_${index}_background_panel_provenance`,
                      target.backgroundPanelProvenance,
                    );
                  }
                  if (target.speciesPanelSelectionRationale.trim()) {
                    form.set(
                      `target_${index}_species_panel_selection_rationale`,
                      target.speciesPanelSelectionRationale,
                    );
                  }
                  if (target.speciesTargetTaxid.trim())
                    form.set(
                      `target_${index}_species_target_taxid`,
                      target.speciesTargetTaxid.trim(),
                    );
                  if (target.speciesTaxonomySnapshot.trim())
                    form.set(
                      `target_${index}_species_taxonomy_snapshot`,
                      target.speciesTaxonomySnapshot,
                    );
                  if (target.speciesDatabaseSnapshot.trim())
                    form.set(
                      `target_${index}_species_database_snapshot`,
                      target.speciesDatabaseSnapshot,
                    );
                  if (target.speciesPanelAccessionManifest.trim())
                    form.set(
                      `target_${index}_species_panel_accession_manifest`,
                      target.speciesPanelAccessionManifest,
                    );
                  if (target.speciesPanelRecordMetadataManifest.trim())
                    form.set(
                      `target_${index}_species_panel_record_metadata_manifest`,
                      target.speciesPanelRecordMetadataManifest,
                    );
                  if (target.speciesPanelRetrievedDate.trim())
                    form.set(
                      `target_${index}_species_panel_retrieved_date`,
                      target.speciesPanelRetrievedDate,
                    );
                  if (target.min) form.set(`target_${index}_min`, target.min);
                  if (target.max) form.set(`target_${index}_max`, target.max);
                  if (target.tube.trim()) form.set(`target_${index}_tube`, target.tube.trim());
                  if (target.primerConcentrationNm.trim())
                    form.set(
                      `target_${index}_primer_concentration_nm`,
                      target.primerConcentrationNm.trim(),
                    );
                  if (target.empiricalEvidenceRef.trim())
                    form.set(
                      `target_${index}_empirical_evidence_ref`,
                      target.empiricalEvidenceRef.trim(),
                    );
                });
              setState(await runMultiplexAction(moduleId, form));
            })
          }
        >
          {pending ? "Choosing a set…" : "Design the set"}
        </Button>

        {!ready ? (
          <p className="text-xs text-muted-foreground">
            {inputTooLarge
              ? "The combined sequence input is too large; split the panel or use smaller records."
              : moduleId === "species-specific-pcr" && !speciesSpecificContextComplete
                ? "Each species-specific target needs inclusivity/exclusion panels, provenance for both panels, and a panel-selection rationale."
                : moduleId === "colony-pcr" && !colonyContextComplete
                  ? "Colony multiplexing needs a shared host class, preparation branch, and named vendor/laboratory SOP."
                  : readout === "agarose" && !readoutReferenceReady
                    ? "Choose the named agarose reference profile."
                    : readout === "capillary" && !readoutReferenceReady
                      ? "Choose the capillary cartridge/reference profile."
                      : !perTubeValid
                        ? `Targets per tube must be an integer from 1 to ${MAX_TARGETS}.`
                        : readout
                          ? "Two targets with sequence, at least."
                          : "Choose a readout first."}
          </p>
        ) : null}
      </div>

      {state.error ? (
        <Card className="workbench-card">
          <CardContent className="pt-6">
            <p className="text-sm leading-relaxed text-destructive">{state.error}</p>
          </CardContent>
        </Card>
      ) : null}

      {state.result ? <Result result={state.result} /> : null}
    </div>
  );
}

function Result({ result }: { result: MultiplexResult }) {
  return (
    <div className="workbench-result space-y-3 rounded-2xl border-t border-primary/20 pt-5">
      <MultiplexResultView result={result} />
    </div>
  );
}
