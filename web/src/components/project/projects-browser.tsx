"use client";

import {
  Activity,
  ArrowRight,
  Blocks,
  Clock,
  Dna,
  FlaskConical,
  FolderOpen,
  Microscope,
  Play,
  Plus,
  ScanLine,
  Search,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { LocalTime } from "@/components/local-time";
import type { ModuleManifest, Project } from "@/lib/api/types";

const GOAL_ICONS: Record<string, LucideIcon> = {
  amplify: FlaskConical,
  quantify: Activity,
  genotype: Dna,
  detect: Microscope,
  sequence: ScanLine,
  assemble: Blocks,
  engineer: Wrench,
};

export interface ProjectsBrowserProps {
  projects: Project[];
  modules: ModuleManifest[];
}

export function ProjectsBrowser({ projects, modules }: ProjectsBrowserProps) {
  const [query, setQuery] = useState("");
  const [selectedGoal, setSelectedGoal] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"updated" | "name" | "runs">("updated");

  const moduleMap = useMemo(() => {
    return new Map(modules.map((m) => [m.id, m]));
  }, [modules]);

  const goals = useMemo(() => {
    const set = new Set<string>();
    for (const m of modules) {
      if (m.goal) set.add(m.goal);
    }
    return Array.from(set).sort();
  }, [modules]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return projects
      .filter((p) => {
        if (q) {
          const nameMatch = p.name.toLowerCase().includes(q);
          const notesMatch = p.notes?.toLowerCase().includes(q) ?? false;
          const moduleMatch = (moduleMap.get(p.moduleId)?.name ?? p.moduleId)
            .toLowerCase()
            .includes(q);
          if (!nameMatch && !notesMatch && !moduleMatch) return false;
        }

        if (selectedGoal !== "all") {
          const mod = moduleMap.get(p.moduleId);
          if (mod?.goal !== selectedGoal) return false;
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === "name") {
          return a.name.localeCompare(b.name);
        }
        if (sortBy === "runs") {
          return b.runCount - a.runCount;
        }
        return b.updatedAt.localeCompare(a.updatedAt);
      });
  }, [projects, query, selectedGoal, sortBy, moduleMap]);

  return (
    <div className="space-y-4">
      {/* Search, Filter & Quick Action Toolbar */}
      <div className="workbench-card flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-surface-wash/45 p-3 sm:p-4">
        <div className="relative min-w-0 flex-1 basis-full sm:min-w-[16rem] sm:basis-auto">
          <label htmlFor="project-search" className="sr-only">
            Search projects
          </label>
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="project-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects by name, notes or assay…"
            className="pl-8 text-xs"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear project search"
              className="absolute top-1/2 right-1.5 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Goal Filter */}
          <select
            value={selectedGoal}
            onChange={(e) => setSelectedGoal(e.target.value)}
            aria-label="Filter projects by goal"
            className="h-9 rounded-lg border border-border/70 bg-surface-wash/35 px-2.5 py-1 text-xs text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="all">All Goals ({projects.length})</option>
            {goals.map((g) => {
              const countForGoal = projects.filter(
                (p) => moduleMap.get(p.moduleId)?.goal === g,
              ).length;
              return (
                <option key={g} value={g}>
                  {g.charAt(0).toUpperCase() + g.slice(1)} ({countForGoal})
                </option>
              );
            })}
          </select>

          {/* Sort By */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "updated" | "name" | "runs")}
            aria-label="Sort projects"
            className="h-9 rounded-lg border border-border/70 bg-surface-wash/35 px-2.5 py-1 text-xs text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="updated">Recently modified</option>
            <option value="name">Name (A–Z)</option>
            <option value="runs">Most runs</option>
          </select>

          {/* New Project Starter Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button size="sm" className="gap-1.5 shadow-xs">
                  <Plus className="size-3.5" />
                  <span>New Project</span>
                </Button>
              }
            />
            <DropdownMenuContent align="end" className="max-h-72 w-56 overflow-y-auto">
              <DropdownMenuLabel className="text-xs">Choose Design System</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {modules.map((m) => (
                <DropdownMenuItem
                  key={m.id}
                  render={<Link href={`/modules/${m.id}`} />}
                  className="cursor-pointer text-xs"
                >
                  <div className="flex flex-col">
                    <span className="font-serif text-xs font-semibold text-foreground">
                      {m.name}
                    </span>
                    <span className="text-xs text-muted-foreground">{m.goal}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <p className="sr-only" role="status" aria-live="polite">
        {filtered.length} project{filtered.length === 1 ? "" : "s"} shown
      </p>

      {/* Projects Grid or Empty Filter Results */}
      {filtered.length === 0 ? (
        <div className="workbench-card rounded-xl border border-dashed border-border/60 bg-surface-wash/40 p-10 text-center">
          <FolderOpen className="mx-auto size-8 text-muted-foreground" />
          <p className="mt-2 font-serif text-sm font-semibold text-foreground">
            No projects match your filter
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try adjusting your search query or resetting the filters.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={() => {
              setQuery("");
              setSelectedGoal("all");
            }}
          >
            Reset Filters
          </Button>
        </div>
      ) : (
        <ul className="grid gap-3.5 sm:grid-cols-2">
          {filtered.map((project) => (
            <li key={project.id}>
              <ProjectCard project={project} module={moduleMap.get(project.moduleId)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ProjectCard({ project, module }: { project: Project; module?: ModuleManifest }) {
  const Icon = (module?.goal ? GOAL_ICONS[module.goal] : null) ?? FolderOpen;

  return (
    <Link
      href={`/projects/${project.id}`}
      className="workbench-card group flex h-full cursor-pointer flex-col justify-between rounded-xl border bg-surface-wash/45 p-4 transition-all duration-150 hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md"
    >
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 space-y-1">
            <h2 className="truncate font-serif text-base font-semibold tracking-tight text-foreground group-hover:text-primary group-hover:underline">
              {project.name}
            </h2>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon className="size-3.5 shrink-0 text-primary" />
              <span className="truncate">{module?.name ?? project.moduleId}</span>
              {module?.goal ? (
                <>
                  <span>&middot;</span>
                  <span className="capitalize">{module.goal}</span>
                </>
              ) : null}
            </div>
          </div>

          <Badge variant="secondary" className="shrink-0 gap-1 text-xs tabular-nums">
            <Play className="size-2.5" />
            <span>
              {project.runCount} {project.runCount === 1 ? "run" : "runs"}
            </span>
          </Badge>
        </div>

        {project.notes ? (
          <p className="line-clamp-2 pt-0.5 text-xs leading-relaxed text-muted-foreground">
            {project.notes}
          </p>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border/50 pt-2.5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Clock className="size-3" />
          <span>
            Last touched <LocalTime iso={project.updatedAt} relative />
          </span>
        </span>

        <span className="flex items-center gap-1 font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
          <span>Open</span>
          <ArrowRight className="size-3 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </Link>
  );
}
