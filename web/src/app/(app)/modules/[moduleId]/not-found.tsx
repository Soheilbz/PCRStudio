import { PackageSearch } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export default function ModuleNotFound() {
  return (
    <div className="py-10">
      <EmptyState
        icon={PackageSearch}
        title="No module has that identifier"
        description="The core does not have a design system registered under this address. It may have been renamed, or the link may be out of date."
        action={
          <Button render={<Link href="/modules" />} variant="outline" size="sm">
            See the modules that exist
          </Button>
        }
      />
    </div>
  );
}
