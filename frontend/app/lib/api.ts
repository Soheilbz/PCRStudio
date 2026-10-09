import createClient from 'openapi-fetch';
import type { paths, components } from './api.generated';
export type Me = components['schemas']['Me'];
export type Workspace = components['schemas']['Workspace'];
export type Member = components['schemas']['Member'];
export type Project = components['schemas']['Project'];
export type ProjectAccess = components['schemas']['ProjectAccess'];
export const api = createClient<paths>({ credentials: 'same-origin' });
export function csrfCookie(): string {
  return (
    document.cookie
      .split('; ')
      .find((c) => c.startsWith('csrftoken='))
      ?.slice(10) ?? ''
  );
}
api.use({
  onRequest({ request }) {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method))
      request.headers.set('X-CSRFToken', csrfCookie());
    return request;
  },
});
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
export function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (result.error || !result.response.ok) {
    // Notify after the parsed request result exists, so a denied read settles
    // before the next task clears stale content and revalidates mounted reads.
    if (
      [401, 403, 404].includes(result.response.status) &&
      /\/api\/v1\/(projects|workspaces)\//.test(result.response.url) &&
      typeof window !== 'undefined'
    )
      window.dispatchEvent(new Event('pcrstudio-access-changed'));
    const error = result.error as
      { code?: string; detail?: string } | undefined;
    throw new ApiError(
      result.response.status,
      error?.code ?? 'request_failed',
      error?.detail ?? 'We couldn’t complete this request. Please try again.',
    );
  }
  return result.data as T;
}
export async function bootstrapCsrf(signal?: AbortSignal) {
  unwrap(await api.GET('/api/v1/csrf/', { signal }));
}
export function errorMessage(error: unknown): string {
  if (
    error instanceof ApiError &&
    error.status === 409 &&
    error.code === 'version_conflict'
  )
    return 'This project changed since you opened it. Your unsaved edits are still here. Reload the latest version, review it, then save again.';
  if (error instanceof TypeError)
    return 'Connection interrupted. Check your connection and try again.';
  return error instanceof Error
    ? error.message
    : 'Something went wrong. Please try again.';
}
