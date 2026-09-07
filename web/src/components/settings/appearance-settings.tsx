"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useTheme } from "next-themes";

import { useMounted } from "@/hooks/use-mounted";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const THEME_OPTIONS: { value: string; label: string; hint: string; icon: LucideIcon }[] = [
  { value: "light", label: "Light", hint: "Best under bench lighting", icon: Sun },
  { value: "dark", label: "Dark", hint: "Best in a dim room", icon: Moon },
  { value: "system", label: "System", hint: "Follow the operating system", icon: Monitor },
];

export function AppearanceSettings() {
  const { theme, setTheme } = useTheme();
  // The stored choice is unknown until the client runs, so no option is marked
  // selected during the server render.
  const mounted = useMounted();

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="font-serif text-lg font-semibold">Appearance</CardTitle>
        <CardDescription>
          Stored in this browser. Nothing about your preferences is sent anywhere.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <fieldset className="space-y-3">
          <legend className="sr-only">Theme</legend>
          <div className="grid gap-2.5 sm:grid-cols-3">
            {THEME_OPTIONS.map(({ value, label, hint, icon: Icon }) => {
              const selected = mounted && theme === value;
              return (
                <label
                  key={value}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-surface-wash/30 p-3 transition-colors hover:border-primary/30 hover:bg-surface-warm/20",
                    selected && "border-primary/50 bg-primary/10 shadow-xs",
                  )}
                >
                  <input
                    type="radio"
                    name="theme"
                    value={value}
                    checked={selected}
                    onChange={() => setTheme(value)}
                    className="sr-only"
                  />
                  <Icon
                    className={cn(
                      "mt-0.5 size-4 shrink-0",
                      selected ? "text-primary" : "text-muted-foreground",
                    )}
                  />
                  <span className="min-w-0 space-y-0.5">
                    <span className="block font-serif text-sm font-semibold">{label}</span>
                    <span className="block text-xs text-muted-foreground">{hint}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      </CardContent>
    </Card>
  );
}
