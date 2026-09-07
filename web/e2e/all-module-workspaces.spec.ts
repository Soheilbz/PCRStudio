import { expect, test, type Page } from "@playwright/test";

import { MODULE_BINDINGS, type ModuleId } from "../src/lib/contracts/module-bindings.generated";

async function signUp(page: Page) {
  const stamp = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  await page.goto("/sign-up");
  await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();
  await page.getByLabel("Name").fill(`Module matrix ${stamp}`);
  await page.getByLabel("Email").fill(`matrix-${stamp}@pcrstudio.example.com`);
  await page.getByRole("textbox", { name: "Password" }).fill("correct horse battery staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByTestId("recovery-code")).toBeVisible();
  await page.getByLabel(/I have saved this code/i).check();
  await page.getByRole("button", { name: "Go to my workspace" }).click();
  await page.waitForURL("/");
  return stamp;
}

const MODULE_IDS = Object.keys(MODULE_BINDINGS) as ModuleId[];

test.describe("CURRENT module workspace matrix", () => {
  test.skip(!process.env.PCR_E2E_WITH_API, "Requires the authenticated API/database stack.");

  test("all 21 canonical modules create a workspace carrying the same module identity", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const stamp = await signUp(page);

    expect(MODULE_IDS).toHaveLength(21);
    for (const moduleId of MODULE_IDS) {
      await page.goto(`/modules/${moduleId}`);
      const name = `Matrix ${moduleId} ${stamp}`;
      await page.getByLabel(/start a project|start another/i).fill(name);
      await page.getByRole("button", { name: "Start", exact: true }).click();
      await page.waitForURL(/\/projects\//);

      await expect(page.locator('input[name="moduleId"]')).toHaveValue(moduleId);
      await expect(page.getByText(name).first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Review and run", exact: true })).toBeVisible();
    }
  });
});
