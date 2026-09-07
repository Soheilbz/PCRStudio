import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useSyncExternalStore } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { GoalDescription, ModuleManifest } from "@/lib/api/types";

import { ModuleBrowser } from "./module-browser";

// `next/link` wants the App Router context, which does not exist outside a
// Next render. The anchor is all this component needs from it.
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

/*
 * A router that keeps the URL, so these tests exercise the real thing.
 *
 * The filters moved out of component state and into the address bar, which
 * means the component no longer holds the answer — the URL does. A mock that
 * merely swallowed `replace` would let every filter test pass while the list
 * never narrowed at all.
 *
 * So this one behaves the way the router does in both directions: it stores
 * what it is given, hands it back through `useSearchParams`, and — the part
 * that is easy to leave out — tells React that it changed. Without the
 * notification the component reads the new URL only on its next render, and
 * nothing would trigger one.
 */
let url = new URLSearchParams();
const listeners = new Set<() => void>();

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

const go = (next: string) => {
  url = new URLSearchParams(next.includes("?") ? next.slice(next.indexOf("?") + 1) : "");
  for (const listener of listeners) listener();
};

// Both are recorded, because *which* one a filter uses is part of the
// behaviour: pushing per keystroke would bury the previous page under six
// history entries, and replacing a deliberate click would make Back skip past
// the whole page instead of undoing it.
const replace = vi.fn(go);
const push = vi.fn(go);

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
  usePathname: () => "/modules",
  useSearchParams: () =>
    useSyncExternalStore(
      subscribe,
      () => url,
      () => url,
    ),
}));

beforeEach(() => {
  url = new URLSearchParams();
  replace.mockClear();
  push.mockClear();
});

const MODULES: ModuleManifest[] = [
  {
    id: "standard-pcr",
    name: "Standard PCR",
    summary: "Primer pairs for endpoint amplification of a single target.",
    guidance: "The default when you have one known template and want one clean product from it.",
    engine: "flanking-pair",
    goal: "amplify",
    status: "planned",
    modifiers: ["multiplex"],
    defaults: { allowedPolymerases: [], purposes: [], constraints: {}, cycling: {} },
    requires: [],
  },
  {
    id: "qpcr-probe",
    name: "qPCR — Hydrolysis Probe",
    summary: "Primer pairs with a matched internal probe.",
    guidance: "A probe inside the product adds a second layer of specificity.",
    engine: "pair-and-probe",
    goal: "quantify",
    status: "experimental",
    modifiers: [],
    defaults: { allowedPolymerases: [], purposes: [], constraints: {}, cycling: {} },
    requires: [],
  },
  {
    id: "lamp",
    name: "LAMP",
    summary: "Primer sets for loop-mediated isothermal amplification.",
    guidance: "Six regions, one temperature, no thermocycler.",
    engine: "loop-set",
    goal: "detect",
    status: "stable",
    modifiers: ["reverse-transcription"],
    defaults: { allowedPolymerases: [], purposes: [], constraints: {}, cycling: {} },
    requires: [],
  },
];

// The core publishes these; the browser only groups and labels by them.
const GOALS: GoalDescription[] = [
  {
    id: "amplify",
    label: "Amplify a region",
    rule: "Checked against the template alone.",
    count: 1,
  },
  { id: "quantify", label: "Quantify", rule: "Checked for even amplification.", count: 1 },
  { id: "detect", label: "Detect an organism", rule: "Checked against a background.", count: 1 },
  {
    id: "engineer",
    label: "Engineer a change",
    rule: "Checked against a template it changes.",
    count: 0,
  },
];

function moduleNames() {
  return screen
    .getAllByRole("link")
    .map((link) => link.textContent?.trim())
    .filter(Boolean);
}

