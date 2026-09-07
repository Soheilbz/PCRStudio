"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
const onClient = () => true;
const onServer = () => false;

/**
 * False during the server render and the first client render, true afterwards.
 *
 * Anything read from `localStorage` or the OS — the chosen theme, most obviously
 * — is unknowable on the server, so a component has to render the neutral case
 * until it is mounted. Doing it through `useSyncExternalStore` rather than
 * `setState` in an effect avoids the extra render pass that pattern costs.
 */
export function useMounted(): boolean {
  return useSyncExternalStore(subscribe, onClient, onServer);
}
