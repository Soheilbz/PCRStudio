"use client";

import {
  Activity,
  Blocks,
  Boxes,
  ChevronDown,
  Dna,
  FlaskConical,
  FolderOpen,
  LayoutDashboard,
  Microscope,
  ScanLine,
  TriangleAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { NavUser } from "@/components/layout/nav-user";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import type { Goal, GoalDescription, ModuleManifest, User } from "@/lib/api/types";

/**
 * The only thing about a goal that lives here. Its wording and its order come
 * from the core, which is where the vocabulary is defined.
 */
const GOAL_ICONS: Record<Goal, LucideIcon> = {
  amplify: FlaskConical,
  quantify: Activity,
  genotype: Dna,
  detect: Microscope,
  sequence: ScanLine,
  assemble: Blocks,
  engineer: Wrench,
};

// Named after the vocabulary it stores, not after "the sidebar". When modules
// were regrouped from categories to goals the old cookie kept naming
// categories, and since none of those ids matched a goal the folded set came
// back empty -- every group open, on a build whose default is closed. A stored
// preference is only meaningful in the vocabulary it was written in, so the
// name has to change with it.
const GROUP_COOKIE = "sidebar_goals";
const ONE_YEAR = 60 * 60 * 24 * 365;

/**
 * Records which groups are folded, so the sidebar comes back the way it was
 * left. A cookie rather than local storage because the server renders the
 * sidebar, and reading it there is what keeps every group from flashing open
 * on load and then folding shut.
 */
function rememberClosedGroups(closed: Set<string>) {
  // Ids are lowercase and hyphenated, so a dot is a separator they can never
  // contain. Secure alongside https, because a preference is not a secret and
  // a plain-http development build should still be able to keep one.
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${GROUP_COOKIE}=${[...closed].join(".")}; path=/; max-age=${ONE_YEAR}; samesite=lax${secure}`;
}

export function AppSidebar({
  modules,
  goals,
  closedGroups,
  user,
}: {
  modules: ModuleManifest[];
  goals: GoalDescription[];
  closedGroups: string[];
  user: User | null;
}) {
  const pathname = usePathname();
  const { state, isMobile } = useSidebar();
  const [closed, setClosed] = useState<Set<string>>(() => new Set(closedGroups));

  // With the sidebar reduced to icons there are no group headings left to
  // click, so a folded group would hide its modules with no way back.
  // A collapsed desktop rail is a flyout navigation, but mobile uses the
  // same `state` cookie only to remember the desktop preference. Reusing that
  // state on a mobile sheet renders right-facing flyouts inside a narrow
  // viewport, which can overflow the sheet and makes a group tap look like a
  // broken/crashing menu. Mobile must always use the readable, inline groups.
  const iconMode = state === "collapsed" && !isMobile;

  const groups = goals
    .map((goal) => ({
      goal,
      modules: modules.filter((module) => module.goal === goal.id),
    }))
    .filter((group) => group.modules.length > 0);

  const setGroupOpen = (goal: Goal, open: boolean) => {
    if (iconMode) return;
    setClosed((previous) => {
      const next = new Set(previous);
      if (open) next.delete(goal);
      else next.add(goal);
      rememberClosedGroups(next);
      return next;
    });
  };

  return (
    <Sidebar collapsible="icon" className="border-sidebar-border/80">
      <SidebarHeader className="border-b border-sidebar-border/80 bg-sidebar/90">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-xl bg-brand text-brand-foreground shadow-sm">
                <Dna className="size-4" />
              </div>
              <div className="grid flex-1 text-left leading-tight">
                <span className="truncate font-serif font-semibold tracking-tight">PCRStudio</span>
                <span className="truncate text-xs text-muted-foreground">
                  Primer design workbench
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* A landmark with a name. There are two navigations on every page —
          this and the breadcrumb — and a screen reader's landmark list showing
          "navigation, navigation" is a list that helps nobody choose. */}
      <SidebarContent role="navigation" aria-label="Design systems">
        <SidebarGroup className="border-b border-sidebar-border/80 pb-3">
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/" />}
                  isActive={pathname === "/"}
                  tooltip="Dashboard"
                >
                  <LayoutDashboard />
                  <span>Dashboard</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/modules" />}
                  isActive={pathname === "/modules"}
                  tooltip="All modules"
                >
                  <Boxes />
                  <span>All modules</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                {/* Shown signed out as well as signed in. The page explains
                    that projects live on an account and offers the way in;
                    hiding it would mean the only hint that saved work exists
                    is one you get after you already have some. */}
                <SidebarMenuButton
                  render={<Link href="/projects" />}
                  isActive={pathname.startsWith("/projects")}
                  tooltip="Your projects"
                >
                  <FolderOpen />
                  <span>Your projects</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {modules.length === 0 ? (
          <SidebarGroup>
            <SidebarGroupLabel>Design systems</SidebarGroupLabel>
            <SidebarGroupContent>
              <p className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
                <TriangleAlert className="size-3.5 shrink-0 text-destructive" />
                Module list unavailable
              </p>
            </SidebarGroupContent>
          </SidebarGroup>
        ) : null}

        {/*
         * Collapsed, the rail shows one button per goal rather than one per
         * module.
         *
         * The icon means the goal — it always did — so repeating it on every
         * module inside that goal produced twenty-five buttons drawn with ten
         * icons: five flasks, four helices, four microscopes, none of them
         * telling you which module you were pointing at. Tooltips existed, but
         * a rail you have to hover twenty-five times to read is not navigation.
         *
         * Nine meaningful buttons, each opening its own list, is the same
         * information with the ambiguity removed.
         */}
        {iconMode
          ? groups.map(({ goal, modules: grouped }) => {
              const Icon = GOAL_ICONS[goal.id];
              const here = grouped.some((module) => pathname === `/modules/${module.id}`);

              return (
                <SidebarGroup key={goal.id} className="py-0.5">
                  <SidebarGroupContent>
                    <SidebarMenu>
                      <SidebarMenuItem>
                        <DropdownMenu>
                          {/* The children belong to the trigger, not inside
                              `render` — and no `tooltip`, because that prop
                              wraps the same element in a second Base UI
                              trigger and the two fight over the pointer. The
                              flyout is the label. */}
                          <DropdownMenuTrigger
                            render={
                              <SidebarMenuButton
                                isActive={here}
                                className="data-[popup-open]:bg-sidebar-accent data-[popup-open]:text-sidebar-accent-foreground"
                              />
                            }
                          >
                            <Icon />
                            <span className="truncate">{goal.label}</span>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent side="right" align="start" className="min-w-56">
                            {/* The group is required, not decoration: a label
                                outside one throws MenuGroupContext is missing,
                                which takes the whole menu down rather than
                                just the label. */}
                            <DropdownMenuGroup>
                              <DropdownMenuLabel>{goal.label}</DropdownMenuLabel>
                              {grouped.map((module) => (
                                <DropdownMenuItem
                                  key={module.id}
                                  render={<Link href={`/modules/${module.id}`} />}
                                >
                                  <span className="truncate">{module.name}</span>
                                </DropdownMenuItem>
                              ))}
                            </DropdownMenuGroup>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </SidebarMenuItem>
                    </SidebarMenu>
                  </SidebarGroupContent>
                </SidebarGroup>
              );
            })
          : groups.map(({ goal, modules: grouped }) => {
              const Icon = GOAL_ICONS[goal.id];
              const open = !closed.has(goal.id);

              return (
                <Collapsible
                  key={goal.id}
                  open={open}
                  onOpenChange={(next) => setGroupOpen(goal.id, next)}
                  className="group/group"
                >
                  <SidebarGroup className="mb-1 py-1 last:mb-0">
                    <SidebarGroupLabel
                      className="min-w-0 gap-3"
                      render={
                        <CollapsibleTrigger className="w-full min-w-0 rounded-lg hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none" />
                      }
                    >
                      {/* The icon and chevron make the group boundary and its
                           open/closed state legible without adding numeric
                           badges to the navigation. */}
                      <Icon
                        className="size-3.5 text-sidebar-accent-foreground"
                        aria-hidden="true"
                      />
                      {goal.label}
                      <ChevronDown className="ml-auto size-3.5 transition-transform duration-200 group-data-[closed]/group:-rotate-90" />
                    </SidebarGroupLabel>

                    <CollapsibleContent className="overflow-hidden">
                      <SidebarGroupContent className="relative ml-3 w-auto min-w-0 pl-2 before:absolute before:inset-y-1 before:left-0.5 before:w-px before:bg-sidebar-border/80">
                        <SidebarMenu>
                          {grouped.map((module) => (
                            <SidebarMenuItem
                              key={module.id}
                              className="before:absolute before:top-1/2 before:left-[-0.5rem] before:h-px before:w-2 before:bg-sidebar-border/80 has-data-[active=true]:before:bg-primary/60"
                            >
                              <SidebarMenuButton
                                render={<Link href={`/modules/${module.id}`} />}
                                isActive={pathname === `/modules/${module.id}`}
                                tooltip={module.name}
                              >
                                <Icon />
                                <span className="truncate">{module.name}</span>
                              </SidebarMenuButton>
                            </SidebarMenuItem>
                          ))}
                        </SidebarMenu>
                      </SidebarGroupContent>
                    </CollapsibleContent>
                  </SidebarGroup>
                </Collapsible>
              );
            })}
      </SidebarContent>

      {/* Settings and About live in the account menu rather than as rows of
          their own, so each destination has exactly one place in the interface. */}
      <SidebarFooter className="border-t border-sidebar-border">
        <NavUser user={user} />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
