import {
  ArrowRight,
  Boxes,
  CheckCircle2,
  Dna,
  FlaskConical,
  FolderOpen,
  ShieldCheck,
  UserRound,
  Workflow,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Nested } from "@/components/heading-level";
import { LocalTime } from "@/components/local-time";
import { loadModules, loadVocabulary } from "@/lib/api/load";
import { loadProjects } from "@/lib/projects/load";
import { requireUser } from "@/lib/auth/current-user";
import type { GoalDescription, ModuleManifest, Project } from "@/lib/api/types";
import { jsonLd, site, siteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: `${site.name} — ${site.tagline}`,
  description: site.description,
  alternates: { canonical: "/" },
  robots: { index: false, follow: true },
};

export default async function DashboardPage() {
  // The workbench starts here, and the workbench belongs to an account. The
  // proxy turns strangers away before a render; this line is the one that
  // checks the session is real.
  const user = await requireUser("/");

  const [{ modules }, { goals }, { projects, error: projectsError }] = await Promise.all([
    loadModules(),
    loadVocabulary(),
    loadProjects(),
  ]);

  const recent = [...projects].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 3);
  const totalRuns = projects.reduce((sum, project) => sum + project.runCount, 0);
  const stableCount = modules.filter((module) => module.status === "stable").length;
  const experimentalCount = modules.filter((module) => module.status === "experimental").length;

  return (
    <div className="space-y-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd({
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: site.name,
            alternateName: `${site.name} — ${site.tagline}`,
            description: site.description,
            url: siteUrl,
          }),
        }}
      />

      <Hero moduleCount={modules.length} displayName={user.displayName} />

      {/* Quick actions: the three things a returning visitor does first, one
          click each instead of a trip through the sidebar or the palette. */}
      <section aria-label="Quick actions" className="grid gap-3 sm:grid-cols-3">
        <QuickAction
          href="/modules"
          icon={FlaskConical}
          title="Start a design"
          description="Choose the assay that matches your lab question."
        />
        <QuickAction
          href="/projects"
          icon={FolderOpen}
          title="Open projects"
          description={
            projects.length > 0
              ? `${projects.length} saved ${projects.length === 1 ? "project" : "projects"}.`
              : "Your saved designs will appear here."
          }
        />
        <QuickAction
          href="/account"
          icon={UserRound}
          title="Account"
          description="Manage sign-in, recovery and bench preferences."
        />
      </section>

      {projectsError ? (
        <ErrorState error={new Error(projectsError)} title="Your projects could not be loaded" />
      ) : null}

      {!projectsError && recent.length > 0 ? (
        <section className="space-y-2.5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="font-serif text-lg font-semibold">Pick up where you left off</h2>
            <Button
              render={<Link href="/projects" />}
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
            >
              All projects
              <ArrowRight className="size-3.5" />
            </Button>
          </div>
          <Nested>
            <ul className="grid gap-3 sm:grid-cols-3">
              {recent.map((project) => (
                <li key={project.id}>
                  <RecentProject
                    project={project}
                    systemName={
                      modules.find((one) => one.id === project.moduleId)?.name ?? project.moduleId
                    }
                  />
                </li>
              ))}
            </ul>
          </Nested>
        </section>
      ) : !projectsError ? (
        <EmptyState
          icon={FolderOpen}
          title="Start with an assay"
          description="A project keeps the target, settings, runs and primer pairs together so you can review or continue the work later."
          action={
            <Button render={<Link href="/modules" />}>
              <FlaskConical className="size-4" />
              Start your first design
            </Button>
          }
        />
      ) : null}

      <section className="space-y-2.5">
        <h2 className="font-serif text-lg font-semibold">Your workspace at a glance</h2>
        <Nested>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Saved projects"
              hint="Available in this account"
              value={projects.length}
            />
            <StatCard label="Design runs" hint="Across your projects" value={totalRuns} />
            <StatCard
              label="Validated assays"
              hint={`${stableCount} of ${modules.length} have bench validation`}
              value={stableCount}
            />
            <StatCard
              label="Needs bench validation"
              hint={`${experimentalCount} of ${modules.length} assays`}
              value={experimentalCount}
            />
          </div>
        </Nested>
      </section>

      <section className="space-y-2.5">
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-serif text-lg font-semibold">Choose an assay</h2>
          {modules.length > 0 ? (
            <Button
              render={<Link href="/modules" />}
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
            >
              See all
              <ArrowRight className="size-3.5" />
            </Button>
          ) : null}
        </div>
        {modules.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No assays are available"
            description="The assay catalogue could not be loaded. Try again or check the design service connection."
          />
        ) : (
          <Nested>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {modules.slice(0, 6).map((module) => (
                <ModuleCard key={module.id} module={module} goals={goals} />
              ))}
            </div>
          </Nested>
        )}
      </section>
    </div>
  );
}

