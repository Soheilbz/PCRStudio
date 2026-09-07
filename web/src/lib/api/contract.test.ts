/**
 * Guards generated browser vocabulary and error-schema parity with Rust.
 *
 * Domain vocabulary IDs are generated from their canonical authorities; these
 * tests independently prove the generated projection still matches Rust.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  accountErrorSchema,
  coreErrorSchema,
  goalSchema,
  modifierSchema,
  moduleStatusSchema,
  projectErrorSchema,
} from "./types";

function readRustSource(relative: string): string {
  // Vitest runs from `web/`; the crates sit beside it in the repository root.
  return readFileSync(join(process.cwd(), "..", relative), "utf8");
}

/** Variant names of a `pub enum`, in declaration order. */
function enumVariants(source: string, name: string): string[] {
  const start = source.indexOf(`pub enum ${name} {`);
  if (start === -1) throw new Error(`could not find \`pub enum ${name}\` in the Rust source`);
  const bodyStart = source.indexOf("{", start) + 1;

  let depth = 1;
  let index = bodyStart;
  while (index < source.length && depth > 0) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    index += 1;
  }

  return source
    .slice(bodyStart, index - 1)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => !line.startsWith("//") && !line.startsWith("#["))
    .map((line) => /^([A-Z]\w*)\s*[,({]/.exec(line)?.[1])
    .filter((variant): variant is string => Boolean(variant));
}

const kebab = (variant: string) => variant.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();

const camel = (variant: string) => variant.charAt(0).toLowerCase() + variant.slice(1);

describe("the TypeScript wire types match the Rust ones", () => {
  const taxonomySource = readRustSource("crates/pcr-core/src/taxonomy.rs");
  const errorSource = readRustSource("crates/pcr-core/src/error.rs");

  // Order matters for the goals: it is the order the sidebar groups in, and
  // both sides read it from the same declaration.
  it("covers every Goal", () => {
    expect(enumVariants(taxonomySource, "Goal").map(kebab)).toEqual([...goalSchema.options]);
  });

  it("covers every Modifier", () => {
    expect(enumVariants(taxonomySource, "Modifier").map(kebab)).toEqual([
      ...modifierSchema.options,
    ]);
  });

  it("covers every Status", () => {
    expect(enumVariants(taxonomySource, "Status").map(kebab)).toEqual([
      ...moduleStatusSchema.options,
    ]);
  });

  it("covers every CoreError kind", () => {
    const rust = enumVariants(errorSource, "CoreError").map(camel).sort();
    const typescript = coreErrorSchema.options.map((option) => option.shape.kind.value).sort();
    expect(rust).toEqual(typescript);
  });

  it("covers every AccountError kind", () => {
    const accountSource = readRustSource("crates/pcr-accounts/src/error.rs");
    const rust = enumVariants(accountSource, "AccountError").map(camel);
    // The schema also names the sign-in limiter's refusal, which is not an
    // AccountError because it is produced before the store is called. The
    // sensitive-operation limiter uses the AccountError::TooManyRequests
    // variant and must therefore be covered by this comparison.
    const extra = ["tooManyAttempts"];
    const typescript = accountErrorSchema.options
      .map((option) => option.shape.kind.value)
      .filter((kind) => !extra.includes(kind))
      .sort();
    expect([...rust].sort()).toEqual(typescript);
  });

  it("covers every ProjectError kind", () => {
    const projectSource = readRustSource("crates/pcr-projects/src/lib.rs");
    const rust = enumVariants(projectSource, "ProjectError").map(camel).sort();
    const typescript = projectErrorSchema.options.map((option) => option.shape.kind.value).sort();
    expect(rust).toEqual(typescript);
  });
});
