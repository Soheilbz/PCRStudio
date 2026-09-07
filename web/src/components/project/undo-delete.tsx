"use client";

import { Undo2 } from "lucide-react";
import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { restoreProjectAction, type ProjectState } from "@/lib/projects/actions";

/**
 * The offer to take a deletion back.
 *
 * It appears on the list rather than where the deletion happened, because that
 * page no longer exists — which is precisely why an undo is worth having here.
 * Deleting a project used to remove a sequence, a draft and every saved run
 * outright, on the second of two clicks; the second click is where the mistake
 * is made, so a confirmation step protected nobody.
 *
 * Not a toast. A toast is gone in five seconds, and somebody who deleted the
 * wrong project usually realises after looking at the list and not finding the
 * one they wanted. This stays until the page is left.
 */
export function UndoDelete({ projectId }: { projectId: string }) {
  const [state, formAction, pending] = useActionState(restoreProjectAction, {} as ProjectState);

  return (
    <div
      // Announced, because for a screen reader the deletion is otherwise a page
      // that changed with no explanation of what happened or what can be done.
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/30 bg-warning/5 px-4 py-3"
    >
      <div className="space-y-1">
        <p className="text-sm">
          Project deleted. It and its runs can be brought back for thirty days.
        </p>
        {state.error ? (
          <p role="alert" className="text-sm text-destructive">
            {state.error}
          </p>
        ) : null}
      </div>
      <form action={formAction}>
        <input type="hidden" name="projectId" value={projectId} />
        <Button type="submit" variant="outline" size="sm" disabled={pending}>
          <Undo2 />
          {pending ? "Bringing back…" : "Undo"}
        </Button>
      </form>
    </div>
  );
}
