import { describe, expect, it } from "vitest";

import {
  parsePublicOrigin,
  parseSerializedOrigin,
  publicOriginRequiresSecureTransport,
  requirePublicOrigin,
} from "@/lib/http/public-origin";

describe("public origin authority", () => {
  it.each(["https://pcr.example", "https://pcr.example/", "http://127.0.0.1:8080"])(
    "accepts an origin-only deployment URL: %s",
    (raw) => {
      expect(parsePublicOrigin(raw)?.origin).toBe(new URL(raw).origin);
    },
  );

  it.each([
    "",
    "file:///tmp/pcrstudio",
    "https://user:pass@pcr.example",
    "https://pcr.example/app",
    "https://pcr.example/?x=1",
    "https://pcr.example/#fragment",
  ])("rejects non-origin deployment URLs: %s", (raw) => {
    expect(parsePublicOrigin(raw)).toBeNull();
  });

  it("requires Origin-header serialization rather than an arbitrary URL with the same origin", () => {
    expect(parseSerializedOrigin("https://pcr.example")?.origin).toBe("https://pcr.example");
    expect(parseSerializedOrigin("https://pcr.example/")).toBeNull();
    expect(parseSerializedOrigin("https://pcr.example/path")).toBeNull();
  });

  it("fails an explicitly malformed configured public URL instead of silently widening trust", () => {
    expect(() => requirePublicOrigin("https://pcr.example/app", "http://localhost:3000")).toThrow();
  });

  it("keeps secure-transport policy identical for cookies and response headers", () => {
    expect(publicOriginRequiresSecureTransport("https://pcr.example", "production")).toBe(true);
    expect(publicOriginRequiresSecureTransport("http://pcr.example", "production")).toBe(true);
    expect(publicOriginRequiresSecureTransport("http://localhost:3000", "production")).toBe(false);
    expect(publicOriginRequiresSecureTransport("http://127.0.0.1:3000", "production")).toBe(false);
    expect(publicOriginRequiresSecureTransport("http://[::1]:3000", "production")).toBe(false);
    expect(publicOriginRequiresSecureTransport("http://pcr.example", "development")).toBe(false);
    expect(publicOriginRequiresSecureTransport(undefined, "production")).toBe(true);
    expect(publicOriginRequiresSecureTransport("not a url", "production")).toBe(true);
  });
});
