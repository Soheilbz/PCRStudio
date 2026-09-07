"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/**
 * Theme state for the whole app.
 *
 * `next-themes` writes the class before first paint via a small inline script,
 * which is what keeps a dark-mode visitor from seeing a white flash on load.
 */
export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      // Light is the bench default: most lab rooms are bright and most
      // protocols get printed. "Match system" stays available, it is just not
      // what an unconfigured visitor gets.
      defaultTheme="light"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
