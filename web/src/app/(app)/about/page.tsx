import { ArrowRight, ExternalLink } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { loadAppInfo } from "@/lib/api/load";
import { METHODS } from "@/lib/methods";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "About",
  description:
    "PCRStudio is a proprietary primer design workbench. The scientific work lives in a separate Rust core, so the same logic can support the web interface and approved deployments.",
  alternates: { canonical: "/about" },
};

export default async function AboutPage() {
  const { data: info, error } = await loadAppInfo();

  return (
    <div className="space-y-6">
      <PageHeader
        title="About"
        description="PCRStudio is a workbench for designing PCR primers. The scientific work lives in a separate core, so the same logic can support this interface and approved deployments."
        actions={
          <Button
            render={<a href={site.repository} target="_blank" rel="noreferrer noopener" />}
            variant="outline"
            size="sm"
          >
            <ExternalLink />
            Repository
          </Button>
        }
      />

      {error ? <ErrorState error={new Error(error)} title="Build details are unavailable" /> : null}

      {/*
       * Two columns on a wide screen, one on anything narrower.
       *
       * Stacked in a single column these three cards ran the full width of the
       * content area — around a hundred characters a line on a large monitor,
       * which is half again what long-form text is set at — and left the right
       * half of the screen empty while doing it. The citations are the reason
       * anybody opens this page, so they take the wider column; what the build
       * is and how it is arranged are reference, and sit beside them.
       *
       * `minmax(0, …)` on both tracks rather than a bare fraction: a grid
       * column's default minimum is its content, so one long unbroken string —
       * a DOI, a version, a sequence — would otherwise push the track wider
       * than its share and take the page's horizontal scrollbar with it.
       *
       * `items-start` so a short card keeps its own height instead of
       * stretching to match the tall one beside it.
       *
       * The split waits for `xl` rather than `lg`, measured rather than
       * guessed: the sidebar takes 256px, so at 1137px the second column came
       * out 296px wide — about forty characters a line, which is narrower than
       * prose should ever be set and worse than the full-width version it
       * replaced. At 1280 it is around 350 and at 1900 around 600.
       */}
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card className="workbench-card">
          <CardHeader>
            <CardTitle className="font-serif text-lg font-semibold">
              How the numbers are computed
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-relaxed text-muted-foreground">
              A melting temperature is the output of a model, not a measurement, and two respectable
              models disagree on the same oligo by more than a protocol has room for. So the model
              is fixed, named on every result, and cited here — a figure you cannot trace is a
              figure you have to take on faith.
            </p>

            <ul className="space-y-4">
              {METHODS.map((method) => (
                <li key={method.paper.doi} className="space-y-1.5 border-l-2 pl-3.5">
                  <p className="text-sm leading-relaxed">{method.what}</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {method.software ? (
                      <>
                        <a
                          href={method.software.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="underline hover:text-foreground"
                        >
                          {method.software.name}
                        </a>
                        {" — "}
                      </>
                    ) : null}
                    {method.paper.authors} ({method.paper.year}). {method.paper.title}.{" "}
                    <span className="italic">{method.paper.journal}</span> {method.paper.where}.{" "}
                    <a
                      href={`https://doi.org/${method.paper.doi}`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="underline hover:text-foreground"
                    >
                      doi:{method.paper.doi}
                    </a>
                  </p>
                </li>
              ))}
            </ul>

            <p className="text-xs leading-relaxed text-muted-foreground">
              Specificity is checked against a background only when one is given. When none is,
              every result says so rather than leaving the omission to be inferred.
            </p>
          </CardContent>
        </Card>

        <div className="grid gap-6">
          <Card className="workbench-card">
            <CardHeader>
              <CardTitle className="font-serif text-lg font-semibold">This build</CardTitle>
            </CardHeader>
            <CardContent>
              {info ? (
                <dl className="grid gap-x-8 gap-y-3">
                  <Field label="Service" value={info.name} />
                  <Field label="Version" value={info.version} mono />
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">
                  The core did not report which version is running.
                </p>
              )}
            </CardContent>
          </Card>

          <Card className="workbench-card">
            <CardHeader>
              <CardTitle className="font-serif text-lg font-semibold">
                How it is put together
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-relaxed">
              <p className="text-muted-foreground">
                Each PCR design system is a module registered with the core. The interface never
                hard-codes a list of them: it asks the core what it has and renders the answer,
                which is why adding a design system does not mean editing the navigation.
              </p>
              <p className="text-muted-foreground">
                A module is registered before it is implemented, and until it has an engine the core
                refuses to run it rather than returning an empty result — so no screen here can be
                mistaken for a designed primer set. Every module in this build does have one; what
                none of them has yet is a bench validation, which is what their status says.
              </p>
              <p className="text-muted-foreground">
                Modules are grouped by what their design has to be checked against, which is not the
                same as what the product is used for afterwards. That distinction decides where
                every module sits.
              </p>
              <Button render={<Link href="/organisation" />} variant="outline" size="sm">
                How the modules are organised
                <ArrowRight />
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={mono ? "font-mono text-sm break-all" : "text-sm"}>{value}</dd>
    </div>
  );
}
