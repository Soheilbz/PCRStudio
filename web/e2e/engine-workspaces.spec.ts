import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const TILING_REFERENCE = readFileSync(
  new URL("../../tools/tests/corpus/NC_012920.1.fasta", import.meta.url),
  "utf8",
);

async function signUp(page: Page) {
  const stamp = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  await page.goto("/sign-up");
  await expect(page.locator('form[data-form-ready="true"]')).toBeVisible();
  await page.getByLabel("Name").fill(`CURRENT E2E ${stamp}`);
  await page.getByLabel("Email").fill(`r17-${stamp}@pcrstudio.example.com`);
  await page.getByRole("textbox", { name: "Password" }).fill("correct horse battery staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByTestId("recovery-code")).toBeVisible();
  await page.getByLabel(/I have saved this code/i).check();
  await page.getByRole("button", { name: "Go to my workspace" }).click();
  await page.waitForURL("/");
  return stamp;
}

async function start(page: Page, moduleId: string, name: string) {
  await page.goto(`/modules/${moduleId}`);
  await page.getByLabel(/start a project|start another/i).fill(name);
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await page.waitForURL(/\/projects\//);
}

test.describe("Current engine workspace wiring", () => {
  test.skip(!process.env.PCR_E2E_WITH_API, "Requires the authenticated API/database stack.");

  test("exposes the current qPCR, RACE, sequencing, inverse and tiling controls through real project workspaces", async ({
    page,
  }) => {
    const stamp = await signUp(page);

    await start(page, "qpcr-probe", `qPCR ${stamp}`);
    await page.getByRole("button", { name: "Probe design", exact: true }).click();
    await expect(page.locator("#probeProtocol")).toBeVisible();
    await page.locator("#probeProtocol").selectOption("idt-primetime-conventional");
    await page.getByRole("button", { name: /^Reaction/ }).click();
    await expect(page.locator("#probeReporter")).toBeVisible();
    await page.getByRole("button", { name: "Add target" }).click();
    await expect(page.getByLabel("Multiplex target 1 name")).toBeVisible();

    await start(page, "race", `RACE ${stamp}`);
    await page.getByRole("button", { name: "RACE direction", exact: true }).click();
    await expect(page.locator("#raceDirection")).toBeVisible();
    await page
      .locator('nav[aria-label="Design steps"] button')
      .filter({ hasText: "RACE reaction" })
      .click();
    await expect(page.locator("#raceChemistry")).toBeVisible();

    await start(page, "sequencing-primer", `Sanger ${stamp}`);
    await page.getByRole("button", { name: "Read design", exact: true }).click();
    await expect(page.locator("#sequencingDesignProfile")).toBeVisible();
    await page
      .getByRole("button", { name: /^Provider & reaction/ })
      .first()
      .click();
    await expect(page.locator("#sequencingProvider")).toBeVisible();

    await start(page, "inverse-pcr", `Inverse ${stamp}`);
    await page.getByRole("button", { name: "Digest & circle", exact: true }).click();
    await expect(page.locator("#inverseBranch")).toBeVisible();
    await expect(page.locator("#mappingUseCase")).toBeVisible();

    await start(page, "tiled-scheme", `Tiling ${stamp}`);
    await page
      .getByRole("button", { name: /^Lifecycle/ })
      .first()
      .click();
    await expect(page.locator("#tilingBackend")).toHaveValue("primalscheme3");
    await expect(page.locator("#tilingOperation")).toHaveValue("scheme-create");
  });
});

async function runCurrentWorkspace(page: Page) {
  await page
    .locator('nav[aria-label="Design steps"] button')
    .filter({ hasText: "Review and run" })
    .click();
  await expect(page.getByRole("button", { name: "Run and save", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Run and save", exact: true }).click();
  // A completed worker run may be orderable or may be an honest incomplete
  // result (for example, a tiled scheme with uncovered declared regions).
  // Both are successful result renderings; the UI must not turn the latter
  // into a fake order sheet just to make this assertion green.
  await expect(
    page.getByRole("heading", { name: /What to order|Design incomplete/i }).first(),
  ).toBeVisible({ timeout: 120_000 });
}

async function makeCurrentWorkspaceRunnable(page: Page, moduleId: string) {
  // The verified sequence example answers only Target. The remaining values
  // below are explicit, source-shaped test inputs for each current engine;
  // relying on a visually displayed fallback would test a request different
  // from the one a real user submitted.
  if (moduleId === "qpcr-probe") {
    await page.getByRole("button", { name: "Probe design", exact: true }).click();
    await page.locator("#probeProtocol").selectOption("thermofisher-taqman-conventional");
    await page.getByRole("button", { name: /^Reaction/ }).click();
    await expect(page.locator("#probeReporter")).toBeVisible();
    await expect(page.locator("#probeQuencher")).toBeVisible();
    await page.waitForTimeout(250);
    await page.locator("#probeQuencher").selectOption("TAMRA");
    await expect(page.locator("#probeQuencher")).toHaveValue("TAMRA");
    await page.locator("#probeReporter").selectOption("FAM");
    await expect(page.locator("#probeReporter")).toHaveValue("FAM");
    await expect(page.locator("#probeQuencher")).toHaveValue("TAMRA");
    return;
  }
  if (moduleId === "race") {
    await page.locator("#targetStart").fill("100");
    await page.locator("#targetLength").fill("300");
    await page.getByRole("button", { name: "RACE direction", exact: true }).click();
    await page.locator("#raceDirection").selectOption("5prime");
    await page.locator("#raceRound").selectOption("primary");
    await page
      .locator('nav[aria-label="Design steps"] button')
      .filter({ hasText: "RACE reaction" })
      .click();
    await page.locator("#raceChemistry").selectOption("generacer-kit-25-0355-vl");
    await page.locator("#raceSubstrate").selectOption("total-rna");
    await page.locator("#racePreparation").fill("RNA preparation SOP, revision 1");
    return;
  }
  if (moduleId === "sequencing-primer") {
    await page.locator("#targetStart").fill("100");
    await page.locator("#targetLength").fill("300");
    await page.getByRole("button", { name: "Read design", exact: true }).click();
    await page.locator("#direction").selectOption("forward");
    await page.locator("#deadZone").fill("20");
    await page.locator("#readLength").fill("700");
    return;
  }
  if (moduleId === "inverse-pcr") {
    const referenceSequence = (await page.getByRole("textbox", { name: "Sequence" }).inputValue())
      .split(/\r?\n/)
      .filter((line) => !line.trim().startsWith(">"))
      .join("")
      .replace(/\s+/g, "");
    await page.getByRole("button", { name: "Digest & circle", exact: true }).click();
    await page.locator("#inverseReferenceSequence").fill(`GCGGCCGC${referenceSequence}GCGGCCGC`);
    await page.locator("#enzyme").fill("NotI");
    await page.locator("#methylationBranch").fill("Reviewed restriction digest context");
    await page.locator("#leftEndPhosphate").selectOption("phosphorylated");
    await page.locator("#rightEndPhosphate").selectOption("phosphorylated");
    await page
      .locator("#linearControlProvenance")
      .fill("Linear control prepared under SOP revision 1");
    await page
      .locator("#circularizationProvenance")
      .fill("Restriction digest and self-ligation SOP revision 1");
    return;
  }
  if (moduleId === "tiled-scheme") {
    await page.getByRole("button", { name: "Lifecycle", exact: true }).click();
    await page.locator("#tilingAlignmentMode").selectOption("auto");
    await page.getByRole("button", { name: "Scheme design", exact: true }).click();
    await page.locator("#overlap").fill("100");
    await expect(page.locator("#overlap")).toHaveValue("100");
    await page.waitForTimeout(2_000);
    await page
      .locator('nav[aria-label="Design steps"] button')
      .filter({ hasText: "Pools" })
      .click();
    await page.locator("#pools").fill("1");
  }
}

test("runs the five CURRENT workspaces through browser → Next → Rust → Python result rendering", async ({
  page,
}) => {
  test.setTimeout(180_000);
  test.skip(
    !process.env.PCR_E2E_WITH_API,
    "Requires the qualified authenticated API/database/scientific stack.",
  );
  const stamp = await signUp(page);
  for (const [moduleId, label] of [
    ["qpcr-probe", "qPCR"],
    ["race", "RACE"],
    ["sequencing-primer", "Sanger"],
    ["inverse-pcr", "Inverse"],
    ["tiled-scheme", "Tiling"],
  ] as const) {
    await start(page, moduleId, `${label} runtime ${stamp}`);
    const sample = page.getByRole("button", { name: "pUC19", exact: true });
    await expect(sample).toBeVisible({ timeout: 15_000 });
    if (moduleId === "tiled-scheme") {
      await page.getByRole("textbox", { name: "Sequence" }).fill(TILING_REFERENCE);
    } else {
      await sample.click();
    }
    await makeCurrentWorkspaceRunnable(page, moduleId);
    await runCurrentWorkspace(page);
  }
});
