import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      /*
       * None of these is content, and most are about one person.
       *
       * `/projects` and `/shared` are the ones that matter. A crawler cannot
       * reach a project without a session and cannot guess a share token, but
       * a share link pasted somewhere public is a link a crawler will follow —
       * and a result that ends up in a search index is a result its owner did
       * not put there. Those pages also carry `noindex` for the crawlers that
       * fetch first and read the rules afterwards.
       *
       * `/modules` and `/organisation` are part of the workbench, which starts
       * behind the sign-in gate: an index entry for them would be an entry
       * for a redirect.
       *
       * `/recover` is here because a page whose whole subject is somebody
       * being locked out should not be a search result.
       */
      disallow: [
        "/account",
        "/projects",
        "/shared",
        "/sign-in",
        "/sign-up",
        "/recover",
        "/modules",
        "/organisation",
      ],
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
