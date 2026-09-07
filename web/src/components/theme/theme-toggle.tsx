"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { useMounted } from "@/hooks/use-mounted";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * One button, one click, two states.
 *
 * "Match system" is not here on purpose: a menu for a two-state switch costs a
 * click every time to reach the thing almost everyone wants. The third option
 * lives on the account page, where changing it is a deliberate act rather than
 * something done in passing.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // The server cannot know the visitor's theme, so the icon is only decided
  // after mount. A fixed icon until then avoids a hydration mismatch.
  const mounted = useMounted();
  const isDark = mounted && resolvedTheme === "dark";

  const label = !mounted
    ? "Change theme"
    : isDark
      ? "Switch to the light theme"
      : "Switch to the dark theme";

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="relative size-8"
            aria-label={label}
            onClick={() => setTheme(isDark ? "light" : "dark")}
          />
        }
      >
        {/* Both icons are rendered and crossfaded, so the button does not
              change width or jump as the swap happens. */}
        <Sun className="size-4 scale-100 rotate-0 transition-transform duration-200 dark:scale-0 dark:-rotate-90" />
        <Moon className="absolute size-4 scale-0 rotate-90 transition-transform duration-200 dark:scale-100 dark:rotate-0" />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
