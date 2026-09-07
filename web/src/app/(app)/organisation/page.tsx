import {
  Activity,
  ArrowRight,
  Blocks,
  Compass,
  Dna,
  FlaskConical,
  HelpCircle,
  Layers,
  Microscope,
  ScanLine,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { loadModules, loadVocabulary } from "@/lib/api/load";
import { requireUser } from "@/lib/auth/current-user";
import type {
  EngineDescription,
  Goal,
  GoalDescription,
  ModifierTerm,
  ModuleManifest,
} from "@/lib/api/types";

export const metadata: Metadata = {
  title: "How the modules are organised",
  description:
    "Why PCRStudio groups primer design modules the way it does: an engine is one search, a modifier is applied to an engine rather than listed beside it, and a goal is what a design has to be checked against — not what the product is used for afterwards.",
  alternates: { canonical: "/organisation" },
  // Part of the workbench, so behind the sign-in gate rather than in an index.
  robots: { index: false, follow: true },
};

const GOAL_ICONS: Record<Goal, LucideIcon> = {
  amplify: FlaskConical,
  quantify: Activity,
  genotype: Dna,
  detect: Microscope,
  sequence: ScanLine,
  assemble: Blocks,
  engineer: Wrench,
};

export default async function OrganisationPage() {
  await requireUser("/organisation");

  const [{ modules, error }, { goals, engines, modifiers }] = await Promise.all([
    loadModules(),
    loadVocabulary(),
  ]);

  return (
    <div className="space-y-8">
      <PageHeader
        title="How the modules are organised"
        description="Every module, what distinguishes it from its neighbours, and why the groups are drawn where they are."
        actions={
          <Button render={<Link href="/modules" />} variant="outline" size="sm">
            All modules
            <ArrowRight className="size-3.5" />
          </Button>
        }
      />

      {error ? <ErrorState error={new Error(error)} title="The catalogue is unavailable" /> : null}

      <TheQuestion />
      <Goals goals={goals} modules={modules} />
      <ThreeLayers />
      <Engines engines={engines} modules={modules} />
      <Modifiers modifiers={modifiers} />
    </div>
  );
}

/**
 * The objection this page exists to answer, formatted as an editorial callout card.
 */
function TheQuestion() {
  return (
    <Card className="workbench-card border-l-4 border-l-primary">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2 text-primary">
          <HelpCircle className="size-4 shrink-0" />
          <CardTitle className="font-serif text-lg font-semibold text-foreground">
            &ldquo;Standard PCR is used for detection too. Why is it not under Detect?&rdquo;
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>
          Because a goal here is not what you do with the tube afterwards. Almost every assay in
          this catalogue can be used to find out whether something is present, so grouping by use
          would put nearly all of them under one heading and separate nothing.
        </p>

        <div className="rounded-lg border bg-surface-warm/30 p-3.5 font-medium text-foreground">
          A goal is{" "}
          <span className="font-semibold text-primary">
            what the design has to be checked against
          </span>{" "}
          — the constraint that changes the thermodynamic search itself.
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Comparison
            name="Standard PCR"
            href="/modules/standard-pcr"
            checked="the template it will run on, and nothing else"
            engine="Flanking pair · Target template only"
          />
          <Comparison
            name="Species-specific PCR"
            href="/modules/species-specific-pcr"
            checked="the template, plus a background of relatives that must not amplify"
            engine="Flanking pair · Checked against non-target background"
          />
        </div>

        <p>
          Both are the same engine — a flanking pair — and both hand you two primers. They are
          separate assays because the second has to reject candidates the first would happily keep.
          So if you are detecting an organism, the module under Detect is the one you want; it is
          not Standard PCR with a different label on it.
        </p>
        <p>
          The same rule puts qPCR under Quantify rather than Amplify. It is also a flanking pair,
          but it is checked for even amplification over a short product, because there the signal is
          the measurement rather than a band at the end.
        </p>
      </CardContent>
    </Card>
  );
}

function Comparison({
  name,
  href,
  checked,
  engine,
}: {
  name: string;
  href: string;
  checked: string;
  engine: string;
}) {
  return (
    <Link
      href={href}
      className="workbench-card group block space-y-1.5 rounded-xl border bg-surface-wash/45 p-3.5 transition-all hover:-translate-y-0.5 hover:border-primary/50"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-foreground group-hover:text-primary group-hover:underline">
          {name}
        </span>
        <ArrowRight className="size-3 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Checked against <span className="font-medium text-foreground">{checked}</span>.
      </p>
      <p className="text-xs text-muted-foreground/80">{engine}</p>
    </Link>
  );
}

/** Every goal with its modules in an interactive card layout. */
function Goals({ goals, modules }: { goals: GoalDescription[]; modules: ModuleManifest[] }) {
  if (goals.length === 0) return null;

  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h2 className="font-serif text-lg tracking-tight text-foreground">The seven goals</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Each is a different thing a design is measured against. An assay belongs to exactly one,
          which is what keeps the catalogue from listing the same search three times under three
          names.
        </p>
      </div>

      <div className="space-y-4">
        {goals.map((goal) => {
          const inGoal = modules.filter((module) => module.goal === goal.id);
          const Icon = GOAL_ICONS[goal.id] ?? FlaskConical;

          return (
            <Card key={goal.id} className="workbench-card">
              <CardHeader className="border-b bg-primary/5 pb-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border bg-surface-wash/45 text-primary">
                      <Icon className="size-4" />
                    </div>
                    <div>
                      <CardTitle className="font-serif text-base font-semibold text-foreground">
                        {goal.label}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground">{goal.rule}</p>
                    </div>
                  </div>
                  <Badge variant="secondary" className="tabular-nums">
                    {goal.count} {goal.count === 1 ? "module" : "modules"}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="pt-4">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {inGoal.map((module) => (
                    <Link
                      key={module.id}
                      href={`/modules/${module.id}`}
                      className="workbench-card group flex flex-col justify-between rounded-xl border bg-surface-wash/45 p-3 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary/5"
                    >
                      <div className="space-y-1">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-xs font-semibold text-foreground group-hover:text-primary">
                            {module.name}
                          </span>
                        </div>
                        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                          {module.guidance || module.summary}
                        </p>
                      </div>
                      <div className="mt-2 flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                        <span>Open module</span>
                        <ArrowRight className="size-3" />
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function ThreeLayers() {
  return (
    <Card className="workbench-card">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-primary" />
          <CardTitle className="font-serif text-lg font-semibold">
            Three layers, and only one is expensive
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
        <p>
          An <strong className="font-medium text-foreground">engine</strong> is one search: a
          pairing of what you start from with what shape the answer has. Eleven of them cover the
          catalogue. Writing one is real work, so the list is closed and adding to it is a decision
          rather than a commit.
        </p>
        <p>
          A <strong className="font-medium text-foreground">modifier</strong> is something applied
          to an engine rather than listed beside it. Multiplexing is not an alternative to standard
          PCR; it is standard PCR run several ways at once. Keeping modifiers separate is what stops
          the catalogue growing by multiplication.
        </p>
        <p>
          An <strong className="font-medium text-foreground">assay</strong> — what this interface
          calls a module — is an engine plus its limits and its wording. Five of them share the
          flanking-pair engine. That is the point of the split: they differ in what they reject, not
          in what they compute.
        </p>
        <p>
          Which modifiers each engine accepts is declared rather than assumed, and checked when the
          service starts. An assay asking for something its engine refuses stops the process instead
          of failing under somebody mid-run.
        </p>
      </CardContent>
    </Card>
  );
}

/** The compatibility matrix of engines. */
function Engines({
  engines,
  modules,
}: {
  engines: EngineDescription[];
  modules: ModuleManifest[];
}) {
  if (engines.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="space-y-0.5">
        <h2 className="font-serif text-lg tracking-tight text-foreground">The eleven engines</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          A rule that decides which assays can exist is worth being able to read. The count is how
          many assays share each one.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {engines.map((engine) => {
          const using = modules.filter((module) => module.engine === engine.id);
          return (
            <div
              key={engine.id}
              className="workbench-card space-y-2 rounded-xl border bg-surface-wash/45 p-3.5"
            >
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="text-xs font-semibold text-foreground">{engine.name}</h3>
                <Badge variant="outline" className="text-xs tabular-nums">
                  {using.length} {using.length === 1 ? "assay" : "assays"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Input: <code className="font-mono text-foreground">{engine.input}</code>
              </p>
              <div className="flex flex-wrap gap-1 border-t pt-2">
                {using.map((m) => (
                  <span
                    key={m.id}
                    className="rounded bg-surface-warm/35 px-1.5 py-0.5 text-xs text-muted-foreground"
                  >
                    {m.name}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Modifiers({ modifiers }: { modifiers: ModifierTerm[] }) {
  if (modifiers.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="space-y-0.5">
        <h2 className="font-serif text-lg tracking-tight text-foreground">The five modifiers</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Every module page lists the ones it carries, and every engine declares which it will take.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {modifiers.map((modifier) => (
          <div
            key={modifier.id}
            className="workbench-card flex items-center gap-1.5 rounded-xl border bg-surface-wash/45 px-3 py-1.5 text-xs font-medium text-foreground"
          >
            <Compass className="size-3.5 text-primary" />
            <span>{modifier.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
