"use client";

import {
  Activity,
  Blocks,
  Boxes,
  Compass,
  Dna,
  FlaskConical,
  Info,
  FolderOpen,
  LayoutDashboard,
  Microscope,
  ScanLine,
  Search,
  UserRound,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { NEVER_CHANGES, noModifierKey, readModifierKey } from "@/lib/platform";
import { cn } from "@/lib/utils";
import type { Goal, GoalDescription, ModuleManifest } from "@/lib/api/types";

const GOAL_ICONS: Record<Goal, LucideIcon> = {
  amplify: FlaskConical,
  quantify: Activity,
  genotype: Dna,
  detect: Microscope,
  sequence: ScanLine,
  assemble: Blocks,
  engineer: Wrench,
};

const PAGES: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/modules", label: "All modules", icon: Boxes },
  { href: "/try", label: "Try it without an account", icon: FlaskConical },
  { href: "/projects", label: "Your projects", icon: FolderOpen },
  { href: "/organisation", label: "How the modules are organised", icon: Compass },
  { href: "/account", label: "Account", icon: UserRound },
  { href: "/about", label: "About", icon: Info },
];

/**
 * How well an entry matches what was typed.
 */
function score(value: string, search: string): number {
  const needle = search.trim().toLowerCase();
  if (!needle) return 1;

  const name = value.toLowerCase();
  if (name === needle) return 1;
  if (name.startsWith(needle)) return 0.9;
  if (name.includes(needle)) return 0.8;

  return 0;
}

interface CommandPaletteValue {
  open: () => void;
}

const CommandPaletteContext = createContext<CommandPaletteValue | null>(null);

export function useCommandPalette(): CommandPaletteValue {
  const value = useContext(CommandPaletteContext);
  if (!value) throw new Error("useCommandPalette must be used inside <CommandPaletteProvider>.");
  return value;
}

/**
 * Keyboard-first navigation over everything the core published.
 */
export function CommandPaletteProvider({
  modules,
  goals,
  children,
}: {
  modules: ModuleManifest[];
  goals: GoalDescription[];
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const openPalette = useCallback(() => setOpen(true), []);

  const select = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const byGoal = useMemo(() => {
    const map = new Map<string, ModuleManifest[]>();
    for (const goal of goals) map.set(goal.id, []);
    // Named `entry` rather than `module`: binding that identifier shadows the
    // CommonJS `module` object, which Next refuses to compile.
    for (const entry of modules) {
      const list = map.get(entry.goal) ?? [];
      list.push(entry);
      map.set(entry.goal, list);
    }
    return map;
  }, [modules, goals]);

  return (
    <CommandPaletteContext value={{ open: openPalette }}>
      {children}
      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title="Command palette"
        description="Search every module, page and assay in PCRStudio."
      >
        <Command
          filter={(value, search) => score(value, search)}
          className="rounded-none! border-0 bg-transparent p-0 shadow-none"
        >
          <CommandInput placeholder="Search modules, assays, pages…" />
          <CommandList>
            <CommandEmpty>No matching modules or pages found.</CommandEmpty>
            <CommandGroup heading="Pages">
              {PAGES.map((page) => {
                const Icon = page.icon;
                return (
                  <CommandItem
                    key={page.href}
                    value={page.label}
                    onSelect={() => select(page.href)}
                  >
                    <Icon className="size-4" />
                    <span>{page.label}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
            <CommandSeparator />
            {goals.map((goal) => {
              const inGoal = byGoal.get(goal.id) ?? [];
              if (inGoal.length === 0) return null;
              const Icon = GOAL_ICONS[goal.id] ?? FlaskConical;
              return (
                <div key={goal.id}>
                  <CommandGroup heading={goal.label}>
                    {inGoal.map((module) => (
                      <CommandItem
                        key={module.id}
                        value={`${module.name} ${module.summary}`}
                        onSelect={() => select(`/modules/${module.id}`)}
                      >
                        <Icon className="size-4" />
                        <span>{module.name}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </div>
              );
            })}
          </CommandList>
          <div className="flex items-center justify-between gap-3 border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
            <span className="truncate">Search across modules, assays and pages</span>
            <span className="hidden shrink-0 items-center gap-2 sm:flex">
              <span className="inline-flex items-center gap-1">
                <kbd className="rounded border border-border/70 bg-surface-wash/70 px-1.5 py-0.5 font-mono text-xs">
                  ↑↓
                </kbd>
                Navigate
              </span>
              <span className="inline-flex items-center gap-1">
                <kbd className="rounded border border-border/70 bg-surface-wash/70 px-1.5 py-0.5 font-mono text-xs">
                  ↵
                </kbd>
                Open
              </span>
            </span>
          </div>
        </Command>
      </CommandDialog>
    </CommandPaletteContext>
  );
}

/** The header's search affordance, responsive for mobile & desktop. */
export function CommandTrigger({ className }: { className?: string }) {
  const { open } = useCommandPalette();
  const modifier = useSyncExternalStore(NEVER_CHANGES, readModifierKey, noModifierKey);

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={open}
        aria-label="Search modules and pages"
        className="size-8 text-muted-foreground sm:hidden"
      >
        <Search className="size-4" />
      </Button>

      <Button
        variant="outline"
        size="sm"
        onClick={open}
        className={cn(
          "hidden h-8 w-full justify-start gap-2 px-2.5 font-normal text-muted-foreground sm:inline-flex sm:w-56",
          className,
        )}
      >
        <Search className="size-4 shrink-0" />
        <span className="truncate">Search…</span>
        <kbd className="pointer-events-none ml-auto hidden min-w-11 shrink-0 items-center justify-center gap-0.5 rounded border bg-surface-wash/45 px-1.5 font-mono text-xs font-medium text-muted-foreground sm:inline-flex">
          {modifier ? (
            <>
              <span className={modifier === "Ctrl" ? undefined : "text-xs"}>{modifier}</span>K
            </>
          ) : null}
        </kbd>
      </Button>
    </>
  );
}
