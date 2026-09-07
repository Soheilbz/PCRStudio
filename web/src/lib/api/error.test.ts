import { describe, expect, it } from "vitest";

import { PcrStudioError, toPcrStudioError } from "./error";

describe("toPcrStudioError", () => {
  it("keeps the structured cause when the core sent one", () => {
    const error = toPcrStudioError({ kind: "notImplemented", detail: "Flanking pair" });
    expect(error).toBeInstanceOf(PcrStudioError);
    expect(error.core).toEqual({ kind: "notImplemented", detail: "Flanking pair" });
    expect(error.isNotImplemented).toBe(true);
    expect(error.message).toContain("Flanking pair");
  });

  it("names the module that was not found", () => {
    const error = toPcrStudioError({ kind: "unknownProfile", detail: "no-such-thing" });
    expect(error.message).toContain("no-such-thing");
    expect(error.isNotImplemented).toBe(false);
  });

  it("recognises a build mistake the registry would have refused", () => {
    const error = toPcrStudioError({
      kind: "incompatibleModifier",
      detail:
        "the assay `x` asks for `Multiplexed`, which the `Tiling scheme` engine does not accept",
    });
    expect(error.kind).toBe("incompatibleModifier");
    expect(error.message).toContain("Tiling scheme");
  });

  it("passes an invalid-request detail through unchanged", () => {
    const error = toPcrStudioError({ kind: "invalidRequest", detail: "template is empty" });
    expect(error.message).toBe("template is empty");
  });

  it("carries a bare string, which is what a proxy error looks like", () => {
    const error = toPcrStudioError("502 Bad Gateway");
    expect(error.message).toBe("502 Bad Gateway");
    expect(error.core).toBeNull();
  });

  it("does not invent a cause it was not given", () => {
    const error = toPcrStudioError(undefined);
    expect(error.core).toBeNull();
    expect(error.kind).toBeNull();
    expect(error.message).toBe("The server failed without saying why.");
  });

  it("recognises an account failure and keeps its kind", () => {
    const error = toPcrStudioError({ kind: "emailTaken" });
    expect(error.kind).toBe("emailTaken");
    expect(error.message).toContain("already has an account");
    // Account failures are not core failures; the module pages must not branch
    // on them by accident.
    expect(error.core).toBeNull();
  });

  it("passes a policy failure through in the words the server chose", () => {
    const error = toPcrStudioError({
      kind: "weakPassword",
      detail: "the password must be at least 10 characters",
    });
    expect(error.message).toBe("the password must be at least 10 characters");
  });

  it("says nothing about which half of a sign-in was wrong", () => {
    const error = toPcrStudioError({ kind: "invalidCredentials" });
    expect(error.message).toBe("That email and password do not match an account.");
    expect(error.message).not.toMatch(/email address (is|was) (not )?(found|registered)/i);
  });

  it("normalizes redacted store failures from the HTTP layer", () => {
    const error = toPcrStudioError({
      kind: "storeFailure",
      detail: "The account store is unavailable. Try again in a moment.",
    });
    expect(error.kind).toBe("store");
    expect(error.message).toBe("The account store is unavailable. Try again in a moment.");
  });

  it("recognizes a temporarily unavailable shared limiter", () => {
    const error = toPcrStudioError({
      kind: "serviceUnavailable",
      detail: "The service is temporarily unavailable. Try again shortly.",
    });
    expect(error.kind).toBe("store");
    expect(error.message).toContain("temporarily unavailable");
  });
});

describe("common HTTP error envelope", () => {
  it("preserves correlation and retry metadata from Rust", () => {
    const error = toPcrStudioError({
      code: "INVALID_REQUEST",
      kind: "invalidRequest",
      detail: "template is empty",
      fieldPath: "target.sequence",
      stage: "validation",
      retryable: false,
      requestId: "req-123",
    });
    expect(error.code).toBe("INVALID_REQUEST");
    expect(error.fieldPath).toBe("target.sequence");
    expect(error.stage).toBe("validation");
    expect(error.retryable).toBe(false);
    expect(error.requestId).toBe("req-123");
  });

  it("recognises the Rust cancellation vocabulary", () => {
    const error = toPcrStudioError({
      code: "REQUEST_CANCELLED",
      kind: "cancelled",
      detail: "the running design was cancelled",
      stage: "execution",
      retryable: false,
    });
    expect(error.core?.kind).toBe("cancelled");
    expect(error.message).toContain("cancelled");
  });
});
