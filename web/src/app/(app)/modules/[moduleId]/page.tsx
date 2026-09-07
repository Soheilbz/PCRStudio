import { ArrowLeft, ArrowRight, BookOpen, Compass, Info, Layers } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ModuleProjects } from "@/components/project/module-projects";
import { MODULE_BINDINGS } from "@/lib/contracts/module-bindings.generated";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { loadModule, loadVocabulary } from "@/lib/api/load";
import { requireUser } from "@/lib/auth/current-user";
import { loadProjects } from "@/lib/projects/load";
import { multiplexCapabilityFor } from "@/lib/multiplex-capabilities";
import { jsonLd, site, siteUrl } from "@/lib/site";

interface PageProps {
  params: Promise<{ moduleId: string }>;
}

// The module catalogue is a generated, closed contract. Rejecting an id that
// is not in that contract at the route boundary makes an unknown module a
// genuine HTTP 404 even when the server-rendered response is streamed.
export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(MODULE_BINDINGS).map((moduleId) => ({ moduleId }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { moduleId } = await params;
  const { data: module, missing } = await loadModule(moduleId);

  if (missing) notFound();

  if (!module) {
    return { title: "Module unavailable", robots: { index: false, follow: true } };
  }

  const title = `${module.name} primer design`;
  return {
    title,
    description: module.summary,
    alternates: { canonical: `/modules/${module.id}` },
    // Part of the workbench: behind the sign-in gate rather than in an index.
    robots: { index: false, follow: true },
    openGraph: {
      type: "article",
      title: `${title} — ${site.name}`,
      description: module.summary,
      url: `${siteUrl}/modules/${module.id}`,
    },
  };
}

export default async function ModulePage({ params }: PageProps) {
  const { moduleId } = await params;
  await requireUser(`/modules/${moduleId}`);

  const [
    { data: module, error, missing },
    { engines },
    { projects, signedIn, error: projectsError },
  ] = await Promise.all([loadModule(moduleId), loadVocabulary(), loadProjects()]);

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

  const multiplex = multiplexCapabilityFor(module.id);

  return (
    <div className="space-y-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd({
            "@context": "https://schema.org",
            "@type": "TechArticle",
            headline: `${module.name} primer design`,
            description: module.summary,
            url: `${siteUrl}/modules/${module.id}`,
            isPartOf: { "@type": "WebSite", name: site.name, url: siteUrl },
          }),
        }}
      />

      <PageHeader
        title={module.name}
        description={module.summary}
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              render={<Link href={`/modules/${module.id}/documentation`} />}
              variant="outline"
              size="sm"
            >
              <BookOpen className="size-3.5" />
              Module guide
            </Button>
            {multiplex?.genericBuilder ? (
              <Button
                render={<Link href={`/modules/${module.id}/multiplex`} />}
                variant="default"
                size="sm"
                className="shadow-sm"
              >
                <Layers className="size-3.5" />
                Multiplex design
                <ArrowRight className="size-3.5" />
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="workbench-card">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2 text-primary">
              <Compass className="size-4" />
              <CardTitle className="font-serif text-lg font-semibold text-foreground">
                When this assay fits
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-muted-foreground">{module.guidance}</p>
          </CardContent>
        </Card>

        <Card className="workbench-card bg-surface-warm/35">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Info className="size-4" />
              <CardTitle className="font-serif text-lg font-semibold text-foreground">
                How this design is checked
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-muted-foreground">{module.checks}</p>
          </CardContent>
        </Card>
      </div>

      {projectsError ? (
        <ErrorState
          error={new Error(projectsError)}
          title="Projects for this module could not be loaded"
        />
      ) : (
        <ModuleProjects
          moduleId={module.id}
          moduleName={module.name}
          projects={projects.filter((project) => project.moduleId === module.id)}
          signedIn={signedIn}
          runnable={
            module.status !== "planned" &&
            Boolean(engines.find((entry) => entry.id === module.engine)?.implemented)
          }
        />
      )}
    </div>
  );
}
