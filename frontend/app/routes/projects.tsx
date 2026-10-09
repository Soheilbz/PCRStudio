import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  ArrowRight,
  FolderPlus,
  LockKeyhole,
  Plus,
} from 'lucide-react';
import { api, ApiError, unwrap, type Project } from '../lib/api';
import { useWorkspace } from '../lib/context';
import { privateKey, privateStateEpoch } from '../lib/privacy';
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
export default function Projects() {
  const { me, workspace, url } = useWorkspace();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const key = privateKey(me.id, workspace.id, 'projects', page);
  const projects = useQuery({
    queryKey: key,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/projects/', {
          params: { path: { workspace_id: workspace.id }, query: { page } },
          signal,
        }),
      ),
  });
  async function create() {
    setPending(true);
    setError(undefined);
    try {
      unwrap(
        await api.POST('/api/v1/workspaces/{workspace_id}/projects/', {
          params: { path: { workspace_id: workspace.id } },
          body: { name, description },
        }),
      );
      setName('');
      setDescription('');
      setOpen(false);
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'projects'),
      });
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHeading
        title="Projects"
        subtitle="A private home for your primer-design work."
        action={
          <Modal
            title="New project"
            description="Only you can access this project until you grant access."
            trigger={
              <>
                <Plus size={18} />
                New project
              </>
            }
            open={open}
            onOpenChange={setOpen}
          >
            <form
              onSubmit={(e) => {
                submitted(e);
                void create();
              }}
            >
              <Field label="Project name">
                <input
                  required
                  maxLength={160}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
              <Field
                label="Description"
                hint="Optional. Keep a short note about the project."
              >
                <textarea
                  maxLength={4000}
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </Field>
              <ErrorNotice error={error} />
              <PendingButton className="primary full" pending={pending}>
                Create project
              </PendingButton>
            </form>
          </Modal>
        }
      />
      <div className="workspace-note">
        <LockKeyhole size={18} />
        <span>
          {workspace.kind === 'personal'
            ? 'Your personal workspace'
            : 'Organization membership does not grant project access.'}
        </span>
      </div>
      <ErrorNotice error={projects.error} />
      {projects.error && (
        <button onClick={() => void projects.refetch()}>Try again</button>
      )}
      {projects.isPending ? (
        <Loading text="Loading your projects…" />
      ) : !projects.error && projects.data?.results.length ? (
        <>
          <div className="project-grid">
            {projects.data.results.map((project) => (
              <Link
                key={project.id}
                to={url(`/projects/${project.id}`)}
                className="project-card"
              >
                <div className="row between">
                  <FolderPlus size={24} className="accent" />
                  <span className="badge">
                    {project.archived
                      ? 'Archived'
                      : project.orphaned
                        ? 'Read only · owner unavailable'
                        : project.role}
                  </span>
                </div>
                <h2>{project.name}</h2>
                <p>{project.description || 'No description yet.'}</p>
                <div className="project-foot">
                  <span>
                    Updated{' '}
                    {new Date(project.updated_at).toLocaleDateString('en-US')}
                  </span>
                  <ArrowRight size={18} />
                </div>
              </Link>
            ))}
          </div>
          <div className="pagination" aria-label="Project pages">
            <button
              disabled={!projects.data.previous}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              disabled={!projects.data.next}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </>
      ) : (
        !projects.error &&
        projects.data && (
          <Empty title="Room for your next idea">
            Create your first project to keep your research organized and
            private.
          </Empty>
        )
      )}
    </>
  );
}
export function ProjectDetail() {
  const { id = '' } = useParams();
  const { me, workspace, url, selectWorkspace } = useWorkspace();
  const project = useQuery({
    queryKey: privateKey(me.id, workspace.id, 'project', id),
    queryFn: async ({ signal }) => {
      const result = unwrap(
        await api.GET('/api/v1/projects/{project_id}/', {
          params: { path: { project_id: id } },
          signal,
        }),
      );
      if (result.workspace_id !== workspace.id) {
        await selectWorkspace(result.workspace_id, true);
        throw new Error('Opening the project’s workspace…');
      }
      return result;
    },
  });
  const temporaryFailure =
    project.error instanceof TypeError ||
    (project.error instanceof ApiError && project.error.status >= 500);
  return (
    <>
      <Link className="back-link" to={url('/')}>
        <ArrowLeft size={16} />
        Projects
      </Link>
      <ErrorNotice error={project.error} />
      {project.error && (
        <button onClick={() => void project.refetch()}>Try again</button>
      )}
      {project.isPending ? (
        <Loading text="Loading project…" />
      ) : (
        (!project.error || temporaryFailure) &&
        project.data && (
          <ProjectEditor key={project.data.id} project={project.data} />
        )
      )}
    </>
  );
}
export function ProjectEditor({ project }: { project: Project }) {
  const { me, workspace } = useWorkspace();
  const client = useQueryClient();
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [version, setVersion] = useState(project.version);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const editable =
    !project.orphaned && !project.archived && project.role !== 'viewer';
  const owner = project.role === 'owner' && !project.orphaned;
  async function save(archived?: boolean) {
    const epoch = privateStateEpoch();
    setPending(true);
    setError(undefined);
    setSaved(false);
    try {
      const result = unwrap(
        await api.PATCH('/api/v1/projects/{project_id}/', {
          params: { path: { project_id: project.id } },
          body:
            archived === undefined
              ? { name, description, version }
              : { archived, version },
        }),
      );
      if (epoch !== privateStateEpoch()) return;
      setVersion(result.version);
      client.setQueryData(
        privateKey(me.id, workspace.id, 'project', project.id),
        result,
      );
      await client.invalidateQueries({
        queryKey: privateKey(me.id, workspace.id, 'projects'),
      });
      setSaved(true);
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  async function reload() {
    const epoch = privateStateEpoch();
    setPending(true);
    try {
      const latest = unwrap(
        await api.GET('/api/v1/projects/{project_id}/', {
          params: { path: { project_id: project.id } },
        }),
      );
      if (epoch !== privateStateEpoch()) return;
      setName(latest.name);
      setDescription(latest.description);
      setVersion(latest.version);
      client.setQueryData(
        privateKey(me.id, workspace.id, 'project', project.id),
        latest,
      );
      setError(undefined);
      setSaved(false);
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHeading title={project.name} subtitle="Project details" />
      {project.orphaned && (
        <Notice>
          The project owner is no longer active. You can read this project;
          editing is unavailable until the workspace owner recovers management.
        </Notice>
      )}
      {project.archived && <Notice>This project is archived.</Notice>}
      <section className="card">
        <div className="section-heading">
          <h2>Overview</h2>
          <span className="badge">{project.role}</span>
        </div>
        <form
          onSubmit={(e) => {
            submitted(e);
            void save();
          }}
        >
          <Field label="Project name">
            <input
              required
              maxLength={160}
              value={name}
              readOnly={!editable}
              onChange={(e) => {
                setName(e.target.value);
                setSaved(false);
              }}
            />
          </Field>
          <Field label="Description">
            <textarea
              maxLength={4000}
              rows={6}
              value={description}
              readOnly={!editable}
              onChange={(e) => {
                setDescription(e.target.value);
                setSaved(false);
              }}
            />
          </Field>
          <ErrorNotice error={error} />
          {error instanceof ApiError && error.status === 409 && (
            <button
              type="button"
              onClick={() => void reload()}
              disabled={pending}
            >
              Reload latest and replace my edits
            </button>
          )}
          {saved && <Notice>Saved. Your changes are up to date.</Notice>}
          <div className="row between">
            <small>
              {editable
                ? 'Changes are saved when you choose Save.'
                : project.role === 'viewer'
                  ? 'You have viewer access.'
                  : 'Editing is currently unavailable.'}
            </small>
            {editable && (
              <PendingButton className="primary" pending={pending}>
                Save changes
              </PendingButton>
            )}
          </div>
        </form>
      </section>
      {owner && (
        <>
          <ProjectAccess
            project={{ ...project, version }}
            onVersion={setVersion}
          />
          <section className="card">
            <h2>{project.archived ? 'Restore project' : 'Archive project'}</h2>
            <p>
              {project.archived
                ? 'Bring this project back to active work.'
                : 'Keep its record and access while pausing edits.'}
            </p>
            <PendingButton
              pending={pending}
              onClick={() => void save(!project.archived)}
            >
              {project.archived ? 'Restore project' : 'Archive project'}
            </PendingButton>
          </section>
        </>
      )}
    </>
  );
}
function ProjectAccess({
  project,
  onVersion,
}: {
  project: Project;
  onVersion: (version: number) => void;
}) {
  const { me, workspace } = useWorkspace();
  const client = useQueryClient();
  const [member, setMember] = useState('');
  const [role, setRole] = useState<'viewer' | 'editor' | 'owner'>('viewer');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [page, setPage] = useState(1);
  const accessKey = privateKey(me.id, workspace.id, 'access', project.id);
  const access = useQuery({
    queryKey: accessKey,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/access/', {
          params: { path: { project_id: project.id } },
          signal,
        }),
      ),
  });
  const members = useQuery({
    queryKey: privateKey(me.id, workspace.id, 'members', page),
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/members/', {
          params: { path: { workspace_id: workspace.id }, query: { page } },
          signal,
        }),
      ),
  });
  async function update(membership_id: string, remove = false) {
    const epoch = privateStateEpoch();
    setPending(true);
    setError(undefined);
    try {
      if (remove)
        unwrap(
          await api.DELETE(
            '/api/v1/projects/{project_id}/access/{membership_id}/',
            {
              params: {
                path: { project_id: project.id, membership_id },
                query: { version: project.version },
              },
            },
          ),
        );
      else
        unwrap(
          await api.POST('/api/v1/projects/{project_id}/access/', {
            params: { path: { project_id: project.id } },
            body: { membership_id, role, version: project.version },
          }),
        );
      if (epoch !== privateStateEpoch()) return;
      const latest = unwrap(
        await api.GET('/api/v1/projects/{project_id}/', {
          params: { path: { project_id: project.id } },
        }),
      );
      if (epoch !== privateStateEpoch()) return;
      onVersion(latest.version);
      client.setQueryData(
        privateKey(me.id, workspace.id, 'project', project.id),
        latest,
      );
      await client.invalidateQueries({ queryKey: accessKey });
      setMember('');
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="card">
      <h2>Project Access</h2>
      <p>
        Grant access separately from workspace membership. Transferring
        ownership replaces your owner role with editor access.
      </p>
      <ErrorNotice error={access.error || members.error || error} />
      {access.isPending ? (
        <Loading text="Loading project access…" />
      ) : (
        <div
          className="table-scroll"
          role="region"
          aria-label="Project access"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Member</th>
                <th>Project role</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {access.data?.map((grant) => (
                <tr key={grant.membership_id}>
                  <td>{grant.email}</td>
                  <td>{grant.role}</td>
                  <td>
                    {grant.role !== 'owner' && (
                      <button
                        disabled={pending}
                        onClick={() => void update(grant.membership_id, true)}
                      >
                        Remove access
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form
        className="grant-form"
        onSubmit={(e) => {
          submitted(e);
          void update(member);
        }}
      >
        <Field label="Workspace member">
          <select
            required
            value={member}
            onChange={(e) => setMember(e.target.value)}
          >
            <option value="">Choose an active member</option>
            {members.data?.results
              .filter((m) => m.active && m.id !== project.owner_membership_id)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.email}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Project role">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as typeof role)}
          >
            <option value="viewer">Viewer · read</option>
            <option value="editor">Editor · read and edit</option>
            <option value="owner">Owner · transfer management</option>
          </select>
        </Field>
        <PendingButton className="primary" pending={pending} disabled={!member}>
          {role === 'owner' ? 'Transfer ownership' : 'Grant access'}
        </PendingButton>
      </form>
      {members.data && (members.data.previous || members.data.next) && (
        <div className="pagination">
          <button
            disabled={!members.data.previous}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous members
          </button>
          <span>Page {page}</span>
          <button
            disabled={!members.data.next}
            onClick={() => setPage((p) => p + 1)}
          >
            More members
          </button>
        </div>
      )}
    </section>
  );
}
