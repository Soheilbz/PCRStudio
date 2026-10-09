import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import { authRequest, recoveryData, sessionData } from '../lib/auth';
import { useAccount } from '../lib/context';
import { privateKey } from '../lib/privacy';
import {
  ErrorNotice,
  Field,
  Loading,
  Notice,
  PageHeading,
  PendingButton,
  submitted,
} from '../lib/ui';
export default function Account() {
  const { me, refresh } = useAccount();
  const client = useQueryClient();
  const [password, setPassword] = useState('');
  const [reauthCode, setReauthCode] = useState('');
  const [code, setCode] = useState('');
  const [secret, setSecret] = useState('');
  const [uri, setUri] = useState('');
  const [recovery, setRecovery] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  const sessionsKey = privateKey(me.id, 'account', 'sessions');
  const sessions = useQuery({
    queryKey: sessionsKey,
    queryFn: async ({ signal }) =>
      sessionData(
        await authRequest('auth/sessions', 'GET', undefined, [], signal),
      ),
  });
  async function run(task: () => Promise<void>) {
    setPending(true);
    setError(undefined);
    setNotice('');
    try {
      await task();
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  async function setup() {
    const result = await authRequest(
      'account/authenticators/totp',
      'GET',
      undefined,
      [404],
    );
    if (result.status === 404) {
      setSecret(result.meta?.secret ?? '');
      setUri(result.meta?.totp_url ?? '');
    } else {
      setNotice('An authenticator is already enabled.');
      await client.invalidateQueries({ queryKey: ['me'] });
    }
  }
  async function activate() {
    const enrollmentCode = code;
    await authRequest('account/authenticators/totp', 'POST', {
      code: enrollmentCode,
    });
    setSecret('');
    setUri('');
    setCode('');
    try {
      await authRequest('auth/2fa/reauthenticate', 'POST', {
        code: enrollmentCode,
      });
      setRecovery(
        recoveryData(
          await authRequest('account/authenticators/recovery-codes'),
        ),
      );
      setNotice(
        'Two-factor authentication is enabled. Save your recovery codes in a secure place.',
      );
    } finally {
      // Enrollment is already committed even if confirmation/code retrieval
      // fails. Refresh so the user can continue via the authenticator form.
      await client.invalidateQueries({ queryKey: ['me'] });
    }
  }
  async function recent() {
    await authRequest(
      me.mfa_enabled ? 'auth/2fa/reauthenticate' : 'auth/reauthenticate',
      'POST',
      me.mfa_enabled ? { code: reauthCode } : { password },
    );
    setPassword('');
    setReauthCode('');
    await client.invalidateQueries({ queryKey: ['me'] });
    setNotice('Identity confirmed. You can continue your protected action.');
  }
  async function endSession(id: number, current: boolean) {
    await authRequest('auth/sessions', 'DELETE', { sessions: [id] }, [401]);
    if (current) await refresh();
    else await client.invalidateQueries({ queryKey: sessionsKey });
  }
  return (
    <>
      <PageHeading
        title="Account"
        subtitle="Your identity, security and active sessions."
      />
      <section className="card">
        <h2>Your account</h2>
        <div className="row between wrap">
          <div>
            <strong>{me.email}</strong>
            <p>
              {me.email_verified
                ? 'Email verified'
                : 'Email verification required'}
            </p>
          </div>
          <span className="badge">
            <ShieldCheck size={16} />
            Verified account
          </span>
        </div>
      </section>
      <section className="card">
        <h2>Two-factor authentication</h2>
        <p>
          {me.mfa_enabled
            ? 'Your authenticator adds a second check when you sign in.'
            : 'Add an authenticator app to protect your account.'}
        </p>
        {me.mfa_required && !me.mfa_enabled && (
          <Notice>
            Organization owners must enable two-factor authentication before
            workspace administration.
          </Notice>
        )}
        {me.mfa_enabled && !me.mfa_authenticated && (
          <Notice>
            Confirm your identity below with your authenticator before protected
            workspace actions.
          </Notice>
        )}
        <ErrorNotice error={error} />
        {notice && <Notice>{notice}</Notice>}
        {!me.mfa_enabled && !secret && (
          <PendingButton
            className="primary"
            pending={pending}
            onClick={() => void run(setup)}
          >
            Set up authenticator
          </PendingButton>
        )}
        {secret && (
          <form
            onSubmit={(e) => {
              submitted(e);
              void run(activate);
            }}
          >
            <p>
              Add PCRStudio to your authenticator app using this setup key.
              Enter the current code to finish.
            </p>
            <Field label="Setup key" hint="Treat this key like a password.">
              <input readOnly value={secret} autoComplete="off" />
            </Field>
            {uri && (
              <details>
                <summary>Authenticator setup URI</summary>
                <code className="secret-uri">{uri}</code>
              </details>
            )}
            <Field label="Six-digit authenticator code">
              <input
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </Field>
            <PendingButton className="primary" pending={pending}>
              Enable two-factor authentication
            </PendingButton>
          </form>
        )}
        {me.mfa_enabled && (
          <div className="row wrap">
            <PendingButton
              pending={pending}
              onClick={() =>
                void run(async () => {
                  setRecovery(
                    recoveryData(
                      await authRequest(
                        'account/authenticators/recovery-codes',
                      ),
                    ),
                  );
                })
              }
            >
              View recovery codes
            </PendingButton>
            <PendingButton
              pending={pending}
              onClick={() =>
                void run(async () => {
                  await authRequest(
                    'account/authenticators/recovery-codes',
                    'POST',
                  );
                  setRecovery(
                    recoveryData(
                      await authRequest(
                        'account/authenticators/recovery-codes',
                      ),
                    ),
                  );
                  setNotice(
                    'New codes replace all previous codes. Save these securely.',
                  );
                })
              }
            >
              Regenerate recovery codes
            </PendingButton>
            {!me.mfa_required && (
              <PendingButton
                pending={pending}
                onClick={() =>
                  void run(async () => {
                    await authRequest('account/authenticators/totp', 'DELETE');
                    setRecovery([]);
                    await client.invalidateQueries({ queryKey: ['me'] });
                    setNotice('Two-factor authentication disabled.');
                  })
                }
              >
                Disable authenticator
              </PendingButton>
            )}
          </div>
        )}
        {!!recovery.length && (
          <div className="recovery-box">
            <h3>Recovery codes</h3>
            <p>
              Each code works once. Store them securely outside this browser.
            </p>
            <pre aria-label="Unused recovery codes">{recovery.join('\n')}</pre>
            <button onClick={() => setRecovery([])}>Hide recovery codes</button>
          </div>
        )}
      </section>
      <section className="card">
        <h2>Confirm your identity</h2>
        <p>
          Protected changes, including ownership recovery, require a recent
          identity check.
        </p>
        <form
          onSubmit={(e) => {
            submitted(e);
            void run(recent);
          }}
        >
          <Field
            label={
              me.mfa_enabled ? 'Authenticator or recovery code' : 'Password'
            }
          >
            {me.mfa_enabled ? (
              <input
                required
                autoComplete="one-time-code"
                value={reauthCode}
                onChange={(e) => setReauthCode(e.target.value)}
              />
            ) : (
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <PendingButton
            pending={pending}
            disabled={me.mfa_required && !me.mfa_enabled}
          >
            Confirm identity
          </PendingButton>
        </form>
      </section>
      <section className="card">
        <h2>Active sessions</h2>
        <p>End sessions you no longer recognize.</p>
        <ErrorNotice error={sessions.error} />
        {sessions.isPending ? (
          <Loading text="Loading sessions…" />
        ) : (
          <ul className="session-list">
            {sessions.data?.map((session) => (
              <li key={session.id}>
                <div>
                  <strong>
                    {session.is_current ? 'This browser' : 'Other browser'}
                  </strong>
                  <p>{session.user_agent || 'Browser details unavailable'}</p>
                  <small>
                    Started{' '}
                    {new Date(session.created_at * 1000).toLocaleString(
                      'en-US',
                    )}
                  </small>
                </div>
                <PendingButton
                  pending={pending}
                  onClick={() =>
                    void run(() => endSession(session.id, session.is_current))
                  }
                >
                  End session
                </PendingButton>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
