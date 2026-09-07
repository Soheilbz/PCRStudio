import { ArrowRight, Boxes } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ModuleBrowser } from "@/components/modules/module-browser";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { loadModules, loadVocabulary } from "@/lib/api/load";
import { requireUser } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "Modules",
  description:
    "Every PCR design system in PCRStudio, grouped by what you are trying to do: amplify a region, quantify, genotype a variant, detect an organism, sequence a genome, clone or assemble, engineer a change.",
  alternates: { canonical: "/modules" },
  // Part of the workbench: behind the sign-in gate rather than in an index.
  robots: { index: false, follow: true },
};

export default async function ModulesPage() {
  await requireUser("/modules");

  const [{ modules }, { goals }] = await Promise.all([loadModules(), loadVocabulary()]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Modules"
        description="One module per design system, grouped by what its design has to be checked against. A module is registered here before it is implemented, so its address and its place in the interface are fixed from the start."
        actions={
          <Button render={<Link href="/organisation" />} variant="outline" size="sm">
            Why these groups
            <ArrowRight />
          </Button>
        }
      />

      {modules.length === 0 ? (
        <EmptyState
          icon={Boxes}
          title="No modules are registered"
          description="Either this build shipped without any design systems, or the core is not answering."
        />
      ) : (
        <ModuleBrowser modules={modules} goals={goals} />
      )}
    </div>
  );
}
