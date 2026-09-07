import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowRight, ExternalLink, FileText, Code, BookOpen, Search } from "lucide-react";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Documentation",
  description: "Guides, API reference, and tutorials for getting the most out of PCRStudio.",
};

const sections = [
  {
    title: "Getting Started",
    description: "New to PCRStudio? Start here to learn the basics.",
    items: [
      {
        label: "Quick Start",
        href: "/docs/quick-start",
        description: "Design your first primers in 5 minutes",
        icon: ArrowRight,
      },
      {
        label: "Creating an Account",
        href: "/docs/account",
        description: "Sign up and save your projects",
        icon: ArrowRight,
      },
      {
        label: "Understanding Projects",
        href: "/docs/projects",
        description: "Organise targets, settings, and runs",
        icon: ArrowRight,
      },
    ],
  },
  {
    title: "Design Guides",
    description: "Deep dives into each design system and when to use it.",
    items: [
      {
        label: "Flanking Primers",
        href: "/docs/guides/flanking",
        description: "Standard PCR primer pairs for amplification",
        icon: Search,
      },
      {
        label: "Probe Assays",
        href: "/docs/guides/probe",
        description: "qPCR and digital PCR with hydrolysis probes",
        icon: Search,
      },
      {
        label: "Mutagenic Primers",
        href: "/docs/guides/mutagenic",
        description: "Site-directed mutagenesis designs",
        icon: Search,
      },
      {
        label: "Junction Primers",
        href: "/docs/guides/junction",
        description: "Gibson, NEBuilder, and other assembly methods",
        icon: Search,
      },
      {
        label: "Tiling Schemes",
        href: "/docs/guides/tiling",
        description: "Large amplicon sequencing across genomes",
        icon: Search,
      },
    ],
  },
  {
    title: "Reference",
    description: "Technical details for advanced usage.",
    items: [
      {
        label: "Thermodynamic Models",
        href: "/docs/models",
        description: "Nearest-neighbor parameters and salt corrections",
        icon: FileText,
      },
      {
        label: "Specificity & Backgrounds",
        href: "/docs/specificity",
        description: "How off-target detection works",
        icon: Search,
      },
      {
        label: "Rate Limits & Quotas",
        href: "/docs/limits",
        description: "API limits and best practices",
        icon: Code,
      },
      {
        label: "Export & Import Format",
        href: "/docs/export",
        description: "JSON schema for portability",
        icon: FileText,
      },
    ],
  },
  {
    title: "API Reference",
    description: "Programmatic access for automation and integration.",
    items: [
      {
        label: "Authentication",
        href: "/docs/api/auth",
        description: "Session tokens and API keys",
        icon: Code,
      },
      {
        label: "Design Endpoints",
        href: "/docs/api/design",
        description: "Submit and retrieve designs",
        icon: Code,
      },
      {
        label: "Project Management",
        href: "/docs/api/projects",
        description: "CRUD for projects and runs",
        icon: Code,
      },
      {
        label: "Catalogue & Modules",
        href: "/docs/api/catalogue",
        description: "List available design systems",
        icon: Code,
      },
    ],
  },
];

export default function DocsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Documentation"
        description="Guides, API reference, and tutorials for getting the most out of PCRStudio."
        actions={
          <Button
            render={
              <a
                href={`${site.repository}/tree/main/docs`}
                target="_blank"
                rel="noreferrer noopener"
              />
            }
            variant="outline"
            size="sm"
          >
            <ExternalLink />
            View on GitHub
          </Button>
        }
      />

      {sections.map((section) => (
        <section
          key={section.title}
          className="rounded-2xl border border-border/60 bg-surface-warm/20 p-4 sm:p-5"
        >
          <div className="mb-4 flex items-baseline justify-between gap-4">
            <div>
              <h2 className="font-serif text-xl font-semibold text-foreground">{section.title}</h2>
              <p className="text-sm text-muted-foreground">{section.description}</p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {section.items.map((item) => (
              <Card
                key={item.href}
                className="workbench-card transition-colors hover:-translate-y-0.5 hover:border-primary/30"
              >
                <CardContent className="space-y-3 p-5">
                  <div className="flex items-start gap-3">
                    <div
                      className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
                      aria-hidden="true"
                    >
                      <item.icon className="size-4.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-serif text-base font-semibold text-foreground">
                        {item.label}
                      </h3>
                      <p className="line-clamp-2 text-xs text-muted-foreground">
                        {item.description}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-between"
                    render={<Link href={item.href} />}
                  >
                    Read guide <ArrowRight className="ml-1 size-3.5" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}

      <Card className="workbench-hero border-primary/40">
        <CardContent className="space-y-4 px-6 pt-6 pb-6 text-center">
          <BookOpen className="mx-auto size-10 text-primary/80" aria-hidden="true" />
          <div className="space-y-2">
            <h3 className="font-serif text-lg font-semibold text-foreground">
              Want to contribute?
            </h3>
            <p className="mx-auto max-w-prose text-sm text-muted-foreground">
              This documentation accompanies proprietary software. Found an error, missing topic, or
              unclear explanation? Contact the project team with the details.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            render={
              <a
                href={`${site.repository}/tree/main/docs`}
                target="_blank"
                rel="noreferrer noopener"
              />
            }
          >
            <ExternalLink className="mr-1.5 size-3.5" aria-hidden="true" />
            Contribute on GitHub
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
