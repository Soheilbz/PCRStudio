"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

import { CommandTrigger } from "@/components/command/command-palette";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import type { ModuleManifest } from "@/lib/api/types";

interface Crumb {
  label: string;
  /** Where this step goes back to. The last crumb never links anywhere. */
  href?: string;
}

/**
 * Turns a path into a trail.
 */
function crumbsFor(pathname: string, modules: ModuleManifest[]): Crumb[] {
  if (pathname === "/") return [{ label: "Dashboard" }];
  if (pathname === "/account") return [{ label: "Account" }];
  if (pathname === "/sign-in") return [{ label: "Sign in" }];
  if (pathname === "/sign-up") return [{ label: "Create an account" }];
  if (pathname === "/recover") return [{ label: "Use a recovery code" }];
  if (pathname === "/about") return [{ label: "About" }];
  if (pathname === "/try") return [{ label: "Try it" }];
  if (pathname === "/privacy") return [{ label: "Privacy" }];
  if (pathname === "/terms") return [{ label: "Terms" }];
  if (pathname === "/modules") return [{ label: "Modules" }];
  if (pathname === "/projects") return [{ label: "Your projects" }];
  if (pathname.startsWith("/projects/")) {
    return [{ label: "Your projects", href: "/projects" }, { label: "Project" }];
  }
  if (pathname === "/organisation") {
    return [{ label: "Modules", href: "/modules" }, { label: "How they are organised" }];
  }

  if (pathname.startsWith("/modules/")) {
    const rest = pathname.slice("/modules/".length);
    const [moduleId = "", sub = ""] = rest.split("/");
    const name = modules.find((module) => module.id === moduleId)?.name ?? moduleId;
    const trail: Crumb[] = [
      { label: "Modules", href: "/modules" },
      ...(sub ? [{ label: name, href: `/modules/${moduleId}` }] : [{ label: name }]),
    ];
    // A nested view of a module (the multiplex panel builder, say) keeps the
    // module's own crumb clickable instead of collapsing into one label.
    if (sub) {
      trail.push({ label: sub.charAt(0).toUpperCase() + sub.slice(1) });
    }
    return trail;
  }
  const last = pathname.split("/").filter(Boolean).at(-1);
  if (!last) return [{ label: "PCRStudio" }];

  return [
    {
      label: last
        .split("-")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" "),
    },
  ];
}

export function AppHeader({ modules }: { modules: ModuleManifest[] }) {
  const crumbs = crumbsFor(usePathname(), modules);

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border/70 bg-surface-wash/75 px-3 shadow-[0_8px_24px_-24px_var(--foreground)] backdrop-blur-md sm:px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-1 !h-4" />
      <Breadcrumb className="min-w-0 flex-1">
        <BreadcrumbList className="flex-nowrap">
          {crumbs.map((crumb, index) => {
            const isLast = index === crumbs.length - 1;
            return (
              <Fragment key={crumb.label + index}>
                <BreadcrumbItem className="min-w-0">
                  {isLast || !crumb.href ? (
                    <BreadcrumbPage className="truncate">{crumb.label}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink render={<Link href={crumb.href} className="truncate" />}>
                      {crumb.label}
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
                {isLast ? null : <BreadcrumbSeparator />}
              </Fragment>
            );
          })}
        </BreadcrumbList>
      </Breadcrumb>
      <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
        <CommandTrigger />
        <ThemeToggle />
      </div>
    </header>
  );
}
