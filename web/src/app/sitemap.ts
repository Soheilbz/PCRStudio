import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

/**
 * Only what a stranger may actually see. The workbench pages — `/`, the
 * module catalogue, `/organisation` — start behind the sign-in gate, so they
 * are nobody's search result; listing them would be listing redirects.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    // High, because it answers the question a search actually asked: not "what
    // is this" but "does it do the thing I need". Somebody who lands here can
    // find that out in one paste.
    { url: `${siteUrl}/try`, changeFrequency: "monthly", priority: 0.9 },
    { url: `${siteUrl}/about`, changeFrequency: "monthly", priority: 0.5 },
    // Low priority but present. Nobody searches for these, and a site that
    // hides them is a site that looks like it has something to hide.
    { url: `${siteUrl}/privacy`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${siteUrl}/terms`, changeFrequency: "yearly", priority: 0.3 },
  ];
}
