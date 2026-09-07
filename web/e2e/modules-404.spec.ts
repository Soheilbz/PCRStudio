import { expect, test } from "@playwright/test";

/**
 * `/modules/<id>` sits behind the sign-in gate, so what an anonymous visitor
 * gets for an unknown id is the redirect — the page's own 404 contract is only
 * reachable by somebody with a session:
 *
 * - Signed in, core up: `loadModule` learns the id does not exist and the page
 *   calls `notFound()` — the response is a real HTTP 404.
 * - Signed in, core down: the transport failure is deliberately *not* treated
 *   as "missing"; the page stays a 200 and shows an error state.
 *
 * The first test pins the gate everybody reaches without an account. The
 * second is gated on `PCR_E2E_WITH_API`, signs up through the real form to get
 * a session, and then pins the strict 404 the module page itself owes.
 */
test("an anonymous visit to any /modules/<id> route is sent to sign in", async ({ page }) => {
  await page.goto("/modules/e2e-no-such-module");

  // The gate answers before the id is even looked at: no catalogue call, no
  // workbench shell, just the form with the destination carried along.
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fmodules%2Fe2e-no-such-module$/);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("signed in, an unknown /modules/<id> route returns HTTP 404 when the core answers", async ({
  page,
}) => {
  test.skip(
    !process.env.PCR_E2E_WITH_API,
    "Needs the API core for both the session and the real catalogue (set PCR_E2E_WITH_API).",
  );

  // A session, the same way a person gets one: through the sign-up form. The
  // one-time recovery code appears afterwards; it needs no acknowledgement to
  // simply go somewhere else.
  const stamp = Date.now().toString(36);
  await page.goto("/sign-up");
  await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();
  await page.getByLabel("Name").fill(`E2E 404 ${stamp}`);
  await page.getByLabel("Email").fill(`e2e-404-${stamp}@pcrstudio.example.com`);
  await page.getByRole("textbox", { name: "Password" }).fill("correct horse battery staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByTestId("recovery-code")).toBeVisible();

  const response = await page.goto("/modules/e2e-no-such-module");
  expect(response?.status()).toBe(404);
});
