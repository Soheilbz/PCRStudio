import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { STATUS_LABELS } from "@/lib/api/labels";
import type { ModuleStatus } from "@/lib/api/types";

/**
 * Says out loud how finished a module is.
 *
 * Nothing on the bench should have to guess whether a number came from a
 * validated implementation or a placeholder, so every module carries this.
 */
const STYLES: Record<ModuleStatus, string> = {
  planned: "border-border bg-surface-wash/50 text-muted-foreground",
  experimental: "border-warning/35 bg-warning/12 text-warning",
  stable: "border-success/35 bg-success/12 text-success",
};

export function ModuleStatusBadge({
  status,
  className,
}: {
  status: ModuleStatus;
  className?: string;
}) {
  return (
    <Badge variant="outline" className={cn("font-medium", STYLES[status], className)}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}
