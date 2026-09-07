import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PcrStudioError } from "@/lib/api/error";
import { cn } from "@/lib/utils";

/** Shows a failure in the words the core used, rather than a generic apology. */
export function ErrorState({
  error,
  title = "Something went wrong",
  className,
}: {
  error: unknown;
  title?: string;
  className?: string;
}) {
  const message =
    error instanceof PcrStudioError || error instanceof Error
      ? error.message
      : "The core failed without saying why.";

  return (
    <Alert variant="destructive" className={cn("rounded-xl", className)}>
      <AlertTriangle />
      <AlertTitle className="font-serif text-base font-semibold">{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
