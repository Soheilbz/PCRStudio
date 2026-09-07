import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Field, FieldGroup, WrappedField } from "./form-parts";

/**
 * That a label is attached to its control, which is not what it looks like.
 *
 * A `<Label>` sitting above an `<input>` looks identical whether or not the two
 * are joined. Sighted people read the layout; a screen reader reads the
 * association, and when there is none it announces "edit text, blank".
 *
 * The design form had a private component of its own called `Field` whose label
 * was joined to nothing — every field somebody designs primers in. Two
 * components with one name in one application is how that survived. There is
 * now one of each, and these are what keep them honest.
 */
describe("Field", () => {
  it("attaches its label to the input it renders", () => {
    render(<Field label="Melting temperature" name="tm" />);
    // getByLabelText only finds it through the association, so this passing is
    // the assertion — a nearby label would not satisfy it.
    expect(screen.getByLabelText("Melting temperature")).toBeInTheDocument();
  });

  it("attaches its hint so it is announced with the field", () => {
    render(<Field label="Password" name="password" hint="At least 10 characters." />);
    const input = screen.getByLabelText("Password");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy!)).toHaveTextContent("At least 10 characters.");
  });
});

describe("WrappedField", () => {
  it("attaches its label to a control it did not render", () => {
    render(
      <WrappedField label="Reaction">
        <select>
          <option>Taq</option>
        </select>
      </WrappedField>,
    );
    expect(screen.getByLabelText("Reaction")).toBeInTheDocument();
  });

  it("attaches its hint to that control too", () => {
    render(
      <WrappedField label="How many pairs" hint="Distinct designs, not one shifted along.">
        <input type="number" />
      </WrappedField>,
    );
    const input = screen.getByLabelText("How many pairs");
    const describedBy = input.getAttribute("aria-describedby");
    expect(document.getElementById(describedBy!)).toHaveTextContent("Distinct designs");
  });

  it("keeps an id the caller set deliberately", () => {
    // An id somebody chose is usually being pointed at by something else, and
    // overwriting it would break whatever that is.
    render(
      <WrappedField label="Target">
        <input id="chosen-on-purpose" />
      </WrappedField>,
    );
    expect(screen.getByLabelText("Target")).toHaveAttribute("id", "chosen-on-purpose");
  });

  it("gives two fields on one page different ids", () => {
    // A generated id that is not unique attaches both labels to the first
    // control, which is worse than neither being attached.
    render(
      <>
        <WrappedField label="First">
          <input />
        </WrappedField>
        <WrappedField label="Second">
          <input />
        </WrappedField>
      </>,
    );
    const first = screen.getByLabelText("First");
    const second = screen.getByLabelText("Second");
    expect(first.id).not.toBe(second.id);
    expect(first).not.toBe(second);
  });

  it("preserves an existing description when it adds its hint", () => {
    render(
      <>
        <p id="existing-description">Existing description.</p>
        <WrappedField label="Target" hint="Additional hint.">
          <input aria-describedby="existing-description" />
        </WrappedField>
      </>,
    );
    const input = screen.getByLabelText("Target");
    const ids = input.getAttribute("aria-describedby")?.split(/\s+/) ?? [];
    expect(ids).toContain("existing-description");
    expect(ids).toHaveLength(2);
    expect(ids.map((id) => document.getElementById(id)?.textContent)).toEqual(
      expect.arrayContaining(["Existing description.", "Additional hint."]),
    );
  });

  it("adds no describedby when there is no hint", () => {
    render(
      <WrappedField label="Bare">
        <input />
      </WrappedField>,
    );
    // Pointing at an element that does not exist makes a screen reader say
    // nothing where it would otherwise say the label — worse than silence.
    expect(screen.getByLabelText("Bare")).not.toHaveAttribute("aria-describedby");
  });
});

describe("FieldGroup", () => {
  it("uses fieldset and legend semantics for a related control set", () => {
    render(
      <FieldGroup label="Workflow" hint="Choose one mode.">
        <button type="button">Design</button>
        <button type="button">Evaluate</button>
      </FieldGroup>,
    );
    const group = screen.getByRole("group", { name: "Workflow" });
    expect(group.tagName).toBe("FIELDSET");
    expect(group).toHaveAccessibleDescription("Choose one mode.");
  });
});
