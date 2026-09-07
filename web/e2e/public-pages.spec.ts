import { expect, test } from "@playwright/test";

const PUBLIC_PAGES = [
  "/about",
  "/docs",
  "/privacy",
  "/terms",
  "/contact",
  "/shared/not-a-real-link",
];
const DOCUMENTATION_PAGES = [
  "/docs/quick-start",
  "/docs/account",
  "/docs/projects",
  "/docs/guides",
  "/docs/guides/flanking",
  "/docs/guides/probe",
  "/docs/guides/mutagenic",
  "/docs/guides/junction",
  "/docs/guides/tiling",
  "/docs/models",
  "/docs/specificity",
  "/docs/limits",
  "/docs/export",
  "/docs/api/auth",
  "/docs/api/design",
  "/docs/api/projects",
  "/docs/api/catalogue",
];

test("informational and shared-result pages are public", async ({ page }) => {
  for (const path of PUBLIC_PAGES) {
    const response = await page.goto(path, { waitUntil: "commit" });
    await page.waitForURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    expect(response?.status(), `${path} should render for a guest`).toBe(200);
    await expect(page).not.toHaveURL(/\/sign-in/);
  }
});

test("the public footer navigates to real pages", async ({ page }) => {
  await page.goto("/docs", { waitUntil: "domcontentloaded" });

  for (const [label, href] of [
    ["Privacy", "/privacy"],
    ["Terms", "/terms"],
    ["About", "/about"],
    ["Documentation", "/docs"],
    ["Contact", "/contact"],
  ] as const) {
    await expect(page.getByRole("link", { name: label, exact: true })).toHaveAttribute(
      "href",
      href,
    );
  }
});

test("every documentation link resolves", async ({ page }) => {
  for (const path of DOCUMENTATION_PAGES) {
    const response = await page.goto(path, { waitUntil: "commit" });
    await page.waitForURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    expect(response?.status(), `${path} should resolve`).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});
