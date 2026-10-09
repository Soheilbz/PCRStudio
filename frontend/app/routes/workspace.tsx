import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../lib/api';
import { useWorkspace } from '../lib/context';
import { privateKey } from '../lib/privacy';
import {
  Empty,
  ErrorNotice,
  Field,
  Loading,
  Modal,
  Notice,
  PageHeading,
  PendingButton,
  submitted,
} from '../lib/ui';
export default function WorkspaceSettings() {
  const { me, workspace, refresh, url } = useWorkspace();
  const [name, setName] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  async function create() {
    setPending(true);
    setError(undefined);
    try {
      unwrap(await api.POST('/api/v1/workspaces/', { body: { name } }));
      setName('');
      await refresh();
      setNotice(
        'Organization created. Choose it in the workspace selector to continue.',
      );
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHeading
        title="Workspace settings"
        subtitle="Workspace identity and organization administration."
      />
      <section className="card">
        <h2>{workspace.name}</h2>
        <dl className="details">
          <dt>Workspace type</dt>
          <dd>{workspace.kind === 'personal' ? 'Personal' : 'Organization'}</dd>
          <dt>Your workspace role</dt>
          <dd>{workspace.role}</dd>
        </dl>
        <p>
          {workspace.kind === 'personal'
            ? 'Your personal workspace stays with your account.'
            : 'Membership administration and project access are separate.'}
        </p>
        {workspace.kind === 'organization' && (
          <Link className="button" to={url('/members')}>
            Manage members
          </Link>
        )}
      </section>
      <section className="card">
        <h2>Create an organization</h2>
        <p>
          A shared workspace with explicit membership and private project
          access.
        </p>
        {!me.mfa_enabled ? (
          <Notice>
            Enable two-factor authentication in{' '}
            <Link to={url('/account')}>Account</Link> before creating an
            organization.
          </Notice>
        ) : !me.mfa_authenticated ? (
          <Notice>
            Confirm your identity with your authenticator in{' '}
            <Link to={url('/account')}>Account</Link> before creating an
            organization.
          </Notice>
        ) : (
          <form
            onSubmit={(e) => {
              submitted(e);
              void create();
            }}
          >
            <Field label="Organization name">
              <input
                required
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <ErrorNotice error={error} />
            {notice && <Notice>{notice}</Notice>}
            <PendingButton className="primary" pending={pending}>
              Create organization
            </PendingButton>
          </form>
        )}
      </section>
      {workspace.kind === 'organization' && workspace.role === 'owner' && (
        <Recovery />
      )}
    </>
  );
}
export function Members() {
  const { me, workspace, refresh, url } = useWorkspace();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [invitePage, setInvitePage] = useState(1);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'member' | 'owner'>('member');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  const [removing, setRemoving] = useState<string | null>(null);
  const key = privateKey(me.id, workspace.id, 'members', page);
  const members = useQuery({
    queryKey: key,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/members/', {
          params: { path: { workspace_id: workspace.id }, query: { page } },
          signal,
        }),
      ),
    enabled: workspace.kind === 'organization',
  });
  const invitations = useQuery({
    queryKey: privateKey(me.id, workspace.id, 'invitations', invitePage),
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/invitations/', {
          params: {
            path: { workspace_id: workspace.id },
            query: { page: invitePage },
          },
          signal,
        }),
      ),
    enabled:
      workspace.kind === 'organization' &&
      workspace.role === 'owner' &&
      me.mfa_enabled,
  });
  const admin = workspace.role === 'owner' && me.mfa_enabled;
  async function invite() {
    setPending(true);
    setError(undefined);
    setNotice('');
    try {
      unwrap(
        await api.POST('/api/v1/workspaces/{workspace_id}/invitations/', {
          params: { path: { workspace_id: workspace.id } },
          body: { email, role },
        }),
      );
      setEmail('');
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'invitations'),
      });
      setNotice(
        'Invitation created. Check the invited email for its link. It expires in seven days and grants workspace membership only.',
      );
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  async function revoke() {
    if (!removing) return;
    setPending(true);
    setError(undefined);
    try {
      unwrap(
        await api.DELETE(
          '/api/v1/workspaces/{workspace_id}/members/{membership_id}/',
          {
            params: {
              path: { workspace_id: workspace.id, membership_id: removing },
            },
          },
        ),
      );
      setRemoving(null);
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'members'),
      });
      setNotice('Membership revoked. Project access has ended immediately.');
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  async function changeRole(
    membership_id: string,
    nextRole: 'owner' | 'member',
  ) {
    setPending(true);
    setError(undefined);
    try {
      unwrap(
        await api.PATCH(
          '/api/v1/workspaces/{workspace_id}/members/{membership_id}/',
          {
            params: { path: { workspace_id: workspace.id, membership_id } },
            body: { role: nextRole },
          },
        ),
      );
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'members'),
      });
      await client.invalidateQueries({ queryKey: ['workspaces', me.id] });
      setNotice('Workspace role updated.');
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  async function revokeInvitation(invitation_id: string) {
    setPending(true);
    setError(undefined);
    try {
      unwrap(
        await api.DELETE(
          '/api/v1/workspaces/{workspace_id}/invitations/{invitation_id}/',
          { params: { path: { workspace_id: workspace.id, invitation_id } } },
        ),
      );
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'invitations'),
      });
      setNotice('Invitation revoked.');
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  async function leave() {
    setPending(true);
    setError(undefined);
    try {
      unwrap(
        await api.POST('/api/v1/workspaces/{workspace_id}/leave/', {
          params: { path: { workspace_id: workspace.id } },
        }),
      );
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  if (workspace.kind !== 'organization')
    return (
      <Empty title="A personal workspace">
        Organization membership is managed in an organization workspace.
      </Empty>
    );
  return (
    <>
      <PageHeading
        title="Members"
        subtitle="Workspace membership. Project Access is managed inside each project."
      />
      {workspace.role === 'owner' && !me.mfa_enabled && (
        <Notice>
          Enable two-factor authentication in{' '}
          <Link to={url('/account')}>Account</Link> to administer this
          workspace.
        </Notice>
      )}
      <ErrorNotice error={members.error || error} />
      {notice && <Notice>{notice}</Notice>}
      <section className="card">
        <h2>Workspace members</h2>
        {members.isPending ? (
          <Loading text="Loading members…" />
        ) : (
          <div
            className="table-scroll"
            role="region"
            aria-label="Workspace members"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Workspace role</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {members.data?.results.map((member) => (
                  <tr key={member.id}>
                    <td>
                      {member.email}
                      {member.email === me.email ? ' · you' : ''}
                    </td>
                    <td>{member.role}</td>
                    <td>{member.active ? 'Active' : 'Revoked'}</td>
                    <td>
                      {admin && member.active && (
                        <div className="row wrap">
                          <button
                            disabled={pending}
                            onClick={() =>
                              void changeRole(
                                member.id,
                                member.role === 'owner' ? 'member' : 'owner',
                              )
                            }
                          >
                            {member.role === 'owner'
                              ? 'Change to member'
                              : 'Make workspace owner'}
                          </button>
                          {member.email !== me.email && (
                            <button
                              disabled={pending}
                              onClick={() => setRemoving(member.id)}
                            >
                              Revoke membership
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {members.data && (
          <div className="pagination">
            <button
              disabled={!members.data.previous}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              disabled={!members.data.next}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </section>
      {admin && (
        <>
          <section className="card">
            <h2>Invite a colleague</h2>
            <p>
              The invitation is single-use and bound to the verified email
              address. Membership alone grants no project content.
            </p>
            <form
              onSubmit={(e) => {
                submitted(e);
                void invite();
              }}
            >
              <Field label="Email address">
                <input
                  type="email"
                  required
                  autoComplete="off"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              <Field label="Workspace role">
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as typeof role)}
                >
                  <option value="member">Member</option>
                  <option value="owner">Owner · administer membership</option>
                </select>
              </Field>
              <PendingButton className="primary" pending={pending}>
                Send invitation
              </PendingButton>
            </form>
          </section>
          <section className="card">
            <h2>Invitations</h2>
            <ErrorNotice error={invitations.error} />
            {invitations.isPending ? (
              <Loading text="Loading invitations…" />
            ) : invitations.data?.results.length ? (
              <ul className="session-list">
                {invitations.data.results.map((invitation) => (
                  <li key={invitation.id}>
                    <div>
                      <strong>{invitation.email}</strong>
                      <p>
                        {invitation.role} · expires{' '}
                        {new Date(invitation.expires_at).toLocaleDateString(
                          'en-US',
                        )}
                      </p>
                    </div>
                    <PendingButton
                      pending={pending}
                      onClick={() => void revokeInvitation(invitation.id)}
                    >
                      Revoke invitation
                    </PendingButton>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No pending invitations.</p>
            )}
            {invitations.data && (
              <div className="pagination">
                <button
                  disabled={!invitations.data.previous}
                  onClick={() => setInvitePage((p) => p - 1)}
                >
                  Previous invitations
                </button>
                <span>Page {invitePage}</span>
                <button
                  disabled={!invitations.data.next}
                  onClick={() => setInvitePage((p) => p + 1)}
                >
                  More invitations
                </button>
              </div>
            )}
          </section>
        </>
      )}
      <section className="card">
        <h2>Leave workspace</h2>
        <p>
          Hand over projects you own before leaving. A final workspace owner
          must arrange a new owner first.
        </p>
        <PendingButton pending={pending} onClick={() => void leave()}>
          Leave workspace
        </PendingButton>
      </section>
      <Modal
        title="Revoke membership"
        description="This immediately ends the member’s project access. Projects are preserved; projects they own become read only until management is recovered."
        open={!!removing}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
      >
        <ErrorNotice error={error} />
        <PendingButton
          className="danger full"
          pending={pending}
          onClick={() => void revoke()}
        >
          Revoke membership now
        </PendingButton>
      </Modal>
    </>
  );
}
function Recovery() {
  const { me, workspace, url } = useWorkspace();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [memberPage, setMemberPage] = useState(1);
  const [selected, setSelected] = useState('');
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState<
    'owner_removed' | 'owner_suspended' | 'security_revocation'
  >('owner_removed');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  const key = privateKey(me.id, workspace.id, 'orphans', page);
  const orphans = useQuery({
    queryKey: key,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/orphaned-projects/', {
          params: { path: { workspace_id: workspace.id }, query: { page } },
          signal,
        }),
      ),
    enabled: me.mfa_enabled,
  });
  const members = useQuery({
    queryKey: privateKey(me.id, workspace.id, 'members', memberPage),
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/members/', {
          params: {
            path: { workspace_id: workspace.id },
            query: { page: memberPage },
          },
          signal,
        }),
      ),
    enabled: me.mfa_enabled,
  });
  async function recover() {
    const project = orphans.data?.results.find((p) => p.id === selected);
    if (!project) return;
    setPending(true);
    setError(undefined);
    setNotice('');
    try {
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/recover/', {
          params: { path: { project_id: project.id } },
          body: { membership_id: target, reason, version: project.version },
        }),
      );
      setSelected('');
      setTarget('');
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'orphans'),
      });
      setNotice(
        'Project management recovered. The operation is audited. Your own project access has not changed.',
      );
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="card">
      <h2>Recover project management</h2>
      <p>
        Assign an active member to an ownerless project. This does not grant you
        content access.{' '}
        <Link to={url('/account')}>Confirm your identity in Account</Link>{' '}
        before proceeding.
      </p>
      <ErrorNotice error={orphans.error || members.error || error} />
      {notice && <Notice>{notice}</Notice>}
      {!me.mfa_enabled ? (
        <p>Two-factor authentication is required.</p>
      ) : orphans.isPending ? (
        <Loading text="Checking for ownerless projects…" />
      ) : orphans.data?.results.length ? (
        <>
          <form
            onSubmit={(e) => {
              submitted(e);
              void recover();
            }}
          >
            <Field label="Ownerless project">
              <select
                required
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">Choose a project identifier</option>
                {orphans.data.results.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.id}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="New project owner">
              <select
                required
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">Choose an active member</option>
                {members.data?.results
                  .filter((m) => m.active)
                  .map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.email}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Reason">
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value as typeof reason)}
              >
                <option value="owner_removed">
                  Previous owner’s membership was removed
                </option>
                <option value="owner_suspended">
                  Previous owner’s account was suspended
                </option>
                <option value="security_revocation">
                  Access revoked for account security
                </option>
              </select>
            </Field>
            <PendingButton
              className="primary"
              pending={pending}
              disabled={!target || !selected}
            >
              Recover management
            </PendingButton>
          </form>
          <div className="pagination">
            <button
              disabled={!orphans.data.previous}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous projects
            </button>
            <span>Page {page}</span>
            <button
              disabled={!orphans.data.next}
              onClick={() => setPage((p) => p + 1)}
            >
              More projects
            </button>
          </div>
          {members.data && (members.data.previous || members.data.next) && (
            <div className="pagination">
              <button
                disabled={!members.data.previous}
                onClick={() => setMemberPage((p) => p - 1)}
              >
                Previous members
              </button>
              <span>Member page {memberPage}</span>
              <button
                disabled={!members.data.next}
                onClick={() => setMemberPage((p) => p + 1)}
              >
                More members
              </button>
            </div>
          )}
        </>
      ) : (
        <p>No ownerless projects need recovery.</p>
      )}
    </section>
  );
}
export function InvitationAcceptance() {
  const { refresh } = useWorkspace();
  const location = useLocation();
  const [key, setKey] = useState(
    new URLSearchParams(location.search).get('key') ?? '',
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  async function accept() {
    setPending(true);
    setError(undefined);
    try {
      unwrap(await api.POST('/api/v1/invitations/accept/', { body: { key } }));
      await refresh();
      setKey('');
      setNotice(
        'Membership accepted. Choose the organization in the workspace selector. Project access is granted separately.',
      );
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHeading
        title="Accept invitation"
        subtitle="Join an organization with your verified account."
      />
      <section className="card">
        <form
          onSubmit={(e) => {
            submitted(e);
            void accept();
          }}
        >
          <Field label="Invitation key">
            <input
              required
              autoComplete="off"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
          </Field>
          <ErrorNotice error={error} />
          {notice && <Notice>{notice}</Notice>}
          <PendingButton className="primary" pending={pending}>
            Accept invitation
          </PendingButton>
        </form>
      </section>
    </>
  );
}
