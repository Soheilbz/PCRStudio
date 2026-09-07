import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MultiplexForm } from "@/components/design/multiplex-form";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { loadModule } from "@/lib/api/load";
import { requireUser } from "@/lib/auth/current-user";
import { site, siteUrl } from "@/lib/site";

interface PageProps {
  params: Promise<{ moduleId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { moduleId } = await params;
  const { data: module, missing } = await loadModule(moduleId);

  // A 404 here rather than in the body, for the same reason as the module page:
  // metadata resolves before anything is streamed, so the status line is still
  // ours to set.
  if (missing) notFound();
  if (!module) {
    return { title: "Module unavailable", robots: { index: false, follow: true } };
  }

  // An assay that cannot be multiplexed has no page here, and saying so with a
  // 404 is more honest than rendering a form the server would refuse.
  if (!module.modifiers.includes("multiplex")) notFound();

  const title = `${module.name} in one tube`;
  return {
    title,
    description: `Design several ${module.name} targets that share a reaction.`,
    alternates: { canonical: `/modules/${module.id}/multiplex` },
    // Part of the workbench: behind the sign-in gate rather than in an index.
    robots: { index: false, follow: true },
    openGraph: {
      type: "article",
      title: `${title} — ${site.name}`,
      url: `${siteUrl}/modules/${module.id}/multiplex`,
    },
  };
}

export default async function MultiplexPage({ params }: PageProps) {
  const { moduleId } = await params;
  await requireUser(`/modules/${moduleId}/multiplex`);

  const { data: module, error, missing } = await loadModule(moduleId);

  if (missing) notFound();
  if (!module) {
    return (
      <div className="space-y-5">
        <ErrorState error={new Error(error ?? "")} title="This module could not be loaded" />
        <Button render={<Link href="/modules" />} variant="outline" size="sm">
          <ArrowLeft />
          All modules
        </Button>
      </div>
    );
  }
  if (!module.modifiers.includes("multiplex")) notFound();

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${module.name} in one tube`}
        description="Several targets amplified in one reaction, chosen for how the whole set behaves rather than how each pair scores alone."
      />

      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-lg font-semibold">
            What this does differently
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm leading-relaxed text-muted-foreground">
          <p>
            Every oligo in the tube meets every other one, so picking the top-ranked pair for each
            target separately can produce a set whose members ruin each other. Choosing between sets
            properly is not available: twenty targets with a hundred candidates each is a hundred to
            the twentieth power of possible sets, and the problem was shown to be NP-complete in
            1997. So the targets with the least choice are placed first, then the result is improved
            by swapping — which is what the published tools do.
          </p>
          <p>
            Nothing here passes or fails a set. There is no published line between an acceptable
            multiplex and an unacceptable one, so what comes back is the interactions, the products
            a reader could not tell apart, and a number to compare one set against another.
          </p>
        </CardContent>
      </Card>

      <MultiplexForm moduleId={module.id} />

      <Button render={<Link href={`/modules/${module.id}`} />} variant="outline" size="sm">
        <ArrowLeft />
        {module.name}
      </Button>
    </div>
  );
}
