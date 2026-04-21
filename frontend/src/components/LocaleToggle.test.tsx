import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { LocaleProvider, useLocale } from "../i18n";
import { LocaleToggle } from "./LocaleToggle";

function Probe() {
  const { lang } = useLocale();
  return <span data-testid="probe-lang">{lang}</span>;
}

describe("LocaleToggle", () => {
  beforeEach(() => window.localStorage.clear());

  it("renders EN and FR buttons; clicking FR sets the locale", () => {
    render(
      <LocaleProvider>
        <LocaleToggle />
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("probe-lang").textContent).toBe("en");
    fireEvent.click(screen.getByTestId("locale-fr"));
    expect(screen.getByTestId("probe-lang").textContent).toBe("fr");
    expect(window.localStorage.getItem("locale")).toBe("fr");
    fireEvent.click(screen.getByTestId("locale-en"));
    expect(screen.getByTestId("probe-lang").textContent).toBe("en");
  });
});
