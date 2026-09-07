import { readSessionToken } from "@/lib/auth/session";
import { httpRoute } from "@/lib/api/routes.generated";

const API_URL = (process.env.PCR_API_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
const EXPORT_TIMEOUT_MS = 310_000;

/** Stream an account export from the Rust API to the browser.
 *
 * A Server Action would have to materialise the entire JSON document as a
 * string, serialise it into the RSC response, then materialise it again in the
 * browser before a download could start. This route keeps the export a stream
 * end-to-end instead, so backup size is not coupled to the Server Action body
 * limit or to duplicate JS heaps.
 */
export async function GET(request: Request): Promise<Response> {
  const token = await readSessionToken();
  if (!token) {
    return Response.json({ error: "Your session has ended. Sign in again." }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}${httpRoute("projects_export")}`, {
      headers: {
        authorization: `Bearer ${token}`,
        ...(request.headers.get("x-forwarded-for")
          ? { "x-forwarded-for": request.headers.get("x-forwarded-for")! }
          : {}),
      },
      cache: "no-store",
      signal: AbortSignal.timeout(EXPORT_TIMEOUT_MS),
    });
  } catch {
    return Response.json(
      { error: "Your work could not be exported. Try again in a moment." },
      { status: 503, headers: { "retry-after": "5" } },
    );
  }

  if (!upstream.ok) {
    const body = await upstream.text().catch(() => "");
    return new Response(body || JSON.stringify({ error: "The export could not be prepared." }), {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8",
        "cache-control": "no-store, private",
      },
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8",
      "content-disposition":
        upstream.headers.get("content-disposition") ??
        'attachment; filename="pcrstudio-export.json"',
      "cache-control": "no-store, private",
      "x-content-type-options": "nosniff",
    },
  });
}
