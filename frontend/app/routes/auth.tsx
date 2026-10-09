import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { authRequest, flows } from '../lib/auth';
import { ThemeToggle } from '../lib/theme';
import {
  ErrorNotice,
  Field,
  Notice,
  PendingButton,
  submitted,
} from '../lib/ui';
export default function AuthPage({
  refresh,
  returnTo,
}: {
  refresh: () => Promise<void>;
  returnTo?: string;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const rawPath = location.pathname;
  const path = rawPath.startsWith('/account/verify-email/')
    ? '/verify-email'
    : rawPath.startsWith('/account/password/reset/key/')
      ? '/reset-password/confirm'
      : rawPath === '/account/signup'
        ? '/signup'
        : rawPath;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [key, setKey] = useState(
    new URLSearchParams(location.search).get('key') ??
      (rawPath.startsWith('/account/verify-email/') ||
      rawPath.startsWith('/account/password/reset/key/')
        ? decodeURIComponent(rawPath.split('/').at(-1) ?? '')
        : ''),
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState(
    typeof location.state?.notice === 'string' ? location.state.notice : '',
  );
  const signup = path === '/signup';
  const reset = path === '/reset-password';
  const resetConfirm = path === '/reset-password/confirm';
  const verify = path === '/verify-email';
  const mfa = path === '/authenticate';
  const title = signup
    ? 'Create your account'
    : reset
      ? 'Reset your password'
      : resetConfirm
        ? 'Choose a new password'
        : verify
          ? 'Verify your email'
          : mfa
            ? 'Confirm it’s you'
            : 'Welcome back';
  async function submit() {
    setPending(true);
    setError(undefined);
    setNotice('');
    try {
      const result = await authRequest(
        signup
          ? 'auth/signup'
          : reset
            ? 'auth/password/request'
            : resetConfirm
              ? 'auth/password/reset'
              : verify
                ? 'auth/email/verify'
                : mfa
                  ? 'auth/2fa/authenticate'
                  : 'auth/login',
        'POST',
        signup || (!reset && !resetConfirm && !verify && !mfa)
          ? { email, password }
          : reset
            ? { email }
            : resetConfirm
              ? { key, password }
              : verify
                ? { key }
                : { code },
        [401],
      );
      if (result.errors?.length)
        throw new Error(result.errors.map((e) => e.message).join(' '));
      if (reset) {
        setNotice(
          'If an account exists for that address, a reset link is on its way.',
        );
        return;
      }
      if (result.meta?.is_authenticated) {
        await refresh();
        navigate(
          returnTo ||
            (rawPath === '/invitations/accept'
              ? rawPath + location.search
              : '/'),
        );
        return;
      }
      const pendingFlows = flows(result);
      if (pendingFlows.some((f) => f.id === 'mfa_authenticate' && f.is_pending))
        navigate('/authenticate');
      else if (
        pendingFlows.some((f) => f.id === 'verify_email' && f.is_pending) ||
        signup
      ) {
        navigate('/verify-email');
        setNotice('Check your email for a verification link.');
      } else {
        setPassword('');
        navigate('/login', {
          state: {
            notice: verify
              ? 'Email verified. You can now sign in.'
              : resetConfirm
                ? 'Password updated. Sign in with your new password.'
                : 'Complete verification before signing in.',
          },
        });
      }
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <main id="main-content" className="auth-page">
      <div className="auth-theme">
        <ThemeToggle />
      </div>
      <Link to="/" className="brand">
        PCR<span>Studio</span>
      </Link>
      <section className="card auth-card">
        <div className="eyebrow">Private research workspaces</div>
        <h1>{title}</h1>
        <p>
          {signup
            ? 'A personal workspace for your confidential primer-design projects.'
            : verify
              ? 'Open the link in your email, or paste its verification key below.'
              : mfa
                ? 'Enter an authenticator code or an unused recovery code.'
                : 'Keep your projects and collaborations close.'}
        </p>
        <form
          onSubmit={(event) => {
            submitted(event);
            void submit();
          }}
        >
          {!verify && !mfa && !resetConfirm && (
            <Field label="Email address">
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
          )}
          {!reset && !verify && !mfa && (
            <Field
              label={resetConfirm ? 'New password' : 'Password'}
              hint={
                signup || resetConfirm
                  ? 'Use a long, unique password.'
                  : undefined
              }
            >
              <input
                type="password"
                autoComplete={
                  signup || resetConfirm ? 'new-password' : 'current-password'
                }
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
          )}
          {(verify || resetConfirm) && (
            <Field label={verify ? 'Verification key' : 'Reset key'}>
              <input
                autoComplete="off"
                required
                value={key}
                onChange={(e) => setKey(e.target.value)}
              />
            </Field>
          )}
          {mfa && (
            <Field label="Authenticator or recovery code">
              <input
                autoComplete="one-time-code"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </Field>
          )}
          <ErrorNotice error={error} />
          {notice && <Notice>{notice}</Notice>}
          <PendingButton className="primary full" pending={pending}>
            {signup
              ? 'Create account'
              : reset
                ? 'Send reset link'
                : resetConfirm
                  ? 'Save new password'
                  : verify
                    ? 'Verify email'
                    : mfa
                      ? 'Confirm code'
                      : 'Sign in'}
          </PendingButton>
        </form>
        <div className="auth-links">
          {signup ? (
            <Link to="/login">Already have an account? Sign in</Link>
          ) : (
            <>
              <Link to="/signup">Create an account</Link>
              <Link to="/reset-password">Forgot your password?</Link>
            </>
          )}
        </div>
      </section>
      <p className="auth-footer">
        Your work stays private. Access is always explicit.
      </p>
    </main>
  );
}
