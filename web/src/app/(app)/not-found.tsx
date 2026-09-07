import { Compass } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <div className="py-10">
      <EmptyState
        icon={Compass}
        title="That page does not exist"
        description="The address does not match anything in PCRStudio."
        action={
          <Button render={<Link href="/" />} variant="outline" size="sm">
            Back to the dashboard
          </Button>
        }
      />
    </div>
  );
}
