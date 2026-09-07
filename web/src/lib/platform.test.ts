import { afterEach, describe, expect, it, vi } from "vitest";

import { readModifierKey } from "./platform";

const pretendToBe = (platform: string, modern: boolean) => {
  vi.stubGlobal(
    "navigator",
    modern ? { userAgentData: { platform }, userAgent: "" } : { userAgent: platform },
  );
};

afterEach(() => vi.unstubAllGlobals());

describe("the shortcut hint names a key the reader has", () => {
  it("says Ctrl on Windows and Linux", () => {
    // The hint used to be a hard-coded ⌘ while the handler accepted either.
    // Naming a key somebody's keyboard does not have is worse than saying
    // nothing: it reads as the feature not being for them.
    for (const platform of ["Windows", "Linux", "Chrome OS"]) {
      pretendToBe(platform, true);
      expect(readModifierKey(), platform).toBe("Ctrl");
    }
  });

  it("says command on a Mac", () => {
    pretendToBe("macOS", true);
    expect(readModifierKey()).toBe("\u2318");
  });

  it("falls back to the user-agent string where userAgentData is missing", () => {
    // Safari and Firefox still do not implement `userAgentData`, and Safari is
    // exactly where the answer is most often the command key.
    pretendToBe("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15", false);
    expect(readModifierKey()).toBe("\u2318");

    pretendToBe("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1", false);
    expect(readModifierKey()).toBe("\u2318");

    pretendToBe("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0", false);
    expect(readModifierKey()).toBe("Ctrl");
  });
});
