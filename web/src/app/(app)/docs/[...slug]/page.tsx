import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Doc = {
  title: string;
  description: string;
  sections: { heading: string; paragraphs: string[]; bullets?: string[] }[];
};

const DOCS: Record<string, Doc> = {
  "quick-start": {
    title: "Quick Start",
    description: "Design your first primer pair and understand what the result means.",
    sections: [
      {
        heading: "Try a design",
        paragraphs: [
          "Open Try it without an account, paste a FASTA sequence or bare bases, and choose Design Primers. The guest tool keeps the calculation in scratchpad mode and does not save a project.",
        ],
        bullets: [
          "Use a sequence long enough to contain a plausible amplicon.",
          "Read the discarded-candidate reasons as part of the result, not as an internal log.",
          "Create an account when you need to save the target, settings, and run history.",
        ],
      },
      {
        heading: "Choose a module",
        paragraphs: [
          "A module describes the assay you are trying to build. Its fields and constraints come from the design core, so the interface does not silently invent defaults for a module it does not understand.",
        ],
      },
    ],
  },
  account: {
    title: "Creating an Account",
    description: "Sign up, protect access to your work, and keep the recovery code safe.",
    sections: [
      {
        heading: "What registration does",
        paragraphs: [
          "Registration creates an account, starts a session, and shows a one-time recovery code. The code is stored only as a hash and cannot be displayed again after you leave the panel.",
        ],
        bullets: [
          "Use a password of at least 10 characters.",
          "Save the recovery code in a password manager or another secure place.",
          "Do not put the recovery code in a URL, issue, screenshot, or shared export.",
        ],
      },
      {
        heading: "Sessions",
        paragraphs: [
          "Keep me signed in controls whether the browser retains the session cookie across restarts. Signing out everywhere invalidates every session, including the current one.",
        ],
      },
    ],
  },
  projects: {
    title: "Understanding Projects",
    description: "Keep a target, its settings, and reproducible design runs together.",
    sections: [
      {
        heading: "A project is the record of a decision",
        paragraphs: [
          "A project contains the target sequence, draft settings, notes, and saved runs. Each run keeps both the request and the result, so a primer choice can be reconstructed rather than merely copied.",
        ],
      },
      {
        heading: "Deletion and export",
        paragraphs: [
          "Export a JSON backup before deleting an account or moving work to another instance. Deleting an account removes its projects, runs, and sessions in one operation; there is no recycle bin.",
        ],
      },
    ],
  },
  guides: {
    title: "Design Guides",
    description: "Choose a guide by the scientific question the assay must answer.",
    sections: [
      {
        heading: "Start with the constraint",
        paragraphs: [
          "The catalogue groups modules by what the design must be checked against. Use the module description and compatibility matrix to confirm the assay fits before tuning individual constraints.",
        ],
        bullets: [
          "Template-only amplification: flanking or standard PCR.",
          "Quantification: short, consistently amplifying products and probe-aware assays.",
          "Assembly, mutagenesis, tiling, and genotype-specific work each use their own fields.",
        ],
      },
    ],
  },
  "guides/flanking": {
    title: "Flanking Primers",
    description: "Standard primer pairs that amplify a chosen region of a template.",
    sections: [
      {
        heading: "What is checked",
        paragraphs: [
          "The engine searches for a forward and reverse primer around the target, then checks length, melting temperature, GC composition, self-complementarity, pair complementarity, and product size against the selected reaction.",
        ],
      },
      {
        heading: "Specificity",
        paragraphs: [
          "A template-only design is not an off-target claim. Supply a background when the assay must reject related sequences; the result reports when no background was checked.",
        ],
      },
    ],
  },
  "guides/probe": {
    title: "Probe Assays",
    description: "Design primer pairs with a probe window for quantitative detection.",
    sections: [
      {
        heading: "The probe is part of the assay",
        paragraphs: [
          "A probe assay evaluates the probe placement and its interaction with the pair, not just two primers independently. Keep the target window and reaction conditions consistent with the chemistry you will run.",
        ],
      },
    ],
  },
  "guides/mutagenic": {
    title: "Mutagenic Primers",
    description: "Place a deliberate substitution, insertion, or deletion in a primer pair.",
    sections: [
      {
        heading: "Describe the edit exactly",
        paragraphs: [
          "The edit is validated against the supplied plasmid or template before a search begins. Substitutions, insertions, and deletions have different geometry; do not represent one as another just to fit a field.",
        ],
      },
    ],
  },
  "guides/junction": {
    title: "Junction Primers",
    description: "Design primers across fragments for an assembly plan.",
    sections: [
      {
        heading: "Assembly plans",
        paragraphs: [
          "Name every fragment and identify which portions are amplified. The engine keeps junction geometry and fragment orientation explicit, so an incomplete plan is refused before a worker is started.",
        ],
      },
    ],
  },
  "guides/tiling": {
    title: "Tiling Schemes",
    description: "Cover a long template with overlapping amplicons and defined pools.",
    sections: [
      {
        heading: "Coverage is a design constraint",
        paragraphs: [
          "A tiling scheme reports the intervals and pools required to cover the requested region. Overlap and pooling are checked before the search so a single-pool or zero-overlap request is explained instead of silently changed.",
        ],
      },
    ],
  },
  models: {
    title: "Thermodynamic Models",
    description: "Understand the models and reaction assumptions behind reported values.",
    sections: [
      {
        heading: "A number has conditions",
        paragraphs: [
          "Melting temperature is computed from a named model and the selected reaction conditions. It is not a universal property of an oligo, and changing salt, magnesium, concentration, or polymerase changes the interpretation.",
        ],
      },
    ],
  },
  specificity: {
    title: "Specificity & Backgrounds",
    description: "Know what an off-target check can and cannot establish.",
    sections: [
      {
        heading: "Give the background you mean",
        paragraphs: [
          "Specificity is assessed against the background sequences supplied to the design. An empty background is not treated as proof of specificity; the result states that the check was not performed.",
        ],
      },
    ],
  },
  limits: {
    title: "Rate Limits & Quotas",
    description: "Plan requests around the service limits and project ceilings.",
    sections: [
      {
        heading: "Why limits exist",
        paragraphs: [
          "Design, alignment, and sequence lookup perform real computation. Per-caller rate limits protect the shared worker and return a structured explanation when the ceiling is reached; retry after the stated window rather than rapidly repeating the request.",
        ],
      },
      {
        heading: "Project storage",
        paragraphs: [
          "Projects, runs, notes, and JSON documents are bounded before storage. A refusal names the field or limit so the input can be corrected without truncation.",
        ],
      },
    ],
  },
  export: {
    title: "Export & Import Format",
    description: "Move your projects without losing the request beside the result.",
    sections: [
      {
        heading: "Portable JSON",
        paragraphs: [
          "An export contains the projects, drafts, notes, and saved runs in a versioned JSON document. Import validates the whole document and commits it transactionally, so a failed import does not leave half a project behind.",
        ],
      },
    ],
  },
  "api/auth": {
    title: "API Authentication",
    description: "Understand sessions and the bearer token used by the core API.",
    sections: [
      {
        heading: "Session flow",
        paragraphs: [
          "Register or sign in to receive a bearer token and expiry. The web application keeps that token in an HTTP-only cookie and forwards it server-side; browser code never needs the core API address.",
        ],
      },
    ],
  },
  "api/design": {
    title: "Design Endpoints",
    description: "Submit a module-specific request and read a structured result.",
    sections: [
      {
        heading: "Use the catalogue as the contract",
        paragraphs: [
          "List modules and presets first. Submit only fields declared for the selected module; unknown fields and incompatible modifiers are rejected before a worker is paid for.",
        ],
      },
    ],
  },
  "api/projects": {
    title: "Project Management API",
    description: "Create, update, list, export, and delete authenticated projects.",
    sections: [
      {
        heading: "Ownership is enforced server-side",
        paragraphs: [
          "Every project operation requires a valid session and checks ownership in the core. A guessed project id does not reveal whether another account owns it.",
        ],
      },
    ],
  },
  "api/catalogue": {
    title: "Catalogue & Modules API",
    description: "Discover the design systems and vocabulary supported by this build.",
    sections: [
      {
        heading: "The registry is authoritative",
        paragraphs: [
          "The catalogue publishes modules, goals, engines, modifiers, statuses, and presets. The interface renders those answers rather than maintaining a second hard-coded list.",
        ],
      },
    ],
  },
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}): Promise<Metadata> {
  const doc = DOCS[(await params).slug.join("/")];
  return doc ? { title: doc.title, description: doc.description } : { title: "Documentation" };
}

export default async function DocumentationArticle({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const doc = DOCS[(await params).slug.join("/")];
  if (!doc) return notFound();

  return (
    <div className="space-y-6">
      <PageHeader
        title={doc.title}
        description={doc.description}
        actions={
          <Button render={<Link href="/docs" />} variant="outline" size="sm">
            All documentation
          </Button>
        }
      />

      <div className="mx-auto grid max-w-4xl gap-5">
        {doc.sections.map((section, index) => (
          <Card key={section.heading} className="workbench-card">
            <CardHeader>
              <div className="flex items-start gap-3">
                <span
                  className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-semibold text-primary"
                  aria-hidden="true"
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <CardTitle className="pt-0.5 font-serif text-base font-semibold">
                  {section.heading}
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
              {section.bullets ? (
                <ul className="list-inside list-disc space-y-1.5">
                  {section.bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
