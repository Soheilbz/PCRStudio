"use client";

/**
 * A project's name and notes, editable in place.
 */

import { Check, Copy, Loader2, Pencil, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Project } from "@/lib/api/types";
import {
  deleteProjectAction,
  duplicateProjectAction,
  renameProjectAction,
  type ProjectState,
} from "@/lib/projects/actions";

const EMPTY: ProjectState = {};

export function ProjectHeader({ project, assayName }: { project: Project; assayName: string }) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [state, submit, pending] = useActionState(
    async (previous: ProjectState, form: FormData) => {
      const next = await renameProjectAction(previous, form);
      if (!next.error) setEditing(false);
      return next;
    },
    EMPTY,
  );
  const [duplicateState, duplicateSubmit, duplicatePending] = useActionState(
    duplicateProjectAction,
    EMPTY,
  );
  const [deleteState, deleteSubmit, deletePending] = useActionState(deleteProjectAction, EMPTY);

  const shown = state.project ?? project;

  if (editing) {
    return (
      <form
        action={submit}
        className="workbench-card space-y-3 rounded-xl border bg-surface-wash/45 p-4"
      >
        <input type="hidden" name="projectId" value={project.id} />
        <div className="space-y-1.5">
          <label htmlFor="project-name" className="text-sm font-medium">
            Project name
          </label>
          <Input id="project-name" name="name" defaultValue={shown.name} required maxLength={120} />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="project-notes" className="text-sm font-medium">
            Notes
          </label>
          <Textarea
            id="project-notes"
            name="notes"
            rows={3}
            defaultValue={shown.notes}
            placeholder="What this project is for, what you have tried, anything you want to find again."
          />
        </div>
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={pending}>
            {pending ? <Loader2 className="animate-spin" /> : <Check />}
            Save
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
            <X />
            Cancel
          </Button>
        </div>
        {state.error ? (
          <p role="alert" className="text-sm text-destructive">
            {state.error}
          </p>
        ) : null}
      </form>
    );
  }

  return (
    <header className="workbench-hero relative overflow-hidden rounded-2xl border border-border/70 p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="font-serif text-2xl leading-tight tracking-tight text-foreground sm:text-3xl">
            {shown.name}
          </h1>
          <p className="text-sm text-muted-foreground">
            <Link href={`/modules/${project.moduleId}`} className="underline hover:text-foreground">
              {assayName}
            </Link>{" "}
            — where this project and its siblings live
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="size-3.5" />
            Rename
          </Button>

          <form action={duplicateSubmit}>
            <input type="hidden" name="projectId" value={project.id} />
            <Button type="submit" variant="outline" size="sm" disabled={duplicatePending}>
              <Copy className="size-3.5" />
              {duplicatePending ? "Duplicating…" : "Duplicate"}
            </Button>
          </form>

          {confirming ? (
            <div className="flex items-center gap-1">
              <form action={deleteSubmit}>
                <input type="hidden" name="projectId" value={project.id} />
                <input type="hidden" name="moduleId" value={project.moduleId} />
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={deletePending}
                  className="text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="size-3.5" />
                  Confirm Delete
                </Button>
              </form>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={deletePending}
                onClick={() => setConfirming(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
              <Trash2 className="size-3.5" />
              Delete
            </Button>
          )}
        </div>
      </div>
      {deleteState.error ? (
        <p role="alert" className="text-sm text-destructive">
          {deleteState.error}
        </p>
      ) : null}
      {duplicateState.error ? (
        <p role="alert" className="text-sm text-destructive">
          {duplicateState.error}
        </p>
      ) : null}
      {shown.notes ? (
        <p className="max-w-3xl border-t border-border/50 pt-3 text-sm leading-relaxed text-muted-foreground">
          {shown.notes}
        </p>
      ) : null}
    </header>
  );
}
