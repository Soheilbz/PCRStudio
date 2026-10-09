import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {
  email,
  signUp,
  signIn,
  newProject,
  enrollMfa,
  mailLink,
  freshTotp,
  password,
  workspacePage,
  selectWorkspace,
} from './helpers';
const visualDirectory =
  process.env.PCRSTUDIO_VISUAL_DIR ?? '../.local/artifacts/visual';
async function verifyRenderedPage(page: Page, artifact: string) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `${visualDirectory}/${artifact}.png`,
    fullPage: true,
  });
}
test('verified personal projects retain stale edits, support both themes and keyboard mobile navigation', async ({
  page,
  context,
  request,
}) => {
  const address = email('personal');
  await signUp(page, request, address);
  await expect(
    page.getByRole('heading', { name: 'Room for your next idea' }),
  ).toBeVisible();
  const path = await newProject(page, 'Synthetic alpha');
  await page
    .getByLabel('Description', { exact: true })
    .fill('My unsaved first-tab note');
  const second = await context.newPage();
  await second.goto(path);
  await second
    .getByLabel('Description', { exact: true })
    .fill('Saved from a second tab');
  await second.getByRole('button', { name: 'Save changes' }).click();
  await expect(second.getByRole('status')).toHaveText(
    'Saved. Your changes are up to date.',
  );
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Your unsaved edits are still here',
  );
  await expect(page.getByLabel('Description')).toHaveValue(
    'My unsaved first-tab note',
  );
  await page
    .getByRole('button', { name: 'Reload latest and replace my edits' })
    .click();
  await expect(page.getByLabel('Description')).toHaveValue(
    'Saved from a second tab',
  );
  await second.close();
  await page.goto(path);
  await expect(page.getByLabel('Project name')).toHaveValue('Synthetic alpha');
  await workspacePage(page, '/');
  await expect(
    page.getByRole('heading', { name: 'Synthetic alpha', exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `${visualDirectory}/projects-light-desktop.png`,
    fullPage: true,
  });
  const light = await new AxeBuilder({ page }).analyze();
  expect(light.violations).toEqual([]);
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: `${visualDirectory}/projects-dark-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 320, height: 720 });
  await expect(page.getByLabel('Workspace', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(
    page.getByRole('button', { name: 'Open navigation' }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: `${visualDirectory}/projects-dark-mobile.png`,
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Use light theme' }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: `${visualDirectory}/projects-light-mobile.png`,
    fullPage: true,
  });
  await workspacePage(page, '/');
  await page.getByRole('button', { name: 'New project' }).click();
  await verifyRenderedPage(page, 'new-project-light-mobile');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'New project' })).toBeFocused();
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await page.getByRole('button', { name: 'New project' }).click();
  await verifyRenderedPage(page, 'new-project-dark-mobile');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'New project' })).toBeFocused();
  await expect(page.getByRole('dialog')).toBeHidden();
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([
    'pcrstudio-theme',
  ]);
});
test('MFA owner invites membership, grants content separately, revokes immediately and recovers an orphan', async ({
  page,
  browser,
  request,
}) => {
  test.setTimeout(240_000);
  const ownerEmail = email('owner');
  const colleagueEmail = email('colleague');
  await signUp(page, request, ownerEmail);
  const secret = await enrollMfa(page);
  await verifyRenderedPage(page, 'account-light-desktop');
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await verifyRenderedPage(page, 'account-dark-desktop');
  await page.setViewportSize({ width: 320, height: 720 });
  await verifyRenderedPage(page, 'account-dark-mobile');
  await page.getByRole('button', { name: 'Use light theme' }).click();
  await verifyRenderedPage(page, 'account-light-mobile');
  await page.setViewportSize({ width: 1280, height: 720 });
  await workspacePage(page, '/workspace');
  await page.getByLabel('Organization name').fill('Synthetic organization');
  await page
    .getByRole('button', { name: 'Create organization', exact: true })
    .click();
  await selectWorkspace(page, 'Synthetic organization · Organization');
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(
    page.getByRole('heading', { name: 'Welcome back' }),
  ).toBeVisible();
  await signIn(page, ownerEmail, secret);
  await selectWorkspace(page, 'Synthetic organization · Organization');
  const path = await newProject(page, 'Synthetic private organization project');
  const organizationId = new URL(page.url()).searchParams.get('workspace');
  if (!organizationId)
    throw new Error('Workspace selection is missing its URL identifier');
  await page.goto(path.split('?')[0]);
  await expect(page.getByLabel('Project name')).toHaveValue(
    'Synthetic private organization project',
  );
  await expect(page.getByLabel('Workspace', { exact: true })).toHaveValue(
    organizationId,
  );
  await expect
    .poll(() => new URL(page.url()).searchParams.get('workspace'))
    .toBe(organizationId);
  await page.reload();
  await expect(page.getByLabel('Workspace', { exact: true })).toHaveValue(
    organizationId,
  );
  const colleagueContext = await browser.newContext();
  const colleague = await colleagueContext.newPage();
  await signUp(colleague, request, colleagueEmail);
  await workspacePage(page, '/members');
  await page.getByLabel('Email address').fill(colleagueEmail);
  await page.getByRole('button', { name: 'Send invitation' }).click();
  await expect(page.getByRole('status')).toContainText('Invitation created');
  await colleague.goto(
    await mailLink(request, colleagueEmail, 'invitations/accept'),
  );
  await colleague.getByRole('button', { name: 'Accept invitation' }).click();
  await selectWorkspace(colleague, 'Synthetic organization · Organization');
  await expect(
    colleague.getByRole('heading', { name: 'Room for your next idea' }),
  ).toBeVisible();
  await colleague.goto(path);
  await expect(colleague.getByRole('alert')).toBeVisible();
  await expect(
    colleague.getByText('Synthetic private organization project', {
      exact: true,
    }),
  ).toBeHidden();
  await page.goto(path);
  await page
    .getByLabel('Workspace member')
    .selectOption({ label: colleagueEmail });
  await page.getByLabel('Project role').selectOption('viewer');
  await page.getByRole('button', { name: 'Grant access' }).click();
  await expect(
    page.getByRole('cell', { name: colleagueEmail, exact: true }),
  ).toBeVisible();
  await colleague.goto(path);
  await expect(colleague.getByLabel('Project name')).toHaveAttribute(
    'readonly',
  );
  await expect(
    colleague.getByRole('button', { name: 'Save changes' }),
  ).toBeHidden();
  await page
    .getByLabel('Workspace member')
    .selectOption({ label: colleagueEmail });
  await page.getByLabel('Project role').selectOption('editor');
  await page.getByRole('button', { name: 'Grant access' }).click();
  await expect(
    page
      .getByRole('row')
      .filter({ hasText: colleagueEmail })
      .getByRole('cell', { name: 'editor', exact: true }),
  ).toBeVisible();
  await colleague.reload();
  await colleague.getByLabel('Description').fill('Synthetic editor change');
  await colleague.getByRole('button', { name: 'Save changes' }).click();
  await expect(colleague.getByRole('status')).toHaveText(
    'Saved. Your changes are up to date.',
  );
  await page.reload();
  await page
    .getByRole('row')
    .filter({ hasText: colleagueEmail })
    .getByRole('button', { name: 'Remove access' })
    .click();
  await expect(
    page.getByRole('cell', { name: colleagueEmail, exact: true }),
  ).toBeHidden();
  await colleague.reload();
  await expect(colleague.getByLabel('Project name')).toBeHidden();
  await expect(colleague.getByRole('alert')).toBeVisible();
  await page
    .getByLabel('Workspace member')
    .selectOption({ label: colleagueEmail });
  await page.getByLabel('Project role').selectOption('editor');
  await page.getByRole('button', { name: 'Grant access' }).click();
  await expect(
    page.getByRole('cell', { name: colleagueEmail, exact: true }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByLabel('Workspace member')
    .selectOption({ label: colleagueEmail });
  await page.getByLabel('Project role').selectOption('owner');
  await page.getByRole('button', { name: 'Transfer ownership' }).click();
  await expect(
    page.getByRole('heading', { name: 'Project Access' }),
  ).toBeHidden();
  await workspacePage(page, '/members');
  await page
    .getByRole('row')
    .filter({ hasText: colleagueEmail })
    .getByRole('button', { name: 'Revoke membership' })
    .click();
  await page.getByRole('button', { name: 'Revoke membership now' }).click();
  await expect(page.getByRole('status')).toContainText('Membership revoked');
  await colleague.reload();
  await expect(colleague.getByLabel('Project name')).toBeHidden();
  await page.goto(path);
  await expect(page.getByRole('status')).toContainText(
    'owner is no longer active',
  );
  await expect(page.getByLabel('Description')).toHaveAttribute('readonly');
  await workspacePage(page, '/account');
  await page
    .getByLabel('Authenticator or recovery code')
    .fill(await freshTotp(secret));
  await page.getByRole('button', { name: 'Confirm identity' }).click();
  await expect(page.getByRole('status')).toContainText('Identity confirmed');
  await workspacePage(page, '/workspace');
  await page.getByLabel('Ownerless project').selectOption({ index: 1 });
  await page
    .getByLabel('New project owner')
    .selectOption({ label: ownerEmail });
  await page.getByRole('button', { name: 'Recover management' }).click();
  await expect(page.getByRole('status')).toContainText(
    'Project management recovered',
  );
  await page.goto(path);
  await expect(page.getByLabel('Description')).not.toHaveAttribute('readonly');
  await selectWorkspace(page, 'Personal workspace · Personal');
  await expect(
    page.getByText('Synthetic private organization project', { exact: true }),
  ).toBeHidden();
  await expect(
    page.getByRole('heading', { name: 'Room for your next idea' }),
  ).toBeVisible();
  await selectWorkspace(page, 'Synthetic organization · Organization');
  await expect(
    page.getByRole('heading', {
      name: 'Synthetic private organization project',
    }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole('heading', { name: 'Room for your next idea' }),
  ).toBeVisible();
  await page.goForward();
  await expect(
    page.getByRole('heading', {
      name: 'Synthetic private organization project',
    }),
  ).toBeVisible();
  await workspacePage(page, '/members');
  await page.getByLabel('Email address').fill(colleagueEmail);
  await page.getByRole('button', { name: 'Send invitation' }).click();
  await expect(page.getByRole('status')).toContainText('Invitation created');
  await colleague.goto(
    await mailLink(request, colleagueEmail, 'invitations/accept'),
  );
  await colleague.getByRole('button', { name: 'Accept invitation' }).click();
  await selectWorkspace(colleague, 'Synthetic organization · Organization');
  await expect(
    colleague.getByRole('heading', { name: 'Room for your next idea' }),
  ).toBeVisible();
  await colleague.goto(path);
  await expect(colleague.getByLabel('Project name')).toBeHidden();
  await expect(colleague.getByRole('alert')).toBeVisible();
  await colleagueContext.close();
});
test('password reset and explicit session termination work through allauth and Mailpit', async ({
  page,
  browser,
  request,
}) => {
  const address = email('reset');
  await signUp(page, request, address);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(
    page.getByRole('heading', { name: 'Welcome back' }),
  ).toBeVisible();
  await page.goto('/reset-password');
  await page.getByLabel('Email address').fill(address);
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('status')).toContainText('If an account exists');
  await page.goto(await mailLink(request, address, 'password/reset/key'));
  const updated = password + '-updated';
  await page.getByLabel('New password').fill(updated);
  await page.getByRole('button', { name: 'Save new password' }).click();
  await expect(
    page.getByRole('heading', { name: /^(Welcome back|Projects)$/ }),
  ).toBeVisible();
  if (
    await page
      .getByRole('heading', { name: 'Projects', exact: true })
      .isVisible()
  ) {
    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(
      page.getByRole('heading', { name: 'Welcome back' }),
    ).toBeVisible();
  }
  await signIn(page, address, undefined, updated);
  const otherContext = await browser.newContext();
  const other = await otherContext.newPage();
  await signIn(other, address, undefined, updated);
  await workspacePage(page, '/account');
  const otherSession = page
    .getByRole('listitem')
    .filter({ has: page.getByText('Other browser', { exact: true }) });
  await otherSession.getByRole('button', { name: 'End session' }).click();
  await expect(otherSession).toBeHidden();
  await other.reload();
  await expect(
    other.getByRole('heading', { name: 'Welcome back' }),
  ).toBeVisible();
  await otherContext.close();
});
