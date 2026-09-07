import { Skeleton } from "@/components/ui/skeleton";

/**
 * Immediate navigation feedback for authenticated, API-backed pages.
 *
 * The surrounding app layout/sidebar remain mounted while this segment is
 * loading. The visual skeleton is decorative; the live status is the single
 * announcement assistive technology needs for the transition.
 */
export default function AppLoading() {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="space-y-6">
      <span className="sr-only">Loading page…</span>

      <div aria-hidden="true" className="space-y-2">
        <Skeleton className="h-7 w-56 max-w-[70vw]" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>

      <div aria-hidden="true" className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-36 rounded-xl lg:col-span-2" />
        <Skeleton className="h-36 rounded-xl" />
        <Skeleton className="h-56 rounded-xl lg:col-span-3" />
      </div>
    </div>
  );
}
