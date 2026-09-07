import { expect, test } from "@playwright/test";

// Short synthetic template; long enough to plausibly host a primer pair, short
// enough that a real design round-trips quickly.
const SEQUENCE = `>e2e-target\n${"ATGCGTACGATCGATCGTAGCTAGCTAGCATCGATCGATCGGTACCGATTACGGCATGC".repeat(4)}`;

test("try-it page renders its input", async ({ page }) => {
  await page.goto("/try");
  await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();

  const input = page.getByLabel("Sequence to design against");
  await expect(input).toBeVisible();
  await expect(page.getByRole("button", { name: /Design Primers/ })).toBeVisible();
});

/**
 * Paste a sequence and submit.
 *
 * Two graceful endings, both fine:
 * - Core reachable: a designed pair comes back and the guest scratchpad note
 *   appears above the result.
 * - Core down: `tryDesignAction` catches the transport failure and the form
 *   re-renders with a `role="alert"` explaining it, pasted sequence intact.
 *
 * Either way the page ends in a readable state, which is what this pins.
 */
test("submitting a sequence ends in a result or an honest error, never a crash", async ({
  page,
}) => {
  await page.goto("/try");
  await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();

  const input = page.getByLabel("Sequence to design against");
  await expect(input).toBeVisible();

  // The submit button stays disabled until React owns the textarea and counts
  // the bases, so filling may need a retry if hydration has not landed yet.
  const submit = page.getByRole("button", { name: /Design Primers/ });
  await expect(async () => {
    await input.fill(SEQUENCE);
    await expect(submit).toBeEnabled();
  }).toPass({ timeout: 15_000 });

  await submit.click();

  await expect(
    page
      .getByRole("alert")
      .first()
      .or(page.getByText("This run was generated in guest scratchpad mode.")),
  ).toBeVisible({ timeout: 30_000 });

  // A failure keeps what was typed; nothing was saved either way.
  await expect(input).toBeVisible();
});
