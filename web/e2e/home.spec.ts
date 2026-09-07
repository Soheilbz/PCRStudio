import { expect, test } from "@playwright/test";

/**
 * The home page is the dashboard, and the dashboard belongs to an account.
 *
 * Two layers enforce that: the proxy turns a request with no session cookie
 * away before anything renders, and `requireUser` in the page itself checks
 * the session is real even when a cookie is present. What an anonymous visit
 * must never produce is the workbench.
 */
test("an anonymous visit to home is sent to sign in, carrying where they were heading", async ({
  page,
}) => {
  await page.goto("/");

  // Landed on the form, not the dashboard, and the destination rode along so
  // signing in resumes the journey.
  await expect(page).toHaveURL(/\/sign-in\?next=%2F$/);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("the gate is a redirect, not an empty page", async ({ page }) => {
  const response = await page.goto("/");

  // The redirect chain resolves to a normal 200 document (the sign-in page).
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});
