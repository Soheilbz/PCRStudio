"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { toast } from "sonner";

import type { Project } from "@/lib/api/types";
import { MAX_ACTION_BYTES } from "@/lib/contracts/limits.generated";
import type { RawDraftValues } from "@/lib/projects/draft";
import { saveDraftAction } from "@/lib/projects/actions";
import { threeWayMerge } from "@/lib/projects/three-way-merge";

type Draft = RawDraftValues;
export type DraftSaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * Serialize autosaves, enforce optimistic concurrency, and preserve a local
 * draft on any conflict. UI navigation calls `save()` before moving steps.
 */
export function useDraftAutosave({
  project,
  draft,
  setDraft,
  blank,
}: {
  project: Project;
  draft: Draft;
  setDraft: Dispatch<SetStateAction<Draft>>;
  blank: Draft;
}) {
  const [saved, setSaved] = useState<DraftSaveStatus>("idle");
  const draftRef = useRef(draft);
  const lastSaved = useRef("");
  const serverUpdatedAt = useRef(project.updatedAt);
  const serverBaseDraft = useRef<Draft>({ ...blank, ...(project.settings as Draft) });
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const blockedByConflict = useRef(false);

  useEffect(() => {
    // A save may be in flight while somebody edits another control. Keep the
    // completion handler from applying that older response over the newer
    // local draft.
    draftRef.current = draft;
  }, [draft]);

  const save = useCallback(async () => {
    if (blockedByConflict.current) return;
    const encoded = JSON.stringify(draft);
    const queued = saveQueue.current.then(async () => {
      if (encoded === lastSaved.current) return;
      setSaved("saving");
      const encodedBytes = new TextEncoder().encode(encoded).byteLength;
      if (encodedBytes > MAX_ACTION_BYTES) {
        setSaved("error");
        toast.error("Draft is too large to send", {
          description: `This draft is ${encodedBytes.toLocaleString()} bytes; the canonical Server Action transport ceiling is ${MAX_ACTION_BYTES.toLocaleString()} bytes. Large sequence fields are externalized after they reach the server, so reduce other draft content or split the work into projects.`,
        });
        return;
      }

      let answer: Awaited<ReturnType<typeof saveDraftAction>>;
      try {
        answer = await saveDraftAction(project.id, draft, serverUpdatedAt.current);
      } catch {
        setSaved("error");
        toast.error("Draft not saved", {
          description:
            "The draft could not reach the server. Your local draft is intact; check the connection or reduce the payload and try again.",
        });
        return;
      }

      if (!answer.saved && answer.conflict && answer.remoteUpdatedAt && answer.remoteSettings) {
        const remote = { ...blank, ...(answer.remoteSettings as Draft) };
        const merge = threeWayMerge(serverBaseDraft.current, draft, remote);
        if (merge.conflicts.length > 0) {
          answer = { ...answer, conflictFields: merge.conflicts };
        } else {
          try {
            answer = await saveDraftAction(project.id, merge.merged, answer.remoteUpdatedAt);
          } catch {
            answer = {
              saved: false,
              failure: {
                kind: "transport",
                detail:
                  "The merged draft could not reach the server. Your local draft is intact; try again.",
              },
            };
          }
        }
      }

      const snapshotStillCurrent = JSON.stringify(draftRef.current) === encoded;
      const reconciled = answer.settings as Draft | undefined;
      if (answer.saved && reconciled) {
        const normalized = { ...blank, ...reconciled };
        lastSaved.current = JSON.stringify(normalized);
        serverBaseDraft.current = normalized;
        if (snapshotStillCurrent) {
          if (JSON.stringify(normalized) !== encoded) setDraft(normalized);
        } else {
          // The response belongs to an older snapshot. The newer local draft
          // remains authoritative and the autosave effect will enqueue it;
          // never replace it with a stale server response.
          setSaved("idle");
        }
      } else {
        lastSaved.current = answer.saved && snapshotStillCurrent ? encoded : "";
        if (answer.saved) serverBaseDraft.current = { ...draft };
        if (answer.saved && !snapshotStillCurrent) setSaved("idle");
      }
      if (answer.updatedAt) serverUpdatedAt.current = answer.updatedAt;
      if (answer.conflict) blockedByConflict.current = true;
      setSaved(answer.saved ? (snapshotStillCurrent ? "saved" : "idle") : "error");
      if (!answer.saved) {
        toast.error(answer.conflict ? "Newer project version detected" : "Draft not saved", {
          description: answer.conflict
            ? answer.conflictFields?.length
              ? `Both copies changed: ${answer.conflictFields.join(", ")}. Your local draft is intact; reconcile these fields before saving.`
              : "This project changed again during reconciliation. Your local draft is intact; retry after reviewing the newer server version."
            : (answer.failure?.detail ??
              "The application did not save the draft. The draft here is still intact — try again."),
        });
      }
    });
    saveQueue.current = queued.catch(() => undefined);
    await queued;
  }, [blank, draft, project.id, setDraft]);

  useEffect(() => {
    lastSaved.current = JSON.stringify({ ...blank, ...(project.settings as Draft) });
    serverUpdatedAt.current = project.updatedAt;
    serverBaseDraft.current = { ...blank, ...(project.settings as Draft) };
    blockedByConflict.current = false;
  }, [blank, project.settings, project.updatedAt]);

  useEffect(() => {
    const encoded = JSON.stringify(draft);
    if (encoded === lastSaved.current) return;
    const timer = window.setTimeout(() => void save(), 1500);
    return () => window.clearTimeout(timer);
  }, [draft, save]);

  useEffect(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (JSON.stringify(draft) === lastSaved.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const flushWhenHidden = () => {
      if (document.visibilityState === "hidden" && JSON.stringify(draft) !== lastSaved.current) {
        void save();
      }
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    document.addEventListener("visibilitychange", flushWhenHidden);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      document.removeEventListener("visibilitychange", flushWhenHidden);
    };
  }, [draft, save]);

  return { saved, save };
}
