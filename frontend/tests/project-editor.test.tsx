import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, type Project } from '../app/lib/api';
import { WorkspaceContext } from '../app/lib/context';
import { clearPrivateState, privateKey } from '../app/lib/privacy';
import { ProjectEditor } from '../app/routes/projects';
const project: Project = {
  id: 'synthetic-project',
  workspace_id: 'synthetic-workspace',
  name: 'Synthetic project',
  description: 'Synthetic note',
  version: 2,
  archived: false,
  orphaned: false,
  role: 'editor',
  owner_membership_id: 'synthetic-owner',
  created_at: '2026-10-05T12:00:00Z',
  updated_at: '2026-10-05T12:00:00Z',
};
function show(
  value: Project,
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  return render(
    <QueryClientProvider client={client}>
      <WorkspaceContext.Provider
        value={{
          me: {
            id: 'synthetic-user',
            email: 'fixture@example.test',
            email_verified: true,
            mfa_enabled: false,
            mfa_required: false,
            mfa_authenticated: false,
          },
          workspace: {
            id: 'synthetic-workspace',
            name: 'Synthetic workspace',
            kind: 'personal',
            role: 'owner',
          },
          refresh: async () => {},
          selectWorkspace: async () => {},
          url: (path) => path,
        }}
      >
        <ProjectEditor project={value} />
      </WorkspaceContext.Provider>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.restoreAllMocks());
describe('project edit safety', () => {
  it('retains the user’s unsaved fields after a real-shaped version conflict', async () => {
    vi.spyOn(api, 'PATCH').mockResolvedValue({
      error: { code: 'version_conflict', detail: 'The project has changed.' },
      response: new Response(null, { status: 409 }),
    } as never);
    show(project);
    const user = userEvent.setup();
    const name = screen.getByLabelText('Project name');
    const description = screen.getByLabelText('Description');
    await user.clear(name);
    await user.type(name, 'My unsaved title');
    await user.clear(description);
    await user.type(description, 'My unsaved note');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your unsaved edits are still here',
    );
    expect(name).toHaveValue('My unsaved title');
    expect(description).toHaveValue('My unsaved note');
    expect(
      screen.queryByText('Saved. Your changes are up to date.'),
    ).toBeNull();
  });
  it('keeps a viewer’s fields read only', () => {
    show({ ...project, role: 'viewer' });
    expect(screen.getByLabelText('Project name')).toHaveAttribute('readonly');
    expect(screen.queryByRole('button', { name: 'Save changes' })).toBeNull();
  });
  it('preserves read access while disabling edits for an ownerless project', () => {
    show({ ...project, orphaned: true });
    expect(screen.getByLabelText('Description')).toHaveValue('Synthetic note');
    expect(screen.getByLabelText('Description')).toHaveAttribute('readonly');
    expect(screen.getByRole('status')).toHaveTextContent(
      'owner is no longer active',
    );
  });
  it('does not repopulate private cache when an earlier save completes after sign-out or workspace change', async () => {
    let release: () => void = () => {};
    const delayed = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.spyOn(api, 'PATCH').mockImplementation(async () => {
      await delayed;
      return {
        data: { ...project, version: 3 },
        response: new Response(null, { status: 200 }),
      } as never;
    });
    const client = new QueryClient();
    show(project, client);
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Save changes' }));
    await clearPrivateState(client);
    release();
    await screen.findByRole('button', { name: 'Save changes' });
    expect(
      client.getQueryData(
        privateKey(
          'synthetic-user',
          'synthetic-workspace',
          'project',
          project.id,
        ),
      ),
    ).toBeUndefined();
    expect(
      screen.queryByText('Saved. Your changes are up to date.'),
    ).toBeNull();
  });
});
