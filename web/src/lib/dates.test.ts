import { describe, expect, it } from "vitest";

import { isoDay, when } from "./dates";

const NOW = Date.parse("2026-08-23T12:00:00Z");
const ago = (ms: number) => new Date(NOW - ms).toISOString();

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

describe("how long ago, in the reader's language", () => {
  it("reaches for the unit a person would use", () => {
    expect(when(ago(30 * SECOND), NOW, "en")).toMatch(/second/);
    expect(when(ago(5 * MINUTE), NOW, "en")).toMatch(/5 minutes ago/);
    expect(when(ago(3 * HOUR), NOW, "en")).toMatch(/3 hours ago/);
    expect(when(ago(2 * DAY), NOW, "en")).toMatch(/2 days ago/);
    expect(when(ago(400 * DAY), NOW, "en")).toMatch(/year/);
  });

  it("says yesterday rather than 1 day ago", () => {
    // `numeric: "auto"` is what buys this, and it is the whole reason to use
    // Intl here rather than assemble the string by hand.
    expect(when(ago(DAY), NOW, "en")).toBe("yesterday");
  });

  it("pluralises by the rules of the reader's language, not English's", () => {
    // The version this replaced appended "s" to anything that was not one.
    // Persian has a single form, so the correct string carries no plural
    // marker at all — an "s" here would be wrong in a way nobody reviewing
    // English output would ever catch.
    const persian = when(ago(3 * DAY), NOW, "fa");
    expect(persian).not.toContain("s");
    expect(persian).toContain("۳");

    // Russian picks between three forms by the last digit: 2 and 5 differ.
    expect(when(ago(2 * DAY), NOW, "ru")).not.toBe(when(ago(5 * DAY), NOW, "ru"));
  });

  it("does not claim a future time is in the past", () => {
    expect(when(new Date(NOW + 2 * HOUR).toISOString(), NOW, "en")).toMatch(/in 2 hours/);
  });
});

describe("the form the server can safely render", () => {
  it("is the same characters in every locale", () => {
    // This is what the server emits, and it has to hydrate byte-identical on a
    // reader's machine whatever their locale is set to.
    expect(isoDay("2026-08-23T12:00:00Z")).toBe("2026-08-23");
    expect(isoDay("2026-01-05T23:59:59Z")).toBe("2026-01-05");
  });
});
