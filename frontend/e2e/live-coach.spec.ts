import { test, expect } from "@playwright/test";

// Covers the engine-path happy flow end-to-end without hitting any LLM:
// session creation, hand creation, engine.start snapshot, engine.apply
// advancing the state. The advice-request flow needs a fake oracle
// factory and is covered by the backend lifecycle test; here we focus
// on the UI + HTTP plumbing.

test("start a hand and take the first action", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("nav-live")).toBeVisible();

  await page.getByTestId("new-hand").click();
  await expect(page.getByTestId("poker-table")).toBeVisible();

  // Hero is on the button (SB) and acts first preflop — highlighted ring.
  await expect(page.getByTestId("seat-hero")).toHaveAttribute("data-to-act", "true");

  // Raise to 3bb via the size-input + raise button
  await page.getByTestId("size-input").fill("3");
  await page.getByTestId("action-raise").click();

  // Villain now to act
  await expect(page.getByTestId("seat-villain")).toHaveAttribute("data-to-act", "true");
});
