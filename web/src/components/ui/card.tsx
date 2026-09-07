"use client";

import * as React from "react";

import { useHeadingTag } from "@/components/heading-level";
import { cn } from "@/lib/utils";

function Card({
  className,
  size = "default",
  ...props
}: React.ComponentProps<"div"> & { size?: "default" | "sm" }) {
  // The base card already carries `bg-card`, so looking for `bg-*` on the
  // finished class string cannot tell whether a caller supplied a deliberate
  // surface. Keep that distinction as data instead, allowing the workbench
  // tint to apply to default cards without overriding warning/result surfaces.
  const hasCustomSurface = typeof className === "string" && /(?:^|\s)bg-/.test(className);

  return (
    <div
      data-slot="card"
      data-size={size}
      data-surface={hasCustomSurface ? "custom" : "default"}
      className={cn(
        "group/card flex flex-col gap-(--card-spacing) overflow-hidden rounded-xl border border-border/70 bg-card py-(--card-spacing) text-sm text-card-foreground shadow-[0_10px_30px_-26px_color-mix(in_oklch,var(--foreground)_35%,transparent)] ring-1 ring-foreground/5 [--card-spacing:--spacing(4)] has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 data-[size=sm]:[--card-spacing:--spacing(3)] data-[size=sm]:has-data-[slot=card-footer]:pb-0 *:[img:first-child]:rounded-t-xl *:[img:last-child]:rounded-b-xl",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "group/card-header @container/card-header grid auto-rows-min items-start gap-1 rounded-t-xl px-(--card-spacing) has-data-[slot=card-action]:grid-cols-[1fr_auto] has-data-[slot=card-description]:grid-rows-[auto_auto] [.border-b]:pb-(--card-spacing)",
        className,
      )}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  // A real heading, ranked by where the card sits — see `heading-level.tsx` for
  // why the rank is derived rather than typed at each of the call sites.
  //
  // `createElement` rather than `<Tag …>`, because a capitalised variable in
  // JSX reads as a component whose identity changes every render, and the
  // linter is right to object to that shape even though the value here is only
  // ever the string name of a heading element.
  return React.createElement(useHeadingTag(), {
    "data-slot": "card-title",
    className: cn(
      "font-serif text-base leading-snug font-medium group-data-[size=sm]/card:text-sm",
      className,
    ),
    ...props,
  });
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-sm leading-relaxed text-muted-foreground", className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn("col-start-2 row-span-2 row-start-1 self-start justify-self-end", className)}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card-content" className={cn("px-(--card-spacing)", className)} {...props} />
  );
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn(
        "flex items-center rounded-b-xl border-t border-border/60 bg-surface-wash/55 p-(--card-spacing)",
        className,
      )}
      {...props}
    />
  );
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent };
