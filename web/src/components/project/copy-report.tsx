"use client";

import { Check, FileText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { RunResult } from "@/lib/api/types";
import { reportMarkdown } from "@/lib/projects/report-markdown";
import { copyText } from "@/lib/clipboard";

/**
 * The visible summary of one result, on the clipboard as markdown.
 *
 * A notebook entry, a lab book, an issue: wherever a design goes next, it goes
 * there as text. Everything worth retyping is in the report — the oligos, what
 * they amplify and how warm — so the click saves the retyping rather than
 * pretending to archive the run.
 */
export function CopyReportButton({
  label,
  createdAt,
  moduleName,
  result,
  className,
}: {
  label: string;
  createdAt: string;
  moduleName: string | null;
  result: RunResult;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    const markdown = reportMarkdown({ label, createdAt, moduleName, result });
    try {
      await copyText(markdown);
      setCopied(true);
      toast.success("Result copied as markdown");
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard access is refused on insecure origins and in some browsers.
      // Say so rather than showing a success that did not happen.
      toast.error("Could not reach the clipboard", {
        description: "Your browser refused the request. Select the text and copy it manually.",
      });
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={copy}
      aria-label="Copy this result as markdown"
      className={className}
    >
      {copied ? <Check className="size-3.5" /> : <FileText className="size-3.5" />}
      {copied ? "Copied" : "Copy as markdown"}
    </Button>
  );
}
