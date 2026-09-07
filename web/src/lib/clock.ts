/**
 * The current time, as something React is allowed to read during render.
 *
 * Calling `Date.now()` in a component body is impure: two renders of the same
 * component produce two different strings, and React is free to render whenever
 * it likes. So the clock lives outside React and is read through
 * `useSyncExternalStore`, which is the supported way to read a changing
 * external value.
 *
 * Making it tick is not extra: a relative timestamp that is computed once says
 * "just now" for the rest of the session. Thirty seconds is fine because the
 * shortest thing anybody reads here is "1 minute ago" — a faster tick would
 * re-render for no visible change, and a slower one would leave a stale minute
 * on screen.
 */

const TICK_MS = 30_000;

let now = Date.now();
let timer: ReturnType<typeof setInterval> | undefined;
const listeners = new Set<() => void>();

function tick() {
  now = Date.now();
  for (const listener of listeners) listener();
}

export function subscribeToClock(listener: () => void): () => void {
  listeners.add(listener);
  // Only one interval however many timestamps are on screen, and none at all
  // when there are none — a page of a hundred runs should not hold a hundred
  // timers, and a page with no timestamps should hold none.
  timer ??= setInterval(tick, TICK_MS);

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer !== undefined) {
      clearInterval(timer);
      timer = undefined;
    }
  };
}

/** The last tick. Stable between ticks, which is what React requires of it. */
export function readClock(): number {
  return now;
}

/**
 * What the server sees: nothing.
 *
 * Returning a real timestamp here would make the server render a relative
 * string the client then disagrees with by however long the request took.
 * `null` is the signal to render the locale-free absolute form instead.
 */
export function serverClock(): null {
  return null;
}
