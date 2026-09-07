import type { Metadata } from "next";

import { AccountTabs } from "@/components/account/account-tabs";
import { PageHeader } from "@/components/page-header";
import { loadCatalogue } from "@/lib/api/load";
import { loadPreferences } from "@/lib/projects/load";
import { recoveryStatus } from "@/lib/auth/actions";
import { requireUser } from "@/lib/auth/current-user";

/**
 * What this page calls itself, in one place.
 *
 * The browser tab and the heading were two different names for the same page —
 * "Account & Preferences" above the window and "Settings & Preferences" above
 * the content. The short label in the sidebar, breadcrumb and palette stays
 * "Account": that is a nav label, and all three already agree on it.
 */
const PAGE_NAME = "Account & Preferences";

export const metadata: Metadata = {
  title: PAGE_NAME,
  description: "Your PCRStudio account, laboratory bench defaults, and interface preferences.",
  robots: { index: false, follow: true },
};

/**
 * Account & Laboratory Preferences page.
 * Neatly organized into categorized tabs for Bench Defaults, Profile & Data, Security, and Danger Zone.
 *
 * Entirely about one person, so a stranger is redirected to sign in rather
 * than shown a degraded version of the page.
 */
export default async function AccountPage() {
  const user = await requireUser("/account");

  const [preferences, catalogue] = await Promise.all([loadPreferences(), loadCatalogue()]);
  const recovery = await recoveryStatus();

  return (
    <div className="space-y-6">
      <PageHeader
        title={PAGE_NAME}
        description="Your account details, security credentials, laboratory bench presets, and display theme."
      />

      <AccountTabs
        user={user}
        preferences={preferences}
        polymerases={catalogue.polymerases}
        recovery={recovery}
      />
    </div>
  );
}
