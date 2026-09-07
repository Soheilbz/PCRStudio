import { readSessionToken } from "@/lib/auth/session";
import { httpRoute } from "@/lib/api/routes.generated";
import { hasExpectedBrowserOrigin } from "@/lib/http/origin";
import { MAX_ACCOUNT_IMPORT_BYTES } from "@/lib/limits";

const API_URL = (process.env.PCR_API_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
const IMPORT_TIMEOUT_MS = 310_000;

/** Stream a PCRStudio backup to the Rust importer without routing it through RSC. */
export async function POST(request: Request): Promise<Response> {
  if (!hasExpectedBrowserOrigin(request.headers.get("origin"), request.url)) {
    return Response.json({ error: "This import request was not same-origin." }, { status: 403 });
  }

  const token = await readSessionToken();
  if (!token) {
    return Response.json({ error: "Your session has ended. Sign in again." }, { status: 401 });
  }

  const contentType = request.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase();
  if (contentType !== "application/json") {
    return Response.json(
      { error: "Choose the JSON export downloaded from PCRStudio." },
      { status: 415 },
    );
  }

  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_ACCOUNT_IMPORT_BYTES) {
    return Response.json(
      { error: "That backup is larger than the account import limit." },
      { status: 413 },
    );
  }

  if (!request.body) {
    return Response.json({ error: "The backup file was empty." }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}${httpRoute("projects_import")}`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
        ...(request.headers.get("x-forwarded-for")
          ? { "x-forwarded-for": request.headers.get("x-forwarded-for")! }
          : {}),
      },
      body: request.body,
      // Node's fetch requires this for a streaming request body. It is a
      // runtime option not yet represented in every TypeScript lib version.
      duplex: "half",
      cache: "no-store",
      signal: AbortSignal.timeout(IMPORT_TIMEOUT_MS),
    } as RequestInit & { duplex: "half" });
  } catch {
    return Response.json(
      { error: "The import service is unavailable. Try again in a moment." },
      { status: 503, headers: { "retry-after": "5" } },
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8",
      "cache-control": "no-store, private",
      "x-content-type-options": "nosniff",
      ...(upstream.headers.get("retry-after")
        ? { "retry-after": upstream.headers.get("retry-after")! }
        : {}),
    },
  });
}
