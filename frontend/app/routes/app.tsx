import { useCallback, useEffect, useState } from 'react';
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router';
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Dialog } from '@base-ui/react/dialog';
import {
  Folder,
  Settings,
  UserRound,
  Users,
  Menu,
  X,
  LogOut,
} from 'lucide-react';
import { api, ApiError, bootstrapCsrf, unwrap } from '../lib/api';
import { authRequest } from '../lib/auth';
import { clearDeniedContent, clearPrivateState } from '../lib/privacy';
import { ThemeProvider, ThemeToggle } from '../lib/theme';
import { AccountContext, WorkspaceContext } from '../lib/context';
import { ErrorNotice, Loading, Notice } from '../lib/ui';
import AuthPage from './auth';
import Projects, { ProjectDetail } from './projects';
import Account from './account';
import WorkspaceSettings, { Members, InvitationAcceptance } from './workspace';
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 15_000, refetchOnWindowFocus: true },
    mutations: { retry: false },
  },
});
async function readIdentity({ signal }: { signal?: AbortSignal }) {
  await bootstrapCsrf(signal);
  return unwrap(await api.GET('/api/v1/me/', { signal }));
}

export function Application() {
  const queryClient = useQueryClient();
  const [, forceRefresh] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const [returnTo, setReturnTo] = useState(
    location.pathname === '/invitations/accept'
      ? location.pathname + location.search
      : '',
  );
  const [workspaceId, setWorkspaceId] = useState(
    new URLSearchParams(location.search).get('workspace') ?? '',
  );
  const [switching, setSwitching] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [logoutError, setLogoutError] = useState<unknown>();
  const me = useQuery({
    queryKey: ['me'],
    queryFn: readIdentity,
    refetchInterval: 30_000,
  });
  const workspaces = useQuery({
    queryKey: ['workspaces', me.data?.id],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET('/api/v1/workspaces/', { signal })),
    enabled: !!me.data && (!me.data.mfa_required || me.data.mfa_authenticated),
  });
  const workspace =
    workspaces.data?.find((w) => w.id === workspaceId) ?? workspaces.data?.[0];
  const identityExpired =
    me.error instanceof ApiError && me.error.status === 401;
  const temporaryIdentityFailure =
    me.error instanceof TypeError ||
    (me.error instanceof ApiError && me.error.status >= 500);
  useEffect(() => {
    if (identityExpired) {
      void clearPrivateState(queryClient).then(() =>
        queryClient.setQueryData(['me'], null),
      );
      setWorkspaceId('');
    }
  }, [identityExpired, queryClient]);
  useEffect(() => {
    if (me.data?.mfa_required && !me.data.mfa_authenticated) {
      void clearDeniedContent(queryClient);
      void queryClient.cancelQueries({ queryKey: ['workspaces'] }).then(() => {
        for (const query of queryClient
          .getQueryCache()
          .findAll({ queryKey: ['workspaces'] }))
          query.setState({ data: undefined, dataUpdatedAt: 0 });
      });
    }
  }, [me.data?.mfa_required, me.data?.mfa_authenticated, queryClient]);
  const { refetch: refetchMe } = me;
  const { refetch: refetchWorkspaces } = workspaces;
  useEffect(() => {
    const timers = new Set<ReturnType<typeof setTimeout>>();
    const changed = () => {
      const timer = setTimeout(() => {
        timers.delete(timer);
        void clearDeniedContent(queryClient).then(async () => {
          const result = await refetchMe();
          if (
            result.data &&
            (!result.data.mfa_required || result.data.mfa_authenticated)
          )
            void refetchWorkspaces();
        });
      }, 0);
      timers.add(timer);
    };
    window.addEventListener('pcrstudio-access-changed', changed);
    return () => {
      window.removeEventListener('pcrstudio-access-changed', changed);
      for (const timer of timers) clearTimeout(timer);
    };
  }, [refetchMe, refetchWorkspaces, queryClient]);
  async function refresh() {
    setReturnTo('');
    await clearPrivateState(queryClient);
    setWorkspaceId('');
    try {
      const identity = await queryClient.fetchQuery({
        queryKey: ['me'],
        queryFn: readIdentity,
        staleTime: 0,
      });
      if (!identity.mfa_required || identity.mfa_authenticated)
        await queryClient.fetchQuery({
          queryKey: ['workspaces', identity.id],
          queryFn: async ({ signal }) =>
            unwrap(await api.GET('/api/v1/workspaces/', { signal })),
          staleTime: 0,
        });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401)
        queryClient.setQueryData(['me'], null);
      else throw error;
    } finally {
      forceRefresh((value) => value + 1);
    }
  }
  const selectWorkspace = useCallback(
    async (id: string, preservePath = false) => {
      if (id === workspace?.id) return;
      setSwitching(true);
      const identity = me.data;
      const summaries = workspaces.data;
      await clearPrivateState(queryClient);
      queryClient.setQueryData(['me'], identity);
      queryClient.setQueryData(['workspaces', identity?.id], summaries);
      setWorkspaceId(id);
      const search = new URLSearchParams(preservePath ? location.search : '');
      search.set('workspace', id);
      const destination = `${preservePath ? location.pathname : '/'}?${search.toString()}`;
      if (destination !== location.pathname + location.search)
        navigate(destination);
      setDrawer(false);
      setSwitching(false);
    },
    [
      workspace?.id,
      me.data,
      workspaces.data,
      location.pathname,
      location.search,
      navigate,
      queryClient,
    ],
  );
  useEffect(() => {
    const requested = new URLSearchParams(location.search).get('workspace');
    if (
      !switching &&
      requested &&
      requested !== workspace?.id &&
      workspaces.data?.some((item) => item.id === requested)
    )
      void selectWorkspace(requested, true);
  }, [
    location.search,
    workspace?.id,
    workspaces.data,
    switching,
    selectWorkspace,
  ]);
  async function signOut() {
    try {
      await authRequest('auth/session', 'DELETE', undefined, [401]);
      await clearPrivateState(queryClient);
      setWorkspaceId('');
      queryClient.setQueryData(['me'], null);
      navigate('/login');
    } catch (e) {
      setLogoutError(e);
    }
  }
  const url = (path: string) =>
    `${path}${path.includes('?') ? '&' : '?'}workspace=${workspace?.id ?? ''}`;
  const nav = (
    <>
      <div className="sidebar-top">
        <Link to={url('/')} className="brand" onClick={() => setDrawer(false)}>
          PCR<span>Studio</span>
        </Link>
        <p className="sidebar-tagline">Space for careful work.</p>
      </div>
      <nav aria-label="Main navigation">
        <NavLink to={url('/')} end onClick={() => setDrawer(false)}>
          <Folder size={20} />
          Projects
        </NavLink>
        {workspace?.kind === 'organization' && (
          <NavLink to={url('/members')} onClick={() => setDrawer(false)}>
            <Users size={20} />
            Members
          </NavLink>
        )}
      </nav>
      <div className="sidebar-bottom">
        <NavLink to={url('/account')} onClick={() => setDrawer(false)}>
          <UserRound size={20} />
          Account
        </NavLink>
        <NavLink to={url('/workspace')} onClick={() => setDrawer(false)}>
          <Settings size={20} />
          Workspace settings
        </NavLink>
        <button className="nav-button" onClick={() => void signOut()}>
          <LogOut size={20} />
          Sign out
        </button>
        <small>Confidential by default</small>
      </div>
    </>
  );
  if (me.isPending) return <Loading text="Opening your workspace…" />;
  if (me.error && !identityExpired && (!me.data || !temporaryIdentityFailure))
    return (
      <main className="auth-page">
        <section className="card">
          <h1>Connection interrupted</h1>
          <ErrorNotice error={me.error} />
          <button onClick={() => void me.refetch()}>Try again</button>
        </section>
      </main>
    );
  if (!me.data || identityExpired)
    return (
      <AuthPage key={location.pathname} refresh={refresh} returnTo={returnTo} />
    );
  if (
    location.pathname.startsWith('/account/verify-email/') ||
    location.pathname.startsWith('/account/password/reset/key/') ||
    ['/verify-email', '/reset-password', '/reset-password/confirm'].includes(
      location.pathname,
    )
  )
    return (
      <AuthPage key={location.pathname} refresh={refresh} returnTo={returnTo} />
    );
  if (
    (me.data.mfa_required && !me.data.mfa_authenticated) ||
    (location.pathname === '/account' && !workspace)
  )
    return (
      <AccountContext.Provider value={{ me: me.data, refresh }}>
        <header className="topbar">
          <Link to="/" className="brand">
            PCR<span>Studio</span>
          </Link>
          <ThemeToggle />
        </header>
        <main id="main-content" className="main-content">
          {me.data.mfa_required && !me.data.mfa_authenticated && (
            <Notice>
              {me.data.mfa_enabled
                ? 'Confirm your identity with your authenticator below to open your workspaces.'
                : 'Your role requires two-factor authentication. Set up an authenticator below to open your workspaces.'}
            </Notice>
          )}
          <ErrorNotice error={logoutError || me.error} />
          <Account />
          <div className="row wrap">
            {(!me.data.mfa_required || me.data.mfa_authenticated) && (
              <Link className="button" to="/">
                Projects
              </Link>
            )}
            <button onClick={() => void signOut()}>
              <LogOut size={20} />
              Sign out
            </button>
          </div>
        </main>
      </AccountContext.Provider>
    );
  if (!workspace)
    return (
      <main className="auth-page">
        <ErrorNotice error={workspaces.error} />
        {workspaces.isPending ? (
          <Loading text="Loading workspaces…" />
        ) : (
          <button onClick={() => void workspaces.refetch()}>
            Reload workspaces
          </button>
        )}
      </main>
    );
  return (
    <WorkspaceContext.Provider
      value={{ me: me.data, workspace, refresh, selectWorkspace, url }}
    >
      <div className="app-shell">
        <aside className="sidebar">{nav}</aside>
        <div className="app-body">
          <header className="topbar">
            <Dialog.Root open={drawer} onOpenChange={setDrawer}>
              <Dialog.Trigger
                className="icon-button mobile-menu"
                aria-label="Open navigation"
              >
                <Menu size={22} />
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Backdrop className="backdrop" />
                <Dialog.Popup className="drawer">
                  <div className="row between">
                    <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                    <Dialog.Close
                      className="icon-button"
                      aria-label="Close navigation"
                    >
                      <X size={20} />
                    </Dialog.Close>
                  </div>
                  {nav}
                </Dialog.Popup>
              </Dialog.Portal>
            </Dialog.Root>
            <label className="workspace-selector">
              <span className="sr-only">Workspace</span>
              <select
                aria-label="Workspace"
                value={workspace.id}
                onChange={(e) => void selectWorkspace(e.target.value)}
                disabled={switching}
              >
                {workspaces.data?.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ·{' '}
                    {w.kind === 'personal' ? 'Personal' : 'Organization'}
                  </option>
                ))}
              </select>
            </label>
            <ThemeToggle />
          </header>
          <main id="main-content" className="main-content">
            <ErrorNotice error={logoutError || me.error} />
            {switching ? (
              <Loading text="Switching workspace…" />
            ) : (
              <div key={`${me.data.id}:${workspace.id}`}>
                <Routes>
                  <Route index element={<Projects />} />
                  <Route path="projects/:id" element={<ProjectDetail />} />
                  <Route
                    path="account"
                    element={
                      <AccountContext.Provider value={{ me: me.data, refresh }}>
                        <Account />
                      </AccountContext.Provider>
                    }
                  />
                  <Route path="members" element={<Members />} />
                  <Route path="workspace" element={<WorkspaceSettings />} />
                  <Route
                    path="invitations/accept"
                    element={<InvitationAcceptance />}
                  />
                  <Route
                    path="*"
                    element={
                      <section className="card">
                        <h1>Page unavailable</h1>
                        <Link to="/">Return to projects</Link>
                      </section>
                    }
                  />
                </Routes>
              </div>
            )}
          </main>
        </div>
      </div>
    </WorkspaceContext.Provider>
  );
}
export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <Application />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
