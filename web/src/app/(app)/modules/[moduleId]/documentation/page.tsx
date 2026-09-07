import { ArrowLeft, FileText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import moduleDocumentation from "@/lib/module-documentation.generated.json";
import { loadModule } from "@/lib/api/load";
import { requireUser } from "@/lib/auth/current-user";
import { multiplexCapabilityFor } from "@/lib/multiplex-capabilities";

interface PageProps {
  params: Promise<{ moduleId: string }>;
}

type ModuleDocumentation = {
  citation_accessed: string;
  references: { citation: string; kind: "journal" | "web"; url: string }[];
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { moduleId } = await params;
  const { data: module, missing } = await loadModule(moduleId);
  if (missing) notFound();
  if (!module) return { title: "Module guide", robots: { index: false, follow: true } };

  return {
    title: `${module.name} guide`,
    description: `Scientific and technical sources used to define the ${module.name} module and bound its claims.`,
    alternates: { canonical: `/modules/${module.id}/documentation` },
    robots: { index: false, follow: true },
  };
}

export default async function ModuleDocumentationPage({ params }: PageProps) {
  const { moduleId } = await params;
  await requireUser(`/modules/${moduleId}/documentation`);

  const { data: module, error, missing } = await loadModule(moduleId);
  if (missing) notFound();
  if (!module) {
    return (
      <div className="space-y-5">
        <ErrorState error={new Error(error ?? "")} title="This module could not be loaded" />
        <Button render={<Link href="/modules" />} variant="outline" size="sm">
          <ArrowLeft className="size-3.5" />
          All modules
        </Button>
      </div>
    );
  }

  const moduleDocs = Object.entries(moduleDocumentation.modules).find(
    ([id]) => id === module.id,
  )?.[1] as ModuleDocumentation | undefined;
  const references = moduleDocs?.references ?? [];
  const multiplex = multiplexCapabilityFor(module.id);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${module.name} guide`}
        description="Scientific and technical sources used to define this module, with the scope each source supports."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button render={<Link href={`/modules/${module.id}`} />} variant="outline" size="sm">
              <ArrowLeft className="size-3.5" />
              Back to module
            </Button>
            {multiplex?.genericBuilder ? (
              <Button
                render={<Link href={`/modules/${module.id}/multiplex`} />}
                variant="default"
                size="sm"
              >
                Multiplex design
              </Button>
            ) : null}
          </div>
        }
      />

      <Card className="workbench-card">
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-primary" />
            <CardTitle className="font-serif text-lg font-semibold">
              Source documents used for this module
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {moduleDocs ? (
            <>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The numbered references below are every external source used to define this module
                and its explicitly inherited engine/tool guidance. Links are deduplicated by URL and
                presented in Vancouver bibliography style.
              </p>
              <div className="rounded-lg border bg-surface-wash/35 p-3 text-xs leading-relaxed text-muted-foreground">
                <span className="font-medium text-foreground">Reference list:</span>{" "}
                {references.length} sources, numbered in bibliography order.
              </div>
              {references.length > 40 ? (
                <details className="group rounded-xl border bg-surface-wash/20 p-3">
                  <summary className="cursor-pointer list-none text-sm font-medium text-foreground marker:hidden">
                    <span className="inline-flex items-center gap-2">
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-xs text-primary">
                        {references.length}
                      </span>
                      Open complete reference list
                    </span>
                  </summary>
                  <ReferenceList references={references} />
                </details>
              ) : (
                <ReferenceList references={references} />
              )}
            </>
          ) : (
            <div className="rounded-lg border bg-surface-wash/35 p-3 text-sm leading-relaxed text-muted-foreground">
              <p>
                Documentation for this module is not available in the current build. The module
                remains usable, but its scientific source list should be reviewed before relying on
                the design record.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ReferenceList({
  references,
}: {
  references: { citation: string; kind: "journal" | "web"; url: string }[];
}) {
  return (
    <ol className="mt-4 space-y-3">
      {references.map((reference, index) => (
        <li
          key={reference.url}
          id={`reference-${index + 1}`}
          className="flex items-start gap-3 rounded-lg border bg-surface-wash/35 p-3"
        >
          <span
            className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono text-xs font-semibold text-primary"
            aria-hidden="true"
          >
            {index + 1}
          </span>
          <span className="min-w-0 space-y-1 text-sm leading-relaxed">
            <span className="block text-foreground">
              {reference.citation.endsWith(".") ? reference.citation : `${reference.citation}.`}{" "}
              {reference.kind === "journal" ? (
                <a
                  href={reference.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline decoration-primary/35 underline-offset-2 hover:decoration-primary"
                >
                  {reference.url.startsWith("https://doi.org/") ? "DOI record" : "PubMed record"}
                </a>
              ) : (
                <>
                  <span className="text-muted-foreground">
                    [Internet]. [cited {moduleDocumentation.citation_accessed}]. Available
                    from:{" "}
                  </span>
                  <a
                    href={reference.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline break-all text-primary underline decoration-primary/35 underline-offset-2 hover:decoration-primary"
                  >
                    {reference.url}
                  </a>
                </>
              )}
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}
