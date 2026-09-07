import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The title block every page opens with. */
export function PageHeader({
  title,
  description,
  actions,
  className,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <header
      className={cn(
        "workbench-hero relative flex flex-col gap-4 overflow-hidden rounded-2xl border border-border/60 px-5 py-4 shadow-xs sm:px-6 sm:py-5",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-5 top-0 h-px bg-gradient-to-r from-primary/70 via-brand/50 to-transparent sm:inset-x-6"
      />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-serif text-2xl leading-tight tracking-tight text-balance sm:text-3xl">
              {title}
            </h1>
            {children}
          </div>
          {description ? (
            <p className="w-full text-justify text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex max-w-full min-w-0 flex-wrap items-center justify-start gap-2 sm:justify-end">
            {actions}
          </div>
        ) : null}
      </div>
    </header>
  );
}
