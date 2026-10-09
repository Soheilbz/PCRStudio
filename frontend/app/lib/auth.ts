// The standard allauth browser envelope is separate from the generated business API.
// Wire source: django-allauth headless OpenAPI specification, library version pinned by backend.
import { ApiError, bootstrapCsrf, csrfCookie } from './api';
export type AuthResult = {
  status: number;
  meta?: { is_authenticated?: boolean; secret?: string; totp_url?: string };
  data?: unknown;
  errors?: { message: string; param?: string; code?: string }[];
};
export type AuthFlow = { id: string; is_pending?: boolean };
export function flows(result: AuthResult): AuthFlow[] {
  if (
    typeof result.data !== 'object' ||
    result.data === null ||
    !('flows' in result.data)
  )
    return [];
  return (result.data as { flows: AuthFlow[] }).flows;
}
export async function authRequest(
  path: string,
  method = 'GET',
  body?: unknown,
  accepted: number[] = [],
  signal?: AbortSignal,
): Promise<AuthResult> {
  await bootstrapCsrf(signal);
  const response = await fetch(`/_allauth/browser/v1/${path}`, {
    method,
    signal,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfCookie(),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let result: AuthResult;
  try {
    result = (await response.json()) as AuthResult;
  } catch {
    throw new ApiError(
      response.status,
      'service_unavailable',
      'The service is temporarily unavailable. Please try again.',
    );
  }
  if (!response.ok && !accepted.includes(response.status))
    throw new ApiError(
      response.status,
      result.errors?.[0]?.code ?? 'auth_failed',
      result.errors?.map((e) => e.message).join(' ') ||
        (response.status === 429
          ? 'Too many attempts. Please wait before trying again.'
          : response.status === 401
            ? 'Please confirm your identity in Account settings, then try again.'
            : 'We couldn’t complete this request. Please try again.'),
    );
  return result;
}
export type BrowserSession = {
  id: number;
  user_agent: string;
  created_at: number;
  last_seen_at?: number;
  is_current: boolean;
};
export function sessionData(result: AuthResult): BrowserSession[] {
  return result.data as BrowserSession[];
}
export function recoveryData(result: AuthResult): string[] {
  return (result.data as { unused_codes: string[] }).unused_codes;
}
