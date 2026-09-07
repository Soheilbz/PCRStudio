import { FlaskConical, Link2Off, TriangleAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { SharedRun } from "@/components/project/shared-run";
import { Button } from "@/components/ui/button";
import { currentUser } from "@/lib/auth/current-user";
import { loadSharedRun } from "@/lib/projects/load";

export const metadata: Metadata = {
  title: "A shared result",
  robots: { index: false, follow: false, nocache: true },
};

/**
 * One result, to whoever holds the link.
 */
export default async function SharedPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const [loaded, user] = await Promise.all([loadSharedRun(token), currentUser()]);

  if (loaded.status === "unreachable") {
    return (
      <EmptyState
        icon={TriangleAlert}
        title="This shared result is temporarily unavailable"
        description="The service could not verify the link just now. Try again in a moment; this does not mean the link was withdrawn."
      />
    );
  }

  if (loaded.status === "missing") {
    return (
      <EmptyState
        icon={Link2Off}
        title="This link does not lead anywhere"
        description="It may have been withdrawn, or it may never have been a link. Ask whoever sent it for another."
        action={
          <Button render={<Link href="/try" />} size="sm">
            <FlaskConical />
            Design one of your own
          </Button>
        }
      />
    );
  }

  return <SharedRun run={loaded.run} token={token} signedIn={Boolean(user)} />;
}
