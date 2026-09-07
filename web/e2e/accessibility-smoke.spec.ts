import { expect, test } from "@playwright/test";

/**
 * Small browser-level accessibility contract for pages that do not need the
 * API. This is intentionally dependency-free: it catches the regressions that
 * are easiest to introduce while changing layout (unnamed controls, missing
 * labels, broken links and images) without making the suite depend on a third
 * party scanner's ruleset.
 */
const ROUTES = [
  "/about",
  "/docs",
  "/privacy",
  "/terms",
  "/contact",
  "/try",
  "/sign-in",
  "/sign-up",
];

test.describe("accessible page foundations", () => {
  for (const route of ROUTES) {
    test(`${route} has a usable document surface`, async ({ page }) => {
      const response = await page.goto(route);
      expect(response?.status(), `${route} should respond successfully`).toBe(200);
      await expect(page.locator("main")).toBeVisible();
      await expect(page.locator("main h1")).toHaveCount(1);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
        ),
        `${route} should not create horizontal page overflow`,
      ).toBe(true);

      const problems = await page.locator("body").evaluate((body) => {
        const issues: string[] = [];
        const visible = (element: Element) => {
          const node = element as HTMLElement;
          return node.offsetWidth > 0 || node.offsetHeight > 0 || node === document.activeElement;
        };
        const text = (element: Element) => (element.textContent ?? "").replace(/\s+/g, " ").trim();

        for (const element of body.querySelectorAll("a, button, input, textarea, select, img")) {
          if (!visible(element)) continue;
          const tag = element.tagName.toLowerCase();
          if (tag === "img" && !element.hasAttribute("alt")) {
            issues.push("image without alt");
            continue;
          }
          if (tag === "a") {
            if (!element.getAttribute("href")) issues.push(`link without href: ${text(element)}`);
            continue;
          }
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
            (id && body.querySelector(`label[for="${CSS.escape(id)}"]`));
          if (!labelled && !element.closest("label")) {
            issues.push(`${tag} without a label`);
          }
        }
        return issues;
      });

      expect(problems, `${route} accessibility issues`).toEqual([]);
    });
  }
});