describe("ModuleBrowser", () => {
  it("lists everything before anything is typed", () => {
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);
    expect(screen.getByText("3 of 3 modules")).toBeInTheDocument();
    expect(moduleNames()).toEqual(["Standard PCR", "qPCR — Hydrolysis Probe", "LAMP"]);
  });

  it("searches the summary, not only the name", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.type(screen.getByLabelText("Search modules"), "isothermal");

    expect(await screen.findByText("1 of 3 modules")).toBeInTheDocument();
    expect(moduleNames()).toEqual(["LAMP"]);
  });

  it("takes the words in any order", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.type(screen.getByLabelText("Search modules"), "probe hydrolysis");

    expect(await screen.findByText("1 of 3 modules")).toBeInTheDocument();
    expect(moduleNames()).toEqual(["qPCR — Hydrolysis Probe"]);
  });

  it("offers only the goals something is registered under", () => {
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    // "Engineer a change" is a real goal with nothing under it here; a chip
    // that can only ever return nothing is worse than no chip.
    expect(screen.queryByRole("button", { name: "Engineer a change" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Detect an organism" })).toBeInTheDocument();
  });

  it("narrows to one goal and back", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    const detect = screen.getByRole("button", { name: "Detect an organism" });
    await user.click(detect);
    expect(await screen.findByText("1 of 3 modules")).toBeInTheDocument();
    expect(detect).toHaveAttribute("aria-pressed", "true");

    // The same chip again is a toggle, not a second filter.
    await user.click(detect);
    expect(await screen.findByText("3 of 3 modules")).toBeInTheDocument();
  });

  it("combines a goal with a status", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.click(screen.getByRole("button", { name: "Detect an organism" }));
    await user.click(screen.getByRole("button", { name: "Needs review" }));

    // Nothing in this set is both detection and experimental.
    expect(await screen.findByText("0 of 3 modules")).toBeInTheDocument();
    expect(screen.getByText("No module matches those filters")).toBeInTheDocument();
  });

  it("says nothing matched rather than showing an empty grid", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.type(screen.getByLabelText("Search modules"), "sanger");
    expect(await screen.findByText("No module matches those filters")).toBeInTheDocument();

    // Two of these are on screen when nothing matched — one in the toolbar and
    // the prominent one in the empty state — and they now announce identically
    // because they do the same thing. The empty state's is the one somebody
    // looking at "no matches" actually reaches for.
    const [, inTheEmptyState] = screen.getAllByRole("button", { name: "Clear filters" });
    await user.click(inTheEmptyState!);
    expect(await screen.findByText("3 of 3 modules")).toBeInTheDocument();
  });
});

describe("the module cards", () => {
  it("demotes the machine identifier to the bottom edge rather than beside the title", () => {
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    const id = screen.getByText("standard-pcr");
    // A whisper, not a headline: tiny muted monospace, and never inside the
    // heading or the link where it would read as part of the module's name.
    expect(id).toHaveClass("font-mono", "text-muted-foreground/60");
    expect(id.closest("h1,h2,h3,h4,h5,h6")).toBeNull();
    expect(id.closest("a")).toBeNull();
  });

  it("gives every card a hover affordance that reveals itself", () => {
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    const card = screen.getByRole("link", { name: "Standard PCR" }).closest("[data-slot=card]");
    expect(card).not.toBeNull();
    // The card itself lifts and casts a shadow on hover…
    expect(card).toHaveClass(
      "group",
      "hover:-translate-y-0.5",
      "hover:border-primary/50",
      "hover:shadow-md",
    );
    // …and carries an "Open →" cue that is hidden until then.
    const cue = within(card as HTMLElement).getByText("Open");
    expect(cue).toHaveClass("opacity-0", "group-hover:opacity-100");
  });
});

describe("a filtered list is a place you can link to", () => {
  /*
   * Before this the filters lived in component state, so the address bar never
   * changed. "Send me the genotyping ones" had no answer, a bookmark caught
   * only the unfiltered list, a reload dropped the filter, and Back — which is
   * what everybody presses to undo a filter — left the page entirely.
   */
  it("puts the goal in the URL", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.click(screen.getByRole("button", { name: "Detect an organism" }));

    expect(push).toHaveBeenCalled();
    expect(url.get("goal")).toBe("detect");
  });

  it("reads the filter back out of the URL on arrival", async () => {
    // Which is what a shared link, a bookmark and a reload all depend on.
    url = new URLSearchParams("goal=quantify");
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    expect(await screen.findByText("qPCR — Hydrolysis Probe")).toBeInTheDocument();
    expect(screen.queryByText("Standard PCR")).not.toBeInTheDocument();
  });

  it("combines the filters into one address", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.type(screen.getByLabelText("Search modules"), "pcr");
    await user.click(screen.getByRole("button", { name: "Detect an organism" }));

    expect(url.get("q")).toBe("pcr");
    expect(url.get("goal")).toBe("detect");
  });

  it("keeps typing out of the history and a chosen filter in it", async () => {
    const user = userEvent.setup();
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    // Six keystrokes, six replaces, no pushes: none of "s", "sa", "san" is a
    // state anybody meant to be in, and pushing them turns one Back press into
    // six.
    await user.type(screen.getByLabelText("Search modules"), "sanger");
    expect(replace).toHaveBeenCalledTimes(6);
    expect(push).not.toHaveBeenCalled();
    expect(url.get("q")).toBe("sanger");

    // One deliberate click, one history entry, so Back undoes exactly it.
    await user.click(screen.getByRole("button", { name: "Detect an organism" }));
    expect(push).toHaveBeenCalledTimes(1);
  });

  it("leaves a cleared filter out of the address rather than writing it empty", async () => {
    const user = userEvent.setup();
    url = new URLSearchParams("goal=detect");
    render(<ModuleBrowser modules={MODULES} goals={GOALS} />);

    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    // `?goal=` and a bare `?` are both links somebody would have to look at
    // twice. Pushed, so clearing by accident is one Back press from undone.
    expect(push).toHaveBeenLastCalledWith("/modules", { scroll: false });
  });
});
