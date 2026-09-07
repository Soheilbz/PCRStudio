import { expect, test, type Page } from "@playwright/test";

async function openForm(page: Page, path: string) {
  await page.goto(path);
  const form = page.locator("form").first();
  await expect(form).toBeVisible({ timeout: 15_000 });
  await expect(form).toHaveAttribute("data-form-ready", "true", { timeout: 15_000 });
}

/**
 * The sign-in form uses native `required` constraints, so an empty submit is
 * stopped in the browser before any server action runs — no backend needed to
 * see the feedback.
 */
test("sign-in page renders its credentials form", async ({ page }) => {
  await openForm(page, "/sign-in");

  await expect(page.getByLabel("Email")).toBeVisible();
  // Role, not label: the visibility toggle inside the password field also
  // picks up the accessible name "Show password".
  const password = page.getByRole("textbox", { name: "Password" });
  await expect(password).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("submitting empty credentials shows validation feedback and stays put", async ({ page }) => {
  await openForm(page, "/sign-in");

  const email = page.getByLabel("Email");
  await page.getByRole("button", { name: "Sign in" }).click();

  // The submission was blocked: still on the form, and the browser is pointing
  // at the first field it refused.
  await expect(email).toBeFocused();
  expect(await email.evaluate((el: HTMLInputElement) => !el.checkValidity())).toBe(true);
  // Something is actually said, not just silently blocked.
  expect(
    await email.evaluate((el: HTMLInputElement) => el.validationMessage.length),
  ).toBeGreaterThan(0);
});

test.describe("email inline validation", () => {
  test("shows error for invalid email format on blur", async ({ page }) => {
    await openForm(page, "/sign-in");

    const email = page.getByLabel("Email");
    await email.fill("not-an-email");
    await email.blur();

    // Should show inline validation error
    await expect(page.getByText("Enter a valid email address")).toBeVisible();
    await expect(email).toHaveAttribute("aria-invalid", "true");
  });

  test("clears error when email becomes valid", async ({ page }) => {
    await openForm(page, "/sign-in");

    const email = page.getByLabel("Email");
    await email.fill("not-an-email");
    await email.blur();
    await expect(page.getByText("Enter a valid email address")).toBeVisible();

    await email.fill("valid@lab.example");
    await email.blur();

    await expect(page.getByText("Enter a valid email address")).not.toBeVisible();
    await expect(email).toHaveAttribute("aria-invalid", "false");
  });

  test("shows required error for empty email on blur", async ({ page }) => {
    await openForm(page, "/sign-in");

    const email = page.getByLabel("Email");
    await email.focus();
    // Use a real keyboard focus transition; Base UI's input primitive can
    // treat a programmatic blur of an untouched native email field as a no-op.
    await page.keyboard.press("Tab");

    await expect(page.getByText("Email is required")).toBeVisible();
  });
});

test.describe("password strength indicator (sign-up)", () => {
  test("shows strength meter while typing password", async ({ page }) => {
    await openForm(page, "/sign-up");

    const password = page.getByRole("textbox", { name: "Password" });
    await password.fill("weak");

    // Should show "Very weak" or "Weak"
    await expect(page.getByText(/very weak|weak/i)).toBeVisible();

    await password.fill("StrongerPass123");

    // Should show "Fair" or better
    await expect(page.getByText(/fair|good|strong/i)).toBeVisible();

    await password.fill("correct horse battery staple");

    // Should show "Strong"
    await expect(page.getByText(/strong/i)).toBeVisible();
  });

  test("hides strength meter when field is empty", async ({ page }) => {
    await openForm(page, "/sign-up");

    const password = page.getByRole("textbox", { name: "Password" });
    await password.fill("something");
    await expect(page.getByText(/weak|fair|good|strong/i)).toBeVisible();

    await password.clear();
    await expect(page.getByRole("progressbar", { name: "Password strength" })).not.toBeVisible();
  });
});

test.describe("password visibility toggle", () => {
  test("toggles password visibility on sign-in", async ({ page }) => {
    await openForm(page, "/sign-in");

    const password = page.getByRole("textbox", { name: "Password" });
    await password.fill("secret123");

    // Initially hidden
    await expect(password).toHaveAttribute("type", "password");

    // Click show password button
    await page.getByRole("button", { name: "Show password" }).click();

    // Now visible
    await expect(password).toHaveAttribute("type", "text");

    // Click hide password button
    await page.getByRole("button", { name: "Hide password" }).click();

    // Hidden again
    await expect(password).toHaveAttribute("type", "password");
  });

  test("toggles password visibility on sign-up", async ({ page }) => {
    await openForm(page, "/sign-up");

    const password = page.getByRole("textbox", { name: "Password" });
    await password.fill("secret123");

    await page.getByRole("button", { name: "Show password" }).click();
    await expect(password).toHaveAttribute("type", "text");

    await page.getByRole("button", { name: "Hide password" }).click();
    await expect(password).toHaveAttribute("type", "password");
  });
});

test.describe("recovery flow guidance on sign-in", () => {
  test("shows password recovery link", async ({ page }) => {
    await openForm(page, "/sign-in");

    await expect(page.getByRole("link", { name: "Forgot your password?" })).toBeVisible();
  });
});

test.describe("sign-up page", () => {
  test("renders name, email, and password fields", async ({ page }) => {
    await openForm(page, "/sign-up");

    await expect(page.getByLabel("Name")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Password" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
  });

  test("shows 'Already have an account?' link to sign in", async ({ page }) => {
    await openForm(page, "/sign-up");

    await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  });

  test("password field has minimum length hint", async ({ page }) => {
    await openForm(page, "/sign-up");

    await expect(page.getByText("At least 10 characters")).toBeVisible();
  });
});

test.describe("recover page", () => {
  test("renders email, recovery code, and new password fields", async ({ page }) => {
    await openForm(page, "/recover");

    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Recovery code")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "New password" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Set a new password" })).toBeVisible();
  });

  test("shows inline email validation", async ({ page }) => {
    await openForm(page, "/recover");

    const email = page.getByLabel("Email");
    await email.fill("invalid");
    await email.blur();

    await expect(page.getByText("Enter a valid email address")).toBeVisible();
  });

  test("shows password strength indicator on new password", async ({ page }) => {
    await openForm(page, "/recover");

    const password = page.getByRole("textbox", { name: "New password" });
    await password.fill("weak");

    await expect(page.getByText(/very weak|weak/i)).toBeVisible();

    await password.fill("correct horse battery staple");
    await expect(page.getByText(/strong/i)).toBeVisible();
  });

  test("shows 'What this does' explanation", async ({ page }) => {
    await openForm(page, "/recover");

    // Collapsed by default so the form fits one screen; the detail is one
    // click away and must say what will happen before it happens.
    const details = page.locator("details", { hasText: "What this does" });
    await expect(details.locator("summary")).toBeVisible();
    await details.locator("summary").click();
    await expect(details.getByText("ends every other session")).toBeVisible();
    await expect(details.getByText("The code you use here is spent")).toBeVisible();
  });

  test("links back to sign-in page", async ({ page }) => {
    await openForm(page, "/recover");

    await page.getByRole("link", { name: "Sign in", exact: true }).click();
    await page.waitForURL("/sign-in");
  });
});
