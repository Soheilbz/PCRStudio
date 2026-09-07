/**
 * The sidebar's automatic default.
 *
 * These exist because the path they cover cannot be driven from the browser:
 * changing the viewport through the automation's device-metrics override moves
 * the layout without dispatching `resize` or a media-query `change`, so a real
 * window drag is the one thing a browser check here cannot reproduce. A fake
 * media query can.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useSidebarDefault } from "./use-sidebar-default";

/** A media query whose result we control, and can fire changes from. */
function installMatchMedia(initiallyMatches: boolean) {
  const listeners = new Set<() => void>();
  let matches = initiallyMatches;

  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      get matches() {
        return matches;
      },
      media: query,
      onchange: null,
      addEventListener: (_: string, listener: () => void) => listeners.add(listener),
      removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
      dispatchEvent: () => true,
    }),
  });

  return {
    /** Cross the threshold, the way dragging a window edge would. */
    set(next: boolean) {
      matches = next;
      for (const listener of listeners) listener();
    },
    get listenerCount() {
      return listeners.size;
    },
  };
}

let media: ReturnType<typeof installMatchMedia>;

afterEach(() => {
  // Leave the shared jsdom stub as the setup file left it.
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => true,
    }),
  });
});

describe("with no choice stored", () => {
  it("collapses on a narrow window", () => {
    media = installMatchMedia(true);
    const { result } = renderHook(() => useSidebarDefault(true, false));
    expect(result.current.open).toBe(false);
  });

  it("expands on a wide one", () => {
    media = installMatchMedia(false);
    const { result } = renderHook(() => useSidebarDefault(false, false));
    // The server said closed; with no stored choice the width overrules it.
    expect(result.current.open).toBe(true);
  });

  it("follows the window across the threshold, in both directions", () => {
    media = installMatchMedia(false);
    const { result } = renderHook(() => useSidebarDefault(true, false));
    expect(result.current.open).toBe(true);

    act(() => media.set(true));
    expect(result.current.open).toBe(false);

    act(() => media.set(false));
    expect(result.current.open).toBe(true);
  });
});

describe("once someone has chosen", () => {
  it("keeps a stored choice even where the width disagrees", () => {
    media = installMatchMedia(true); // narrow
    const { result } = renderHook(() => useSidebarDefault(true, true));
    // Expanded on a narrow window, because that is what was asked for.
    expect(result.current.open).toBe(true);
  });

  it("stops following the width the moment the sidebar is toggled", () => {
    media = installMatchMedia(false);
    const { result } = renderHook(() => useSidebarDefault(true, false));

    act(() => result.current.onOpenChange(true));
    act(() => media.set(true));

    // Narrow now, and it would have collapsed a moment ago. It does not.
    expect(result.current.open).toBe(true);
  });

  it("does not keep listening after that", () => {
    media = installMatchMedia(false);
    const { result } = renderHook(() => useSidebarDefault(true, false));
    expect(media.listenerCount).toBe(1);

    act(() => result.current.onOpenChange(false));
    expect(media.listenerCount).toBe(0);
  });
});

describe("cleanup", () => {
  it("removes its listener when the shell unmounts", () => {
    media = installMatchMedia(false);
    const { unmount } = renderHook(() => useSidebarDefault(true, false));
    expect(media.listenerCount).toBe(1);

    unmount();
    expect(media.listenerCount).toBe(0);
  });
});
