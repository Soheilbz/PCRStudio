import { describe, expect, it } from "vitest";

import {
  classifyBrowserOrigin,
  hasExpectedBrowserOrigin,
  shouldRejectBrowserMutationOrigin,
} from "@/lib/http/origin";

describe("hasExpectedBrowserOrigin", () => {
  it("accepts the configured public origin behind a proxy", () => {
    expect(
      hasExpectedBrowserOrigin(
        "https://pcr.example",
        "http://web:3000/account/data/import",
        "https://pcr.example",
      ),
    ).toBe(true);
  });

  it("falls back to the request origin when no public site URL is configured", () => {
    expect(
      hasExpectedBrowserOrigin(
        "http://localhost:3000",
        "http://localhost:3000/account/data/import?source=backup",
        undefined,
      ),
    ).toBe(true);
  });

  it.each([
    [null, "https://pcr.example", "https://pcr.example"],
    ["null", "https://pcr.example", "https://pcr.example"],
    ["https://evil.example", "https://pcr.example", "https://pcr.example"],
    ["https://pcr.example.evil.test", "https://pcr.example", "https://pcr.example"],
    ["file:///tmp/a", "https://pcr.example", "https://pcr.example"],
    ["not a url", "https://pcr.example", "https://pcr.example"],
    ["https://pcr.example/path", "https://pcr.example", "https://pcr.example"],
    ["https://pcr.example/", "https://pcr.example", "https://pcr.example"],
    ["https://pcr.example", "https://pcr.example", "not a url"],
    ["https://pcr.example", "https://pcr.example", "https://pcr.example/app"],
  ])("rejects an invalid or foreign origin %#", (origin, requestUrl, configured) => {
    expect(hasExpectedBrowserOrigin(origin, requestUrl, configured)).toBe(false);
  });
});

describe("browser mutation origin guard", () => {
  const requestUrl = "https://app.example.test/projects/1";

  it("classifies missing, expected, foreign, and malformed origins distinctly", () => {
    expect(classifyBrowserOrigin(null, requestUrl, "https://app.example.test")).toBe("missing");
    expect(
      classifyBrowserOrigin("https://app.example.test", requestUrl, "https://app.example.test"),
    ).toBe("expected");
    expect(
      classifyBrowserOrigin("https://evil.example", requestUrl, "https://app.example.test"),
    ).toBe("foreign");
    expect(classifyBrowserOrigin("null", requestUrl, "https://app.example.test")).toBe("invalid");
  });

  it("rejects only explicitly bad origins on state-changing methods", () => {
    expect(
      shouldRejectBrowserMutationOrigin("POST", null, requestUrl, "https://app.example.test"),
    ).toBe(false);
    expect(
      shouldRejectBrowserMutationOrigin(
        "POST",
        "https://app.example.test",
        requestUrl,
        "https://app.example.test",
      ),
    ).toBe(false);
    expect(
      shouldRejectBrowserMutationOrigin(
        "POST",
        "https://evil.example",
        requestUrl,
        "https://app.example.test",
      ),
    ).toBe(true);
    expect(
      shouldRejectBrowserMutationOrigin("DELETE", "null", requestUrl, "https://app.example.test"),
    ).toBe(true);
    expect(
      shouldRejectBrowserMutationOrigin(
        "GET",
        "https://evil.example",
        requestUrl,
        "https://app.example.test",
      ),
    ).toBe(false);
  });
});
