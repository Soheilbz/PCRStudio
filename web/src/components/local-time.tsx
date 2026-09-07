"use client";

import { useSyncExternalStore } from "react";

import { readClock, serverClock, subscribeToClock } from "@/lib/clock";
import { exactly, isoDay, onDay, when } from "@/lib/dates";

/**
 * A timestamp the reader can actually read.
 *
 * Rendered two ways on purpose. The server knows neither the reader's locale
 * nor their clock, so it emits the ISO day — unambiguous in every locale, and
 * identical in both passes, which is what keeps hydration quiet. In the browser
 * both are known, so the local form replaces it and, for a relative time, keeps
 * up as the clock moves.
 *
 * `<time dateTime>` in both cases, so the machine-readable instant survives
 * whichever form is on screen.
 */
export function LocalTime({ iso, relative = false }: { iso: string; relative?: boolean }) {
  const now = useSyncExternalStore(subscribeToClock, readClock, serverClock);

  if (now === null) {
    return <time dateTime={iso}>{isoDay(iso)}</time>;
  }

  return (
    <time dateTime={iso} title={exactly(iso)}>
      {relative ? when(iso, now) : onDay(iso)}
    </time>
  );
}
