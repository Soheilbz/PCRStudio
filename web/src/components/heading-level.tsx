"use client";

import { createContext, useContext, type ReactNode } from "react";

/**
 * How deep the current region sits, so a heading can be the right rank.
 *
 * Card titles used to be `<div>`s — ninety-eight of them. To a screen reader
 * that means the page has no structure below its `<h1>`: no way to list the
 * sections, no way to jump between them, no way to tell "What to order" from
 * the paragraph next to it. Everything is read in order or not at all.
 *
 * The rank could have been typed into all ninety-eight, and would have been
 * wrong within a month — the same card appears under a page heading on one
 * screen and inside a titled section on another, and the correct number is
 * different in each. So it is derived from where the card actually is, and the
 * only thing anybody has to remember is to mark a region as a region.
 *
 * Capped at six, because `<h7>` is not a tag.
 */
const Depth = createContext(1);

/**
 * A region whose own heading has already been written.
 *
 * Wrap the part of the tree *below* that heading, so what is inside ranks one
 * level under it.
 */
export function Nested({ children }: { children: ReactNode }) {
  const depth = useContext(Depth);
  return <Depth.Provider value={Math.min(depth + 1, 5)}>{children}</Depth.Provider>;
}

/** The tag a heading should use here: `h2` at the top level, deeper inside. */
export function useHeadingTag(): "h2" | "h3" | "h4" | "h5" | "h6" {
  const depth = useContext(Depth);
  return (["h2", "h3", "h4", "h5", "h6"] as const)[Math.min(depth, 5) - 1]!;
}
