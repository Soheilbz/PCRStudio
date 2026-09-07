/**
 * Facts about the deployment that both the pages and the metadata need.
 *
 * `NEXT_PUBLIC_SITE_URL` has to be the public origin for canonical URLs, the
 * sitemap and social cards to be right; it falls back to localhost so a local
 * run works without configuration.
 */
import { requirePublicOrigin } from "@/lib/http/public-origin";

export const siteUrl = requirePublicOrigin(
  process.env.NEXT_PUBLIC_SITE_URL,
  "http://localhost:3000",
).origin;

export const site = {
  name: "PCRStudio",
  tagline: "Primer design for the bench",
  description:
    "PCRStudio is an open workbench for designing and checking PCR primers. Each design system — endpoint PCR, quantitative PCR, multiplex panels, isothermal amplification and genotyping assays — is a separate module with its own parameters.",
  repository: "https://github.com/Soheilbz/PCRStudio",
  locale: "en_US",
} as const;

/**
 * A JSON document safe to put inside a `<script>` tag.
 *
 * `JSON.stringify` alone is not: a `</script>` — or a `<` of any kind, or a
 * line separator the HTML parser treats as one — inside user-reached text
 * closes the tag early and becomes markup on the page. Escaping those
 * characters as Unicode escapes leaves the JSON semantically identical while
 * making it impossible for it to break out of the element.
 */
export function jsonLd(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}
