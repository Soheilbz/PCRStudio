import { describe, expect, it } from "vitest";

import { isSafeDestination } from "./destination";

describe("isSafeDestination", () => {
  it.each([
    "/",
    "/projects",
    "/projects/123?compare=a%2Cb",
    "/account#security",
    "/?next=//text-inside-a-query",
  ])("accepts internal destination %s", (value) => {
    expect(isSafeDestination(value)).toBe(true);
  });

  it.each([
    "",
    "projects",
    "https://example.org/",
    "//example.org/",
    "/\\example.org/",
    "/\n//example.org/",
    "/\r//example.org/",
    "/\t//example.org/",
    "/\u0000//example.org/",
  ])("rejects off-site or parser-ambiguous destination %j", (value) => {
    expect(isSafeDestination(value)).toBe(false);
  });
});
