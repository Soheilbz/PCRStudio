export interface ThreeWayMerge<T extends Record<string, unknown>> {
  merged: T;
  conflicts: string[];
}

function same(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (left === undefined || right === undefined) return false;
  return JSON.stringify(left) === JSON.stringify(right);
}

/**
 * Merge independent field edits without silently choosing a winner.
 *
 * A key changed only locally keeps the local value; a key changed only on the
 * server keeps the server value. A key changed to the same value on both sides
 * is harmless. Only divergent edits of the same key are conflicts.
 */
export function threeWayMerge<T extends Record<string, unknown>>(
  base: T,
  local: T,
  remote: T,
): ThreeWayMerge<T> {
  const merged: Record<string, unknown> = {};
  const conflicts: string[] = [];
  const keys = new Set([...Object.keys(base), ...Object.keys(local), ...Object.keys(remote)]);

  for (const key of [...keys].sort()) {
    const before = base[key];
    const localValue = local[key];
    const remoteValue = remote[key];
    const localChanged = !same(localValue, before);
    const remoteChanged = !same(remoteValue, before);

    if (localChanged && remoteChanged && !same(localValue, remoteValue)) {
      conflicts.push(key);
      // Preserve the remote authoritative value in the merge candidate; the
      // caller must not persist while conflicts is non-empty.
      if (remoteValue !== undefined) merged[key] = remoteValue;
    } else if (localChanged) {
      if (localValue !== undefined) merged[key] = localValue;
    } else if (remoteValue !== undefined) {
      merged[key] = remoteValue;
    }
  }

  return { merged: merged as T, conflicts };
}
