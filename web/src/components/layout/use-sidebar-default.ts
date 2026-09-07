"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Below this width, expanding the sidebar costs content.
 *
 * It is not a round number, it is a sum: the 896px content cap, plus the 256px
 * rail, plus the 48px page gutters. Above it the expanded sidebar is free —
 * content is already at its cap and the rail takes only what was margin. Below
 * it every pixel the rail takes comes out of the page.
 *
 * Picking it this way is what keeps the content column from ever getting
 * narrower as the window gets wider, which is what happened with the sidebar
 * simply following the 768px sheet breakpoint: at 768 the column dropped to
 * about 500px, narrower than the same page on a 640px phone.
 */
const RAIL_TOO_WIDE_BELOW = 896 + 256 + 48;

export interface SidebarState {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * The sidebar's open state, decided by the viewport until someone decides for
 * themselves.
 *
 * Two rules, in this order:
 *
 * 1. **A stored choice always wins.** Expand the sidebar on a small laptop and
 *    it stays expanded, at that width and every other, forever.
 * 2. **With no choice stored, the width decides** — and keeps deciding, so
 *    dragging the window across the threshold does the right thing.
 *
 * The distinction is why this is controlled state rather than a call to
 * `setOpen`: `SidebarProvider` writes the cookie inside `setOpen`, so using it
 * for the automatic decision would record that decision as a preference and
 * silently stop rule 2 from ever applying again.
 *
 * @param serverOpen What the server rendered, from the cookie.
 * @param chosen Whether that cookie existed at all.
 */
export function useSidebarDefault(serverOpen: boolean, chosen: boolean): SidebarState {
  const [open, setOpen] = useState(serverOpen);
  const [decided, setDecided] = useState(chosen);

  useEffect(() => {
    if (decided) return;

    const query = window.matchMedia(`(max-width: ${RAIL_TOO_WIDE_BELOW - 1}px)`);
    const apply = () => setOpen(!query.matches);

    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, [decided]);

  const onOpenChange = useCallback((next: boolean) => {
    // Only a person reaches this: the automatic path sets state directly. By
    // the time it runs, SidebarProvider has written the cookie.
    setDecided(true);
    setOpen(next);
  }, []);

  return { open, onOpenChange };
}
