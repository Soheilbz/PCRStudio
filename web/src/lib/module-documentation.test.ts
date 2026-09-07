import { describe, expect, it } from "vitest";

import documentation from "./module-documentation.generated.json";

describe("generated module documentation", () => {
  it("keeps a complete bibliography for every module and preserves parenthesized DOIs", () => {
    expect(Object.keys(documentation.modules)).toHaveLength(21);

    for (const entry of Object.values(documentation.modules)) {
      expect(entry.references.length).toBeGreaterThan(0);
      expect(
        entry.references.every(
          ({ citation, kind, url }) =>
            citation && (kind === "journal" || kind === "web") && /^https?:\/\//.test(url),
        ),
      ).toBe(true);
      expect(
        entry.references.some(({ url }) => url.includes("github.com/pcrstudio/pcrstudio/")),
      ).toBe(false);
    }

    const nestedUrls = documentation.modules["nested-pcr"].references.map(({ url }) => url);
    expect(nestedUrls).toContain("https://doi.org/10.1016/0035-9203(93)90478-9");

    const standard = documentation.modules["standard-pcr"].references;
    expect(standard.map(({ citation }) => citation)).toContain(
      "Lorenz TC. Polymerase chain reaction: basic protocol plus troubleshooting and optimization strategies. J Vis Exp. 2012;(63):3998. doi:10.3791/3998.",
    );
  });
});
