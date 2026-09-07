/**
 * Which modifier key this keyboard actually has.
 *
 * The shortcut has always accepted either — `event.metaKey || event.ctrlKey` —
 * but the hint beside the search box always read `⌘K`, which is the wrong key
 * on Windows and on Linux. A shortcut hint that names a key the reader does not
 * have is worse than no hint: it does not just fail to help, it tells them the
 * feature is not for them.
 *
 * The server cannot know, so it says nothing and the browser fills it in. Same
 * reasoning as `LocalTime`, and the same shape: a snapshot that differs between
 * the two passes has to be read through `useSyncExternalStore`, not set from an
 * effect.
 */

/** Nothing to subscribe to: the keyboard does not change under a running page. */
export const NEVER_CHANGES = () => () => {};

/** `⌘` on a Mac, `Ctrl` everywhere else. */
export function readModifierKey(): string {
  // `userAgentData.platform` where it exists, and the user-agent string where
  // it does not — Safari and Firefox still have no `userAgentData`, and Safari
  // is exactly where the answer is most likely to be `⌘`.
  const platform =
    (navigator as { userAgentData?: { platform?: string } }).userAgentData?.platform ??
    navigator.userAgent;

  return /mac|iphone|ipad|ipod/i.test(platform) ? "\u2318" : "Ctrl";
}

/** What the server renders: nothing, because it has no way to know. */
export function noModifierKey(): null {
  return null;
}
