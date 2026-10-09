import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { api } from '../app/lib/api';
import { privateKey } from '../app/lib/privacy';
import * as auth from '../app/lib/auth';
import { AccountContext } from '../app/lib/context';
import Account from '../app/routes/account';
import { Application } from '../app/routes/app';

afterEach(() => vi.restoreAllMocks());

it.each([false, true])(
  'confirms enrollment before reading recovery codes and refreshes identity on failure=%s',
  async (confirmationFails) => {
    const steps: string[] = [];
    vi.spyOn(auth, 'authRequest').mockImplementation(async (path, method) => {
      if (path === 'auth/sessions') return { status: 200, data: [] };
      if (path === 'account/authenticators/totp' && method === 'GET')
        return { status: 404, meta: { secret: 'SYNTHETICSETUPKEY' } };
      if (path === 'account/authenticators/totp') {
        steps.push('enrolled');
        return { status: 200 };
      }
      if (path === 'auth/2fa/reauthenticate') {
        steps.push('confirmed');
        if (confirmationFails)
          throw new Error('Synthetic confirmation failure');
        return { status: 200 };
      }
      steps.push('recovery');
      return { status: 200, data: { unused_codes: ['synthetic-recovery'] } };
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    render(
      <QueryClientProvider client={client}>
        <AccountContext.Provider
          value={{
            me: {
              id: 'synthetic-enrollment',
              email: 'enrollment@example.test',
              email_verified: true,
              mfa_enabled: false,
              mfa_required: false,
              mfa_authenticated: false,
            },
            refresh: async () => {},
          }}
        >
          <Account />
        </AccountContext.Provider>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    await user.click(
      screen.getByRole('button', { name: 'Set up authenticator' }),
    );
    await user.type(
      await screen.findByLabelText('Six-digit authenticator code'),
      '123456',
    );
    await user.click(
      screen.getByRole('button', { name: 'Enable two-factor authentication' }),
    );
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['me'] }),
    );
    expect(steps).toEqual(
      confirmationFails
        ? ['enrolled', 'confirmed']
        : ['enrolled', 'confirmed', 'recovery'],
    );
    if (confirmationFails)
      expect(
        await screen.findByText('Synthetic confirmation failure'),
      ).toBeVisible();
    else
      expect(
        await screen.findByRole('heading', { name: 'Recovery codes' }),
      ).toBeVisible();
  },
);

it('allows a required-MFA account to enroll an authenticator without any workspace context', async () => {
  vi.spyOn(auth, 'authRequest').mockImplementation(async (path) =>
    path === 'auth/sessions'
      ? { status: 200, data: [] }
      : {
          status: 404,
          meta: {
            secret: 'SYNTHETICSETUPKEY',
            totp_url: 'otpauth://totp/Synthetic',
          },
        },
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AccountContext.Provider
        value={{
          me: {
            id: 'synthetic-staff',
            email: 'staff@example.test',
            email_verified: true,
            mfa_enabled: false,
            mfa_required: true,
            mfa_authenticated: false,
          },
          refresh: async () => {},
        }}
      >
        <Account />
      </AccountContext.Provider>
    </QueryClientProvider>,
  );
  await userEvent
    .setup()
    .click(screen.getByRole('button', { name: 'Set up authenticator' }));
  expect(await screen.findByLabelText('Setup key')).toHaveValue(
    'SYNTHETICSETUPKEY',
  );
  expect(
    screen.getByRole('button', { name: 'Enable two-factor authentication' }),
  ).toBeEnabled();
  expect(auth.authRequest).toHaveBeenCalledWith(
    'account/authenticators/totp',
    'GET',
    undefined,
    [404],
  );
});

it('opens the security gate before trying a workspace request that requires MFA', async () => {
  const get = vi.spyOn(api, 'GET').mockImplementation(async (path) => {
    if (path === '/api/v1/csrf/')
      return {
        data: { csrf: 'synthetic' },
        response: new Response(null, { status: 200 }),
      } as never;
    if (path === '/api/v1/me/')
      return {
        data: {
          id: 'synthetic-staff',
          email: 'staff@example.test',
          email_verified: true,
          mfa_enabled: false,
          mfa_required: true,
          mfa_authenticated: false,
        },
        response: new Response(null, { status: 200 }),
      } as never;
    return {
      error: {
        code: 'mfa_required',
        detail: 'Two-factor authentication is required.',
      },
      response: new Response(null, { status: 403 }),
    } as never;
  });
  vi.spyOn(auth, 'authRequest').mockResolvedValue({ status: 200, data: [] });
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={['/account']}>
        <Application />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole('button', { name: 'Set up authenticator' }),
  ).toBeEnabled();
  expect(screen.getByRole('heading', { name: 'Account' })).toBeVisible();
  expect(get).not.toHaveBeenCalledWith(
    '/api/v1/workspaces/',
    expect.anything(),
  );
});

