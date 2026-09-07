"use client";

/**
 * The projects somebody has for this module, and a way to start another.
 *
 * One component for every module rather than a page of its own, because a
 * project is not a thing anybody wants for its own sake — it is where this
 * assay's work is kept, and the moment somebody wants one is the moment they
 * are already reading about the assay.
 *
 * It appears on modules that cannot run yet as well. A planned module still
 * has a target to paste and conditions to settle, and having somewhere to put
 * them is the difference between waiting for a feature and being ready for it.
 * What changes is that the card says so, rather than letting somebody find out
 * at the end.
 */

import {
  ArrowRight,
  CalendarPlus,
  Clock,
  FolderOpen,
  Hammer,
  Loader2,
  LogIn,
  Play,
  Plus,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Project } from "@/lib/api/types";
import { createProjectAction, type ProjectState } from "@/lib/projects/actions";
// The same component the projects index uses. Each page having its own
// formatting is how one of them ends up showing the server's locale.
import { LocalTime } from "@/components/local-time";

const EMPTY: ProjectState = {};

export function ModuleProjects({
  moduleId,
  moduleName,
  projects,
  signedIn,
  runnable,
}: {
  moduleId: string;
  moduleName: string;
  /** Only this module's projects. Another assay's work belongs on its own page. */
  projects: Project[];
  signedIn: boolean;
  /** Whether the engine behind this module computes yet. */
  runnable: boolean;
}) {
  const [state, submit, pending] = useActionState(createProjectAction, EMPTY);

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
          <FolderOpen className="size-4" />
          {projects.length > 0
            ? `${projects.length} project${projects.length === 1 ? "" : "s"}`
            : "Projects"}
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          A project keeps one {moduleName} design together: the target, selected chemistry, settings
          and every run you keep. You can return to the work without rebuilding it from memory.
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {!runnable ? (
          <p className="flex gap-2 rounded-lg border border-warning/40 bg-warning/5 p-3 text-xs leading-relaxed text-muted-foreground">
            <Hammer className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
            <span>
              This module has no implementation yet, so a project here can hold your target and your
              settings but cannot be run. Asking the core to run it returns a refusal rather than a
              result, which is deliberate — nothing here can be mistaken for a designed primer set.
            </span>
          </p>
        ) : null}

        {projects.length > 0 ? (
          <ul className="grid gap-2.5 sm:grid-cols-2">
            {projects.map((project) => (
              <li key={project.id}>
                <Link
                  href={`/projects/${project.id}`}
                  className="workbench-card group flex h-full flex-col gap-2 rounded-xl border bg-surface-wash/55 p-3.5 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-warm/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="min-w-0 truncate font-serif text-sm font-semibold">
                      {project.name}
                    </span>
                    <ArrowRight className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                  </span>

                  {project.notes ? (
                    <span className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                      {project.notes}
                    </span>
                  ) : null}

                  {/* What somebody wants from a card at a glance: whether it
                      has been run, how far in it is, and when they last had
                      their hands on it. */}
                  <span className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1 tabular-nums">
                      <Play className="size-3" aria-hidden="true" />
                      {project.runCount} run{project.runCount === 1 ? "" : "s"}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="size-3" aria-hidden="true" />
                      <LocalTime iso={project.updatedAt} relative />
                    </span>
                    <span className="flex items-center gap-1">
                      <CalendarPlus className="size-3" aria-hidden="true" />
                      started <LocalTime iso={project.createdAt} />
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : signedIn ? (
          <p className="text-sm leading-relaxed text-muted-foreground">
            Nothing here yet. Name one below and it opens straight into the workspace.
          </p>
        ) : null}

        {signedIn ? (
          <form action={submit} className="flex flex-wrap items-end gap-3">
            <input type="hidden" name="moduleId" value={moduleId} />
            <div className="min-w-0 flex-1 basis-full space-y-1.5 sm:min-w-[14rem] sm:basis-auto">
              <Label htmlFor="projectName" className="text-xs font-medium">
                {projects.length ? "Start another" : "Start a project"}
              </Label>
              <Input
                id="projectName"
                name="name"
                required
                maxLength={120}
                placeholder={`${moduleName} for …`}
              />
            </div>
            <Button type="submit" size="sm" disabled={pending}>
              {pending ? <Loader2 className="animate-spin" /> : <Plus />}
              Start
            </Button>
          </form>
        ) : (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-primary/20 bg-surface-lilac/25 p-3">
            <p className="min-w-0 flex-1 basis-full text-xs leading-relaxed text-muted-foreground sm:min-w-[16rem] sm:basis-auto">
              Designing happens in a project, and a project belongs to an account. Free, no
              verification email — an address and a password, so your work can be yours.
            </p>
            <div className="flex gap-2">
              <Button render={<Link href={`/sign-up?next=/modules/${moduleId}`} />} size="sm">
                <UserPlus />
                Create an account
              </Button>
              <Button
                render={<Link href={`/sign-in?next=/modules/${moduleId}`} />}
                variant="outline"
                size="sm"
              >
                <LogIn />
                Sign in
              </Button>
            </div>
          </div>
        )}

        {state.error ? (
          <p role="alert" className="text-sm text-destructive">
            {state.error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
