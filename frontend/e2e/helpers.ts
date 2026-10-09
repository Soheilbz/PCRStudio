import { randomUUID, createHmac } from 'node:crypto';
import { expect, type APIRequestContext, type Page } from '@playwright/test';
export const password = 'Synthetic-Research-Passphrase-410!';
export const email = (label: string) => `${label}-${randomUUID()}@example.test`;
const submittedCodes = new Map<string, string>();
export async function freshTotp(secret: string) {
  // allauth rejects a successfully used code for the remainder of its period.
  const previous = submittedCodes.get(secret);
  await expect.poll(() => totp(secret), { timeout: 35_000 }).not.toBe(previous);
  const code = totp(secret);
  submittedCodes.set(secret, code);
  return code;
}
export async function mailLink(
  request: APIRequestContext,
  address: string,
  fragment: string,
) {
  const mailpit = process.env.MAILPIT_URL ?? 'http://localhost:8025';
  let link = '';
  await expect
    .poll(
      async () => {
        const list = await request.get(`${mailpit}/api/v1/search`, {
          params: { query: `to:${address}` },
        });
        expect(list.ok()).toBe(true);
        const data = (await list.json()) as { messages: { ID: string }[] };
        for (const message of data.messages) {
          const detail = await request.get(
            `${mailpit}/api/v1/message/${message.ID}`,
          );
          const body = (await detail.json()) as { Text: string };
          const found = body.Text.match(/https?:\/\/[^\s<>]+/g)?.find((value) =>
            value.includes(fragment),
          );
          if (found) {
            const url = new URL(found);
            link = url.pathname + url.search;
            return true;
          }
        }
        return false;
      },
      { timeout: 20_000 },
    )
    .toBe(true);
  return link;
}
export async function signIn(
  page: Page,
  address: string,
  secret?: string,
  pass = password,
) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(address);
  await page.getByLabel('Password', { exact: true }).fill(pass);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  if (secret) {
    await page
      .getByLabel('Authenticator or recovery code')
      .fill(await freshTotp(secret));
    await page.getByRole('button', { name: 'Confirm code' }).click();
  }
  await expect(
    page.getByRole('heading', { name: 'Projects', exact: true }),
  ).toBeVisible();
}
export async function signUp(
  page: Page,
  request: APIRequestContext,
  address: string,
) {
  await page.goto('/signup');
  await page.getByLabel('Email address').fill(address);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Verify your email' }),
  ).toBeVisible();
  await page.goto(await mailLink(request, address, 'verify-email'));
  await page.getByRole('button', { name: 'Verify email', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: /^(Welcome back|Projects)$/ }),
  ).toBeVisible();
  if (await page.getByRole('heading', { name: 'Welcome back' }).isVisible())
    await signIn(page, address);
  else
    await expect(
      page.getByRole('heading', { name: 'Projects', exact: true }),
    ).toBeVisible();
}
export async function enrollMfa(page: Page) {
  await workspacePage(page, '/account');
  await page.getByRole('button', { name: 'Set up authenticator' }).click();
  const secret = await page.getByLabel('Setup key').inputValue();
  await page
    .getByLabel('Six-digit authenticator code')
    .fill(await freshTotp(secret));
  await page
    .getByRole('button', { name: 'Enable two-factor authentication' })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Recovery codes', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Hide recovery codes' }).click();
  await page
    .getByLabel('Authenticator or recovery code')
    .fill(await freshTotp(secret));
  await page.getByRole('button', { name: 'Confirm identity' }).click();
  await expect(page.getByRole('status')).toContainText('Identity confirmed');
  return secret;
}
export async function workspacePage(page: Page, path: string) {
  const workspace = new URL(page.url()).searchParams.get('workspace');
  await page.goto(
    workspace
      ? `${path}${path.includes('?') ? '&' : '?'}workspace=${workspace}`
      : path,
  );
}
export async function selectWorkspace(page: Page, label: string) {
  const selector = page.getByLabel('Workspace', { exact: true });
  const id = await selector
    .getByRole('option', { name: label, exact: true })
    .getAttribute('value');
  if (!id) throw new Error('Requested workspace has no identifier');
  await selector.selectOption(id);
  await expect(selector).toHaveValue(id);
  await expect
    .poll(() => new URL(page.url()).searchParams.get('workspace'))
    .toBe(id);
  await expect(
    page.getByRole('heading', { name: 'Projects', exact: true }),
  ).toBeVisible();
}
export async function newProject(page: Page, name: string) {
  await workspacePage(page, '/');
  await page.getByRole('button', { name: 'New project' }).click();
  await page.getByLabel('Project name', { exact: true }).fill(name);
  await page
    .getByLabel('Description', { exact: true })
    .fill('Synthetic acceptance fixture');
  await page
    .getByRole('button', { name: 'Create project', exact: true })
    .click();
  await page
    .getByRole('link')
    .filter({ has: page.getByRole('heading', { name, exact: true }) })
    .click();
  await expect(page.getByLabel('Project name')).toHaveValue(name);
  return new URL(page.url()).pathname + new URL(page.url()).search;
}
export function totp(secret: string) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const char of secret.toUpperCase().replace(/=/g, '')) {
    const value = alphabet.indexOf(char);
    if (value < 0) throw new Error('Invalid synthetic TOTP fixture');
    bits += value.toString(2).padStart(5, '0');
  }
  const bytes = [];
  for (let index = 0; index + 8 <= bits.length; index += 8)
    bytes.push(parseInt(bits.slice(index, index + 8), 2));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30_000)));
  const hmac = createHmac('sha1', Buffer.from(bytes)).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 15;
  return ((hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000)
    .toString()
    .padStart(6, '0');
}
