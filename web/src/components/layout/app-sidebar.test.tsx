import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SidebarProvider } from "@/components/ui/sidebar";
import type { GoalDescription, ModuleManifest } from "@/lib/api/types";

import { AppSidebar } from "./app-sidebar";

/**
 * The collapsed rail, which is the part that went wrong.
 *
 * Expanded, the sidebar lists every module under its goal and that is right.
 * Collapsed, it used to list every module as an icon — and the icon means the
 * *goal*, so five modules under "amplify" drew five identical flasks. Measured
 * on the running app: twenty-five buttons drawn with ten icons, four of them
 * repeating. Tooltips existed, which is not navigation: a rail you have to
 * hover twenty-five times to read is a rail you cannot read.
 *
 * What is pinned here is the property, not the pixel count — one button per
 * goal when collapsed, and every module still reachable from it.
 */
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/modules",
}));

// The account menu in the footer imports the sign-out action, which reaches
// the session module, which is `server-only` and refuses to load here. Nothing
// under test calls it — the mock exists so the import graph resolves.
vi.mock("@/lib/auth/actions", () => ({
  signOutAction: vi.fn(),
}));

const GOALS: GoalDescription[] = [
  { id: "amplify", label: "Amplify a region", rule: "a known template", count: 2 },
  { id: "detect", label: "Detect an organism", rule: "a background genome", count: 2 },
];

function assay(id: string, name: string, goal: "amplify" | "detect"): ModuleManifest {
  return {
    id,
    name,
    summary: `${name} summary`,
    guidance: `${name} guidance, long enough to be useful to somebody reading it.`,
    engine: "flanking-pair",
    goal,
    status: "experimental",
    modifiers: [],
    defaults: { allowedPolymerases: [], purposes: [], constraints: {}, cycling: {} },
    requires: [],
  };
}

const MODULES: ModuleManifest[] = [
  assay("standard-pcr", "Standard PCR", "amplify"),
  assay("colony-pcr", "Colony PCR", "amplify"),
  assay("lamp", "LAMP", "detect"),
  assay("rpa", "RPA", "detect"),
];

function renderSidebar({ open }: { open: boolean }) {
  return render(
    <SidebarProvider defaultOpen={open}>
      <AppSidebar modules={MODULES} goals={GOALS} closedGroups={[]} user={null} />
    </SidebarProvider>,
  );
}

describe("expanded", () => {
  it("lists every module under its goal", () => {
    renderSidebar({ open: true });
    for (const one of MODULES) {
      expect(screen.getAllByText(one.name).length).toBeGreaterThan(0);
    }
  });
});

describe("collapsed", () => {
  it("shows one button per goal rather than one per module", () => {
    renderSidebar({ open: false });

    // The goals are there…
    for (const goal of GOALS) {
      expect(screen.getAllByText(goal.label).length).toBeGreaterThan(0);
    }

    // …and the modules are not, because that is the whole point: four modules
    // drawn as four buttons carrying two distinct icons is what this replaced.
    for (const one of MODULES) {
      expect(screen.queryByText(one.name)).not.toBeInTheDocument();
    }
  });

  it("reaches every module through its goal's flyout", async () => {
    const user = userEvent.setup();
    renderSidebar({ open: false });

    const trigger = screen.getByRole("button", { name: /Amplify a region/ });
    await user.click(trigger);

    const menu = await screen.findByRole("menu");
    // Its own modules, and not the other goal's.
    expect(within(menu).getByText("Standard PCR")).toBeInTheDocument();
    expect(within(menu).getByText("Colony PCR")).toBeInTheDocument();
    expect(within(menu).queryByText("LAMP")).not.toBeInTheDocument();
  });

  it("gives each goal in the flyout a link that goes somewhere", async () => {
    const user = userEvent.setup();
    renderSidebar({ open: false });

    await user.click(screen.getByRole("button", { name: /Detect an organism/ }));
    const menu = await screen.findByRole("menu");

    // A menu of labels that navigate nowhere would look right and do nothing.
    for (const [name, id] of [
      ["LAMP", "lamp"],
      ["RPA", "rpa"],
    ] as const) {
      const item = within(menu).getByText(name).closest("a");
      expect(item).toHaveAttribute("href", `/modules/${id}`);
    }
  });
});
