// Generated from contracts/http-api.toml; do not hand-edit.
export const HTTP_ROUTES = {
  "auth_account_delete": {
    "auth": "session",
    "method": "DELETE",
    "path": "/api/v1/auth/account"
  },
  "auth_email": {
    "auth": "session",
    "method": "PATCH",
    "path": "/api/v1/auth/email"
  },
  "auth_login": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/auth/login"
  },
  "auth_logout": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/auth/logout"
  },
  "auth_me": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/auth/me"
  },
  "auth_password": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/auth/password"
  },
  "auth_preferences_get": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/auth/preferences"
  },
  "auth_preferences_put": {
    "auth": "session",
    "method": "PUT",
    "path": "/api/v1/auth/preferences"
  },
  "auth_profile": {
    "auth": "session",
    "method": "PATCH",
    "path": "/api/v1/auth/profile"
  },
  "auth_recover": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/auth/recover"
  },
  "auth_recovery_get": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/auth/recovery"
  },
  "auth_recovery_post": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/auth/recovery"
  },
  "auth_register": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/auth/register"
  },
  "auth_sessions_delete": {
    "auth": "session",
    "method": "DELETE",
    "path": "/api/v1/auth/sessions"
  },
  "check_primers": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/check-primers"
  },
  "engines": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/engines"
  },
  "enzymes": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/enzymes"
  },
  "goals": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/goals"
  },
  "health": {
    "auth": "public",
    "method": "GET",
    "path": "/health"
  },
  "info": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/info"
  },
  "job_cancel": {
    "auth": "session",
    "method": "DELETE",
    "path": "/api/v1/projects/{id}/jobs/{job}"
  },
  "job_get": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects/{id}/jobs/{job}"
  },
  "jobs_create": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/projects/{id}/jobs"
  },
  "modifiers": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/modifiers"
  },
  "module": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/modules/{id}"
  },
  "module_design": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/modules/{id}/design"
  },
  "module_multiplex": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/modules/{id}/multiplex"
  },
  "module_presets": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/modules/{id}/presets"
  },
  "modules": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/modules"
  },
  "operator_diagnostics": {
    "auth": "operator",
    "method": "GET",
    "path": "/operator/diagnostics"
  },
  "operator_metrics": {
    "auth": "operator",
    "method": "GET",
    "path": "/operator/metrics"
  },
  "presets": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/presets"
  },
  "project_delete": {
    "auth": "session",
    "method": "DELETE",
    "path": "/api/v1/projects/{id}"
  },
  "project_design": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/projects/{id}/design"
  },
  "project_get": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects/{id}"
  },
  "project_limits": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/projects/limits"
  },
  "project_patch": {
    "auth": "session",
    "method": "PATCH",
    "path": "/api/v1/projects/{id}"
  },
  "project_restore": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/projects/{id}/restore"
  },
  "projects_create": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/projects"
  },
  "projects_export": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects/export"
  },
  "projects_import": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/projects/import"
  },
  "projects_list": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects"
  },
  "ready": {
    "auth": "public",
    "method": "GET",
    "path": "/ready"
  },
  "run_delete": {
    "auth": "session",
    "method": "DELETE",
    "path": "/api/v1/projects/{id}/runs/{run}"
  },
  "run_get": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects/{id}/runs/{run}"
  },
  "run_share_delete": {
    "auth": "session",
    "method": "DELETE",
    "path": "/api/v1/projects/{id}/runs/{run}/share"
  },
  "run_share_get": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects/{id}/runs/{run}/share"
  },
  "run_share_post": {
    "auth": "session",
    "method": "POST",
    "path": "/api/v1/projects/{id}/runs/{run}/share"
  },
  "runs_list": {
    "auth": "session",
    "method": "GET",
    "path": "/api/v1/projects/{id}/runs"
  },
  "scientific_ready": {
    "auth": "public",
    "method": "GET",
    "path": "/ready/scientific"
  },
  "sequence_align": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/sequences/align"
  },
  "sequence_aligners": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/sequences/align"
  },
  "sequence_consensus": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/sequences/consensus"
  },
  "sequence_fetch": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/sequences/fetch"
  },
  "sequence_fetch_availability": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/sequences/fetch"
  },
  "shared_run": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/shared/{token}"
  },
  "statuses": {
    "auth": "public",
    "method": "GET",
    "path": "/api/v1/statuses"
  },
  "vector_primers": {
    "auth": "public",
    "method": "POST",
    "path": "/api/v1/vector-primers"
  }
} as const;

export type HttpRouteId = keyof typeof HTTP_ROUTES;
export function httpRoute(id: HttpRouteId, params: Record<string, string> = {}): string {
  return HTTP_ROUTES[id].path.replace(/\{([^}]+)\}/g, (_match, key: string) => {
    const value = params[key];
    if (value === undefined) throw new Error(`Missing HTTP route parameter: ${key}`);
    return encodeURIComponent(value);
  });
}
