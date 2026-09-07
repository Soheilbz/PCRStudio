"use client";

import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { CommandPaletteProvider } from "@/components/command/command-palette";
import { AppFooter } from "@/components/layout/app-footer";
import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { useSidebarDefault } from "@/components/layout/use-sidebar-default";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { GoalDescription, ModuleManifest, User } from "@/lib/api/types";

/**
 * The frame every page renders inside.
 *
 * It is a client component because the sidebar and the palette are stateful,
 * but it receives the module list from the server rather than fetching it, so
 * nothing here waits on the network after hydration.
 */
export function AppShell({
  modules,
  goals,
  coreError,
  sidebarOpen,
  sidebarChosen,
  closedGroups,
  user,
  children,
}: {
  modules: ModuleManifest[];
  goals: GoalDescription[];
  coreError: string | null;
  sidebarOpen: boolean;
  sidebarChosen: boolean;
  closedGroups: string[];
  user: User | null;
  children: ReactNode;
}) {
  const sidebar = useSidebarDefault(sidebarOpen, sidebarChosen);

  return (
    <CommandPaletteProvider modules={modules} goals={goals}>
      <TooltipProvider delay={0}>
        <SidebarProvider open={sidebar.open} onOpenChange={sidebar.onOpenChange}>
          <a
            href="#content"
            className="sr-only bg-primary text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:px-3 focus:py-2 focus:text-sm focus:ring-2 focus:ring-ring focus:outline-none"
          >
            Skip to content
          </a>

          <AppSidebar modules={modules} goals={goals} closedGroups={closedGroups} user={user} />
          <SidebarInset className="workbench-shell min-w-0">
            <AppHeader modules={modules} />
            <div id="content" tabIndex={-1} className="min-w-0 flex-1 focus:outline-none">
              <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
                {coreError ? (
                  <Alert variant="destructive" className="mb-5">
                    <TriangleAlert />
                    <AlertTitle className="font-serif text-base font-semibold">
                      The design core is not reachable
                    </AlertTitle>
                    <AlertDescription>{coreError}</AlertDescription>
                  </Alert>
                ) : null}
                {children}
              </div>
            </div>
            <AppFooter signedIn={Boolean(user)} />
          </SidebarInset>
        </SidebarProvider>
      </TooltipProvider>
    </CommandPaletteProvider>
  );
}
