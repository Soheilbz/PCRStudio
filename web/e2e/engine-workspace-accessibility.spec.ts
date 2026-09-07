import { expect, test, type Page } from "@playwright/test";

async function signUp(page: Page) {
  const stamp = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  await page.goto("/sign-up");
  await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();
  await page.getByLabel("Name").fill(`A11y ${stamp}`);
  await page.getByLabel("Email").fill(`a11y-${stamp}@pcrstudio.example.com`);
  await page.getByRole("textbox", { name: "Password" }).fill("correct horse battery staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByTestId("recovery-code")).toBeVisible();
  await page.getByLabel(/I have saved this code/i).check();
  await page.getByRole("button", { name: "Go to my workspace" }).click();
  await page.waitForURL("/");
  return stamp;
}

test("qPCR authenticated workspace remains labelled, keyboard reachable and viewport-safe", async ({
  page,
}) => {
  test.skip(!process.env.PCR_E2E_WITH_API, "Requires the authenticated stack.");
  const stamp = await signUp(page);
  await page.goto("/modules/qpcr-probe");
  await page.getByLabel(/start a project|start another/i).fill(`A11y qPCR ${stamp}`);
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await page.waitForURL(/\/projects\//);
  // A new project opens on the target step. Reach the assay-specific controls
  // through the same labelled step navigation a keyboard user gets.
  await page.getByRole("button", { name: "Probe design", exact: true }).click();
  await expect(page.locator("#probeProtocol")).toBeVisible();
  const issues = await page.locator("body").evaluate((body) => {
    const problems: string[] = [];
    const visible = (el: Element) => {
      const n = el as HTMLElement;
      return n.offsetWidth > 0 || n.offsetHeight > 0;
    };
    for (const el of body.querySelectorAll("button,input,textarea,select")) {
      if (!visible(el) || (el instanceof HTMLInputElement && el.type === "hidden")) continue;
      const id = el.getAttribute("id");
      const named =
        el.getAttribute("aria-label") ||
        el.getAttribute("aria-labelledby") ||
        (id && body.querySelector(`label[for="${CSS.escape(id)}"]`)) ||
        el.closest("label") ||
        (el.tagName === "BUTTON" && (el.textContent ?? "").trim());
      if (!named) problems.push(`${el.tagName.toLowerCase()} has no accessible name`);
    }
    return problems;
  });
  expect(issues).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    ),
  ).toBe(true);
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).not.toHaveCount(0);
});
