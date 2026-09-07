import { expect, test, type Page } from "@playwright/test";

/**
 * The one journey the product exists for, end to end through the real chain:
 *
 *   browser → Next.js server actions → Rust API → PostgreSQL
 *
 * Everything here needs the core up and its database migrated, so the whole
 * spec is gated behind `PCR_E2E_WITH_API` — the same gate the CI "stack" job
 * sets after starting the real API against a real Postgres. Without the gate
 * variable these tests skip rather than pretend.
 */

async function visibleControlAccessibilityProblems(page: Page): Promise<string[]> {
  return page.locator("body").evaluate((body) => {
    const issues: string[] = [];
    const visible = (element: Element) => {
      const node = element as HTMLElement;
      return node.offsetWidth > 0 || node.offsetHeight > 0 || node === document.activeElement;
    };
    const text = (element: Element) => (element.textContent ?? "").replace(/\s+/g, " ").trim();

    for (const element of body.querySelectorAll("button, input, textarea, select")) {
      if (!visible(element)) continue;
      const tag = element.tagName.toLowerCase();
      if (tag === "button") {
        const named =
          element.getAttribute("aria-label") || text(element) || element.getAttribute("title");
        if (!named) issues.push("button without an accessible name");
        continue;
      }
      if (tag === "input" && element.getAttribute("type") === "hidden") continue;
      const id = element.getAttribute("id");
      const labelled =
        element.getAttribute("aria-label") ||
        element.getAttribute("aria-labelledby") ||
        (id && body.querySelector(`label[for="${CSS.escape(id)}"]`));
      if (!labelled && !element.closest("label")) issues.push(`${tag} without a label`);
    }
    return issues;
  });
}

test.describe("authenticated critical journey", () => {
  test.skip(
    !process.env.PCR_E2E_WITH_API,
    "Full-stack journey: needs the API core and its database (set PCR_E2E_WITH_API).",
  );

  test("sign up, start a project, open it, delete it", async ({ page }) => {
    const stamp = Date.now().toString(36);
    const email = `e2e-${stamp}@pcrstudio.example.com`;
    const displayName = `E2E Journey ${stamp}`;
    const projectName = `Journey project ${stamp}`;

    // ── sign up ────────────────────────────────────────────────────────────
    await page.goto("/sign-up");
    await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Make your bench a little clearer" }),
    ).toBeVisible();

    await page.getByLabel("Name").fill(displayName);
    await page.getByLabel("Email").fill(email);
    // Role, not label: the visibility toggle also answers to "Show password".
    await page.getByRole("textbox", { name: "Password" }).fill("correct horse battery staple");

    await page.getByRole("button", { name: "Create account" }).click();

    // Sign-up lands on the one-time recovery code, not a redirect past it.
    await expect(page.getByTestId("recovery-code")).toBeVisible();

    // Moving on is deliberately gated behind acknowledging the code was saved;
    // the panel greys its Continue control out until the box is ticked.
    await page.getByLabel(/I have saved this code/i).check();
    await page.getByRole("button", { name: "Go to my workspace" }).click();
    await page.waitForURL("/");

    // Signed in: the display name is rendered by a server component that only
    // resolves when the session cookie survives the round trip to Postgres.
    await expect(
      page.getByText(`Welcome back, ${displayName.split(/\s+/)[0]}`).first(),
    ).toBeVisible({ timeout: 15_000 });

    // ── create a project ───────────────────────────────────────────────────
    await page.goto("/modules/standard-pcr");
    const nameInput = page.getByLabel(/start a project|start another/i);
    await nameInput.fill(projectName);
    await page.getByRole("button", { name: "Start", exact: true }).click();

    // Creating redirects straight into the workspace.
    await page.waitForURL(/\/projects\//);
    await expect(page.getByText(projectName).first()).toBeVisible();
    expect(
      await visibleControlAccessibilityProblems(page),
      "workspace controls should all be named",
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
      "the project workspace should not create horizontal page overflow",
    ).toBe(true);

    // The signed-in workbench is the densest product surface. Exercise the
    // narrow layout explicitly so a table or control group cannot silently
    // reintroduce page-level horizontal scrolling.
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
      "the project workspace should fit a 390px viewport without page overflow",
    ).toBe(true);
    await page.setViewportSize({ width: 1280, height: 900 });

    // ── run a real design through the worker ───────────────────────────────
    // The sample is deliberately deterministic and avoids making this journey
    // carry a second, hand-maintained biological fixture.
    await page.getByRole("button", { name: "pUC19", exact: true }).click();
    const review = page.getByRole("button", { name: "Review and run", exact: true });
    await expect(review).toBeEnabled({ timeout: 15_000 });
    await review.click();
    await expect(page.locator("#workspace-step-heading")).toBeFocused();
    expect(
      await visibleControlAccessibilityProblems(page),
      "review-step controls should all be named",
    ).toEqual([]);
    await expect(page.getByRole("button", { name: "Run and save", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Run and save", exact: true }).click();
    await expect(page.getByRole("heading", { name: "What to order", exact: true })).toBeVisible({
      timeout: 60_000,
    });
    const sortablePairHeader = page.getByRole("columnheader", { name: /Pair #/ });
    if (await sortablePairHeader.count()) {
      await expect(sortablePairHeader.getByRole("button")).toBeVisible();
    }

    // ── delete it again ────────────────────────────────────────────────────
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await page.getByRole("button", { name: "Confirm Delete" }).click();

    // Deletion lands on the list carrying the id it just retired, which is
    // what the undo offer there restores from.
    await page.waitForURL(/\/projects\?undone=/);

    // Back on the module page the project is gone from the list.
    await page.goto("/modules/standard-pcr");
    await expect(page.getByText(projectName)).toHaveCount(0);
  });
});
