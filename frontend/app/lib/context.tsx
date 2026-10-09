import { createContext, useContext } from 'react';
import type { Me, Workspace } from './api';
export const WorkspaceContext = createContext<{
  me: Me;
  workspace: Workspace;
  refresh: () => Promise<void>;
  selectWorkspace: (id: string, preservePath?: boolean) => Promise<void>;
  url: (path: string) => string;
} | null>(null);
export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('Workspace is unavailable');
  return context;
}
export const AccountContext = createContext<{
  me: Me;
  refresh: () => Promise<void>;
} | null>(null);
export function useAccount() {
  const context = useContext(AccountContext);
  if (!context) throw new Error('Account is unavailable');
  return context;
}