/**
 * Modern, high-impact Hero banner with balanced typography and clear action hierarchy.
 * Greets the signed-in person by name: the dashboard is somebody's bench, not
 * a landing page they happen to be past.
 */
function Hero({ moduleCount, displayName }: { moduleCount: number; displayName: string }) {
  const firstName = displayName.split(/\s+/)[0] || displayName;

  return (
    <section className="workbench-hero relative overflow-hidden rounded-2xl border border-border/80 p-6 shadow-sm transition-all sm:p-8 lg:p-10">
      {/* Decorative subtle background accents */}
      <div
        className="pointer-events-none absolute -top-24 -right-24 size-96 rounded-full bg-primary/5 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -bottom-24 -left-24 size-96 rounded-full bg-brand/5 blur-3xl"
        aria-hidden="true"
      />

      <div className="relative space-y-4">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <Dna className="size-3.5" />
          <span>Welcome back, {firstName}</span>
        </div>

        <div className="space-y-2">
          <h1 className="font-serif text-3xl leading-tight tracking-tight text-foreground sm:text-4xl">
            Start with the question your experiment needs to answer
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
            Choose an assay, provide the sequence and reaction context it needs, and review the
            resulting primers with their checks and evidence in one place. Each design keeps its
            assumptions visible so you can decide what is ready for ordering and what still needs
            bench validation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 pt-1">
          <Button render={<Link href="/modules" />} size="default" className="shadow-xs">
            Browse {moduleCount > 0 ? moduleCount : ""} assays
            <ArrowRight className="size-4" />
          </Button>

          <Button render={<Link href="/about" />} variant="outline" size="default">
            How it works
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t pt-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5 font-medium text-foreground/80">
            <Workflow className="size-3.5 text-primary" />
            Guidance matched to the assay
          </span>
          <span className="flex items-center gap-1.5 font-medium text-foreground/80">
            <ShieldCheck className="size-3.5 text-primary" />
            Assumptions and checks stay visible
          </span>
          <span className="flex items-center gap-1.5 font-medium text-foreground/80">
            <CheckCircle2 className="size-3.5 text-primary" />
            Reports and oligos ready to review
          </span>
        </div>
      </div>
    </section>
  );
}

/** One card-sized shortcut on the dashboard, whole-card clickable. */
function QuickAction({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: typeof FlaskConical;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="workbench-card group flex items-start gap-3 rounded-xl border bg-surface-wash/45 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-warm/40"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="size-4.5" />
      </span>
      <span className="min-w-0 space-y-0.5">
        <span className="flex items-center gap-1 font-serif text-base font-semibold">
          {title}
          <ArrowRight className="size-3.5 -translate-x-1 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
        </span>
        <span className="block truncate text-xs text-muted-foreground">{description}</span>
      </span>
    </Link>
  );
}

function RecentProject({ project, systemName }: { project: Project; systemName: string }) {
  return (
    <Card className="workbench-card h-full gap-1.5 py-3 transition-all hover:-translate-y-0.5 hover:border-primary/40">
      <CardHeader className="px-4">
        <CardTitle className="truncate font-serif text-base font-semibold">
          <Link href={`/projects/${project.id}`} className="hover:underline">
            {project.name}
          </Link>
        </CardTitle>
        <CardDescription className="truncate text-xs">{systemName}</CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <p className="text-xs text-muted-foreground">
          {project.runCount} {project.runCount === 1 ? "run" : "runs"} &middot;{" "}
          <LocalTime iso={project.updatedAt} relative />
        </p>
      </CardContent>
    </Card>
  );
}

function StatCard({ label, hint, value }: { label: string; hint: string; value: number }) {
  return (
    <Card className="workbench-card gap-0 py-3.5">
      <CardHeader className="px-4 pb-1">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
        <p className="text-2xl font-bold tracking-tight tabular-nums">{value}</p>
      </CardHeader>
      <CardContent className="px-4">
        <p className="text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
}

function ModuleCard({ module, goals }: { module: ModuleManifest; goals: GoalDescription[] }) {
  const goal = goals.find((entry) => entry.id === module.goal);

  return (
    <Card className="workbench-card gap-2.5 transition-all hover:-translate-y-0.5 hover:border-primary/40">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <CardTitle className="truncate font-serif text-lg font-semibold">
              {module.name}
            </CardTitle>
            <CardDescription className="text-xs">{goal?.label ?? module.goal}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm leading-relaxed text-muted-foreground">{module.summary}</p>
        <Button render={<Link href={`/modules/${module.id}`} />} variant="outline" size="sm">
          <FlaskConical className="size-3.5" />
          Open
        </Button>
      </CardContent>
    </Card>
  );
}
