import { FlaskConical, FolderOpen, LogIn } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { loadModules } from "@/lib/api/load";
import { UndoDelete } from "@/components/project/undo-delete";
import { OnboardingCard } from "@/components/project/onboarding-card";
import { ProjectsBrowser } from "@/components/project/projects-browser";
import { loadProjectLimits, loadProjects } from "@/lib/projects/load";
import { requireUser } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "Your projects",
  description: "Every design you have started, and which system it belongs to.",
  alternates: { canonical: "/projects" },
  robots: { index: false, follow: false },
};

/**
 * Everything you have started, in one place, searchable and filterable.
 */
export default async function ProjectsPage({
  searchParams,
}: {
  /** `?undone=` carries the project a delete just removed, so it can be undone. */
  searchParams: Promise<{ undone?: string }>;
}) {
  await requireUser("/projects");

  const [{ projects, signedIn, error: projectsError }, { modules }, limits, { undone }] =
    await Promise.all([loadProjects(), loadModules(), loadProjectLimits(), searchParams]);

  const remaining = limits.maxProjectsPerUser - projects.length;
  const nearlyFull = !projectsError && Number.isFinite(remaining) && remaining <= 10;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Your projects"
        description={
          signedIn
            ? "Everything you have started, whichever design system it belongs to."
            : "Projects are saved to your account, so this list needs you signed in."
        }
        actions={
          <Button render={<Link href="/modules" />} size="sm">
            <FlaskConical />
            New design
          </Button>
        }
      />

      {/* Above the list, where somebody looking for the project they meant to keep will be looking */}
      {signedIn && undone ? <UndoDelete projectId={undone} /> : null}

      {signedIn && nearlyFull ? (
        <p className="rounded-xl border border-warning/40 bg-warning/5 px-4 py-3 text-sm leading-relaxed">
          {remaining > 0
            ? `${projects.length} of ${limits.maxProjectsPerUser} projects. ${remaining} more can be started.`
            : `This account is at its limit of ${limits.maxProjectsPerUser} projects. Delete one you have finished with to start another.`}
        </p>
      ) : null}

      {projectsError ? (
        <ErrorState error={new Error(projectsError)} title="Your projects could not be loaded" />
      ) : !signedIn ? (
        <EmptyState
          icon={LogIn}
          title="Sign in to see your projects"
          description="A project keeps a sequence, the settings around it, and every run you saved against it."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button render={<Link href="/sign-in" />} size="sm">
                Sign in
              </Button>
              <Button render={<Link href="/modules" />} variant="outline" size="sm">
                Browse the modules
              </Button>
            </div>
          }
        />
      ) : projects.length === 0 ? (
        <>
          {/* Above the empty state, because the empty state is where somebody
              staring at nothing is already looking. Dismissed once, it never
              comes back — see the note in the component. */}
          <OnboardingCard />
          <EmptyState
            icon={FolderOpen}
            title="No projects yet"
            description="Pick the design system that matches your assay, and starting a project is the first thing it asks for."
            action={
              <Button render={<Link href="/modules" />} size="sm">
                <FlaskConical />
                Browse {modules.length} design systems
              </Button>
            }
          />
        </>
      ) : (
        <ProjectsBrowser projects={projects} modules={modules} />
      )}
    </div>
  );
}
