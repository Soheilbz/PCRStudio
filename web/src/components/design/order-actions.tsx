"use client";

import { Check, Copy, Download, FileText, Printer } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { copyText } from "@/lib/clipboard";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  type Conditions,
  type OrderLine,
  downloadFasta,
  downloadIdtOrderSheet,
  downloadOrderSheet,
  toTabbed,
} from "@/lib/order-sheet";

/**
 * Take the oligos away — as text, as a standard sheet, or in vendor-specific formats.
 */
export function OrderActions({
  lines,
  targetName,
  kind,
  conditions,
  amplicon,
  showPrint = true,
}: {
  lines: OrderLine[];
  targetName?: string;
  /** What these oligos are, for naming the file when the target has no name. */
  kind?: string;
  conditions?: Conditions;
  amplicon?: { name: string; sequence: string };
  showPrint?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  if (lines.length === 0) return null;

  const count = `${lines.length} oligo${lines.length === 1 ? "" : "s"}`;

  return (
    <div className="flex shrink-0 items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label={`Copy ${count} as names and sequences`}
        onClick={() => {
          void copyText(toTabbed(lines))
            .then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            })
            .catch(() => {
              toast.error("Could not reach the clipboard", {
                description: "Your browser refused the request. Download the spreadsheet instead.",
              });
            });
        }}
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {copied ? "Copied" : "Copy"}
      </Button>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label={`Download ${count} as a spreadsheet`}
        onClick={() => downloadOrderSheet(lines, targetName || kind, conditions)}
      >
        <Download className="size-3.5" />
        Download
      </Button>

      {/* Export Options Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={`Export options for ${count}`}
            >
              <Download className="size-3.5" />
              Export…
            </Button>
          }
        />
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuLabel className="text-xs text-muted-foreground">
            Order Formats
          </DropdownMenuLabel>
          <DropdownMenuItem
            onClick={() => downloadOrderSheet(lines, targetName || kind, conditions)}
            className="cursor-pointer text-xs"
          >
            <Download className="size-3.5" />
            Standard CSV (.csv)
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => downloadIdtOrderSheet(lines, targetName || kind)}
            className="cursor-pointer text-xs"
          >
            <Download className="size-3.5" />
            IDT Bulk Order (.csv)
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-xs text-muted-foreground">
            Sequence Files
          </DropdownMenuLabel>
          <DropdownMenuItem
            onClick={() => downloadFasta(lines, targetName || kind, amplicon)}
            className="cursor-pointer text-xs"
          >
            <FileText className="size-3.5" />
            FASTA File (.fasta)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {showPrint ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label="Print design and order sheet"
          onClick={() => window.print()}
          className="hidden sm:inline-flex"
        >
          <Printer className="size-3.5" />
          Print
        </Button>
      ) : null}
    </div>
  );
}
