"use client";

import { X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";

/**
 * Ends a comparison, in one press.
 *
 * The comparison lives in the address bar, so clearing it is editing the
 * address rather than forgetting some state — which is also why this is a
 * replace and not a push: undoing a whole comparison is what Back is for
 * already, and pushing would make Back walk through every pair somebody
 * looked at on the way.
 */
export function ClearComparison() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const clear = () => {
    const next = new URLSearchParams(params.toString());
    next.delete("compare");
    // Whatever run was open stays open: clearing the comparison should not
    // also un-open the result above it.
    const search = next.toString();
    router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false });
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={clear}
      aria-label="Clear comparison"
      className="h-7 px-2 text-muted-foreground"
    >
      <X className="size-3.5" />
      Clear comparison
    </Button>
  );
}
