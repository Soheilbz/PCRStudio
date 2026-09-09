import { cookies, headers } from "next/headers";
import { AppFooter } from "@/components/layout/app-footer";
import { AppShell } from "@/components/layout/app-shell";
import { PublicHeader } from "@/components/layout/public-header";
import { MODULE_BINDINGS } from "@/lib/contracts/module-bindings.generated";
import { loadModules, loadVocabulary } from "@/lib/api/load";
import { requireUser } from "@/lib/auth/current-user";
import { isSafeDestination } from "@/lib/auth/destination";
import { notFound } from "next/navigation";

/**
 * Everything that lives inside the workbench.
 *
 * Signing in and signing up sit outside this on purpose: a page whose whole
 * job is to ask for a password should not also be offering a catalogue to
 * browse, and a sidebar full of modules somebody cannot open yet is an
 * invitation to leave rather than to finish.
 *
 * The module list is fetched here and handed to the shell, so the sidebar
 * arrives in the HTML rather than appearing after a client round trip. That is
 * also what lets a crawler see the navigation.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // These pages live beside the workbench routes so they can share the same
  // build and metadata, but they are public by contract. The proxy stamps the
  // pathname into the request headers; using that value here avoids making a
  // public page pay for catalogue calls or accidentally passing through the
  // account gate.
  const requestHeaders = await headers();
  const pathname = requestHeaders.get("x-pcr-pathname") ?? "";
  const requestedDestination = requestHeaders.get("x-pcr-destination") ?? pathname;
  const destination = isSafeDestination(requestedDestination) ? requestedDestination : "/";
  const isPublic = /^(?:\/(?:about|contact|docs|privacy|terms)(?:\/|$)|\/shared\/)/.test(pathname);
  if (isPublic) {
    return (
      <div className="workbench-shell flex min-h-svh flex-col bg-background">
        <PublicHeader />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12">
          <div className="mx-auto w-full max-w-5xl">{children}</div>
        </main>
        <AppFooter />
      </div>
    );
  }

  const cookieStore = await cookies();
  const user = await requireUser(destination);

  // The proxy redirects visitors without a session before this layout runs.
  // Once a session is present, reject an unknown module before loading the
  // shell's catalogue or rendering any child content; otherwise a streamed
  // dynamic layout can turn `notFound()` in the page into an HTTP 200.
  const moduleId = /^\/modules\/([^/]+)(?:\/|$)/.exec(pathname)?.[1];
  if (moduleId && !Object.hasOwn(MODULE_BINDINGS, moduleId)) notFound();

  const [{ modules, error }, { goals }] = await Promise.all([loadModules(), loadVocabulary()]);

  // The sidebar writes this itself when it is toggled. Reading it here is what
  // keeps a collapsed sidebar collapsed after a reload, instead of springing
  // open and then snapping shut once the client catches up. The cost is that
  // pages render per request rather than being served as static files; the HTML
  // a crawler receives is the same either way.
  // Whether a choice exists matters as much as what it was: with no cookie the
  // shell decides from the viewport instead, and stops as soon as someone
  // expresses a preference.
  const sidebarCookie = cookieStore.get("sidebar_state");
  const sidebarOpen = sidebarCookie?.value !== "false";
  const sidebarChosen = sidebarCookie !== undefined;
  // No cookie means a first visit, and a first visit starts folded: the whole
  // catalogue at once is a wall, and the two top-level entries above it are
  // where someone new should begin. An empty cookie is different from a missing
  // one -- it means every group was deliberately opened.
  // The name carries the vocabulary; see the note beside GROUP_COOKIE.
  const groupsCookie = cookieStore.get("sidebar_goals");
  const closedGroups = groupsCookie
    ? groupsCookie.value.split(".").filter(Boolean)
    : goals.map((goal) => goal.id);

  return (
    <AppShell
      modules={modules}
      goals={goals}
      coreError={error}
      sidebarOpen={sidebarOpen}
      sidebarChosen={sidebarChosen}
      closedGroups={closedGroups}
      user={user}
    >
      {children}
    </AppShell>
  );
}
