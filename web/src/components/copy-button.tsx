"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { copyText } from "@/lib/clipboard";

/**
 * Copies a short value and says so.
 *
 * Identifiers get retyped into scripts and pasted into issues; making that one
 * click removes a class of transcription error.
 */
export function CopyButton({
  value,
  label,
  className,
}: {
  value: string;
  label: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await copyText(value);
      setCopied(true);
      toast.success(`${label} copied`, { description: value });
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
      variant="ghost"
      size="icon"
      onClick={copy}
      aria-label={`Copy ${label.toLowerCase()}`}
      className={cn("size-7", className)}
    >
      {copied ? <Check className="size-3.5 text-chart-2" /> : <Copy className="size-3.5" />}
    </Button>
  );
}