it('keeps an unsaved project draft when an identity refresh has a temporary service failure', async () => {
  vi.spyOn(api, 'GET').mockImplementation(async (path) =>
    path === '/api/v1/csrf/'
      ? ({
          data: { csrf: 'synthetic' },
          response: new Response(null, { status: 200 }),
        } as never)
      : ({
          error: { code: 'service_unavailable', detail: 'Please try again.' },
          response: new Response(null, { status: 503 }),
        } as never),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(['me'], {
    id: 'synthetic-user',
    email: 'fixture@example.test',
    email_verified: true,
    mfa_enabled: false,
    mfa_required: false,
    mfa_authenticated: false,
  });
  client.setQueryData(
    ['workspaces', 'synthetic-user'],
    [
      {
        id: 'synthetic-workspace',
        name: 'Personal workspace',
        kind: 'personal',
        role: 'owner',
      },
    ],
  );
  client.setQueryData(
    privateKey(
      'synthetic-user',
      'synthetic-workspace',
      'project',
      'synthetic-project',
    ),
    {
      id: 'synthetic-project',
      workspace_id: 'synthetic-workspace',
      name: 'Synthetic project',
      description: 'Saved note',
      version: 1,
      archived: false,
      orphaned: false,
      role: 'editor',
      owner_membership_id: 'synthetic-owner',
      created_at: '2026-10-05T12:00:00Z',
      updated_at: '2026-10-05T12:00:00Z',
    },
  );
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[
          '/projects/synthetic-project?workspace=synthetic-workspace',
        ]}
      >
        <Application />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const input = await screen.findByLabelText('Description');
  const user = userEvent.setup();
  await user.clear(input);
  await user.type(input, 'My unsaved synthetic draft');
  await client.invalidateQueries({ queryKey: ['me'] });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Please try again.',
  );
  expect(screen.getByLabelText('Description')).toHaveValue(
    'My unsaved synthetic draft',
  );
});

it('keeps the draft during a temporary project read failure and hides it when access is denied', async () => {
  let status = 503;
  vi.spyOn(api, 'GET').mockImplementation(
    async () =>
      ({
        error: {
          code: status === 503 ? 'service_unavailable' : 'access_unavailable',
          detail: status === 503 ? 'Please try again.' : 'Access unavailable.',
        },
        response: new Response(null, { status }),
      }) as never,
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(['me'], {
    id: 'synthetic-user',
    email: 'fixture@example.test',
    email_verified: true,
    mfa_enabled: false,
    mfa_required: false,
    mfa_authenticated: false,
  });
  client.setQueryData(
    ['workspaces', 'synthetic-user'],
    [
      {
        id: 'synthetic-workspace',
        name: 'Personal workspace',
        kind: 'personal',
        role: 'owner',
      },
    ],
  );
  const key = privateKey(
    'synthetic-user',
    'synthetic-workspace',
    'project',
    'synthetic-project',
  );
  client.setQueryData(key, {
    id: 'synthetic-project',
    workspace_id: 'synthetic-workspace',
    name: 'Synthetic project',
    description: 'Saved note',
    version: 1,
    archived: false,
    orphaned: false,
    role: 'editor',
    owner_membership_id: 'synthetic-owner',
    created_at: '2026-10-05T12:00:00Z',
    updated_at: '2026-10-05T12:00:00Z',
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[
          '/projects/synthetic-project?workspace=synthetic-workspace',
        ]}
      >
        <Application />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const input = await screen.findByLabelText('Description');
  const user = userEvent.setup();
  await user.clear(input);
  await user.type(input, 'My unsaved project draft');
  await client.invalidateQueries({ queryKey: key });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Please try again.',
  );
  expect(screen.getByLabelText('Description')).toHaveValue(
    'My unsaved project draft',
  );
  status = 403;
  await client.invalidateQueries({ queryKey: key });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Access unavailable.',
  );
  expect(screen.queryByLabelText('Description')).toBeNull();
});

it('settles a denied read before clearing its old content without starting a denial loop', async () => {
  const response = new Response(null, { status: 403 });
  Object.defineProperty(response, 'url', {
    value: 'http://localhost/api/v1/projects/synthetic-project/',
  });
  let deniedReads = 0;
  vi.spyOn(api, 'GET').mockImplementation(async (path) => {
    if (path === '/api/v1/projects/{project_id}/') {
      deniedReads += 1;
      return {
        error: { code: 'access_unavailable', detail: 'Access unavailable.' },
        response,
      } as never;
    }
    if (path === '/api/v1/csrf/')
      return {
        data: { csrf: 'synthetic' },
        response: new Response(null, { status: 200 }),
      } as never;
    if (path === '/api/v1/me/')
      return {
        data: {
          id: 'synthetic-user',
          email: 'fixture@example.test',
          email_verified: true,
          mfa_enabled: false,
          mfa_required: false,
          mfa_authenticated: false,
        },
        response: new Response(null, { status: 200 }),
      } as never;
    return {
      data: [
        {
          id: 'synthetic-workspace',
          name: 'Personal workspace',
          kind: 'personal',
          role: 'owner',
        },
      ],
      response: new Response(null, { status: 200 }),
    } as never;
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(['me'], {
    id: 'synthetic-user',
    email: 'fixture@example.test',
    email_verified: true,
    mfa_enabled: false,
    mfa_required: false,
    mfa_authenticated: false,
  });
  client.setQueryData(
    ['workspaces', 'synthetic-user'],
    [
      {
        id: 'synthetic-workspace',
        name: 'Personal workspace',
        kind: 'personal',
        role: 'owner',
      },
    ],
  );
  const key = privateKey(
    'synthetic-user',
    'synthetic-workspace',
    'project',
    'synthetic-project',
  );
  client.setQueryData(key, {
    id: 'synthetic-project',
    workspace_id: 'synthetic-workspace',
    name: 'Synthetic project',
    description: 'Previously authorized note',
    version: 1,
    archived: false,
    orphaned: false,
    role: 'editor',
    owner_membership_id: 'synthetic-owner',
    created_at: '2026-10-05T12:00:00Z',
    updated_at: '2026-10-05T12:00:00Z',
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[
          '/projects/synthetic-project?workspace=synthetic-workspace',
        ]}
      >
        <Application />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByLabelText('Description')).toHaveValue(
    'Previously authorized note',
  );
  await client.invalidateQueries({ queryKey: key });
  await waitFor(() => expect(client.getQueryData(key)).toBeUndefined());
  expect(screen.getByRole('alert')).toHaveTextContent('Access unavailable.');
  expect(screen.queryByLabelText('Description')).toBeNull();
  expect(deniedReads).toBe(1);
});
