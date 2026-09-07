import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";

import { Nested } from "./heading-level";

const card = (title: string) => (
  <Card>
    <CardHeader>
      <CardTitle>{title}</CardTitle>
    </CardHeader>
  </Card>
);

describe("card titles are headings a screen reader can navigate", () => {
  it("is a real heading, not a styled div", () => {
    // Ninety-eight of these were `<div>`s. To somebody using a screen reader
    // that means a page whose only landmark is its `<h1>`: no section list, no
    // way to skip between them, everything read in order or not at all.
    render(card("What to order"));
    expect(screen.getByRole("heading", { name: "What to order" })).toBeInTheDocument();
  });

  it("sits one rank below the page heading by default", () => {
    render(card("What to order"));
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
  });

  it("drops a rank inside a region that has its own heading", () => {
    // This is the case that made a per-call-site `level` prop untenable: the
    // same card is a section on one screen and an item within a section on
    // another, and both places want the same component.
    render(<Nested>{card("Pair 1")}</Nested>);
    expect(screen.getByRole("heading", { level: 3, name: "Pair 1" })).toBeInTheDocument();
  });

  it("keeps dropping as regions nest", () => {
    render(
      <Nested>
        <Nested>{card("Forward primer")}</Nested>
      </Nested>,
    );
    expect(screen.getByRole("heading", { level: 4 })).toBeInTheDocument();
  });

  it("stops at h6 rather than inventing a tag", () => {
    render(
      <Nested>
        <Nested>
          <Nested>
            <Nested>
              <Nested>{card("Deep")}</Nested>
            </Nested>
          </Nested>
        </Nested>
      </Nested>,
    );
    // `<h7>` is not an element. Six deep or more, it stays at six.
    expect(screen.getByRole("heading", { level: 6, name: "Deep" })).toBeInTheDocument();
  });
});
