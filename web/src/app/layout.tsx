import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";

import { ThemeProvider } from "@/components/theme/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { site, siteUrl } from "@/lib/site";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${site.name} — ${site.tagline}`,
    template: `%s — ${site.name}`,
  },
  description: site.description,
  applicationName: site.name,
  keywords: [
    "PCR",
    "primer design",
    "qPCR",
    "multiplex PCR",
    "LAMP",
    "molecular biology",
    "oligonucleotide",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: siteUrl,
    siteName: site.name,
    title: `${site.name} — ${site.tagline}`,
    description: site.description,
    locale: site.locale,
  },
  twitter: {
    card: "summary_large_image",
    title: `${site.name} — ${site.tagline}`,
    description: site.description,
  },
  robots: { index: true, follow: true },
  icons: { icon: "/icon.png" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f1ea" },
    { media: "(prefers-color-scheme: dark)", color: "#201d1a" },
  ],
};

// The module list is fetched here and handed to the shell, so the sidebar

/**
 * The document itself, and nothing else.
 *
 * What used to live here — the sidebar, the module list, who is signed in —
 * moved into `(app)/layout.tsx`, so that the pages which ask for a password can
 * be a page rather than a card floating in a workbench.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  /*
   * The nonce minted for this response, from the middleware that also set the
   * Content-Security-Policy naming it.
   *
   * Next stamps its own scripts automatically. This one has to be passed by
   * hand because it is not Next's: `next-themes` writes the theme class in a
   * small inline script before first paint, which is what stops a dark-mode
   * visitor seeing a white flash. Under a strict policy an inline script with
   * no nonce is blocked — so without this the page still renders, and flashes
   * white on every load for exactly the people who chose dark.
   */
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider nonce={nonce}>
          {children}
          <Toaster position="bottom-right" />
        </ThemeProvider>
      </body>
    </html>
  );
}
