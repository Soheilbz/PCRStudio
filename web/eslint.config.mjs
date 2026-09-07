import js from "@eslint/js";
import next from "eslint-config-next";
import globals from "globals";
import tseslint from "typescript-eslint";

// `eslint-config-next` default-exports the flat config array itself, which
// already carries the TypeScript parser, the React and hooks rules, and the
// Next-specific checks.
export default tseslint.config(
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "coverage/**",
      "test-results/**",
      "playwright-report/**",
      "next-env.d.ts",
    ],
  },
  js.configs.recommended,
  // Turns off the core rules that TypeScript already enforces better —
  // `no-undef` and `no-unused-vars` both misread type-only syntax.
  tseslint.configs.recommended,
  ...next,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    /*
     * Keep the validation library out of the browser.
     *
     * `lib/api/types.ts` begins `import { z } from "zod"`. Importing a *value*
     * from it — a constant, a schema, anything that survives to runtime — pulls
     * that module, every schema in it, and zod itself into whichever bundle did
     * the importing. One three-line record of strings, imported by three
     * components to render the word "Experimental", put 299 KB of validator in
     * every browser.
     *
     * Types are exempt because `import type` is erased before the bundler sees
     * it. Values that a component genuinely needs belong in `lib/api/labels.ts`,
     * which imports nothing.
     *
     * This is a rule rather than a note because the failure is invisible: the
     * page works, the tests pass, and the only symptom is a number nobody looks
     * at until somebody measures the bundle.
     */
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/lib/api/**", "src/**/*.test.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@/lib/api/types",
              message:
                "Import types from here, not values — a value import ships zod to the browser. " +
                "Constants belong in @/lib/api/labels.",
              allowTypeImports: true,
            },
          ],
        },
      ],
    },
  },
);
