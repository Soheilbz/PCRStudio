import { describe, expect, it } from "vitest";

import corpus from "./differential-context.generated.json";
import { MODULE_BINDINGS } from "./module-bindings.generated";
import modules from "./module-contracts.generated.json";

describe("Generation 1 foundation cross-language differential corpus", () => {
  it("matches generated Web module bindings and context projections", () => {
    expect(corpus.cases).toHaveLength(21);
    for (const testCase of corpus.cases) {
      const moduleId = testCase.module as keyof typeof MODULE_BINDINGS;
      const binding = MODULE_BINDINGS[moduleId];
      const moduleContract = modules.modules[moduleId];
      expect(binding.engine).toBe(testCase.expectedEngine);
      expect(binding.command).toBe(testCase.expectedCommand);
      expect(binding.resourceWeight).toBe(testCase.resourceWeight);
      expect(moduleContract.required_context).toEqual(testCase.requiredContext);
      expect(moduleContract.conditional_required_context).toEqual(
        testCase.conditionalRequiredContext,
      );
      expect(moduleContract.wire_required_context).toEqual(testCase.wireRequiredContext);
      expect(moduleContract.wire_conditional_required_context).toEqual(
        testCase.wireConditionalRequiredContext,
      );
      expect(moduleContract.wire_required_any_of).toEqual(testCase.wireRequiredAnyOf);
      expect(moduleContract.field_owners).toEqual(testCase.fieldOwners);
      expect(testCase.wrongEngine).not.toBe(testCase.expectedEngine);
    }
  });
});
