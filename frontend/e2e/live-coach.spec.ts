import { test, expect } from "@playwright/test";

// Covers the engine-path happy flow end-to-end without hitting any LLM:
// session creation, hand creation, engine.start snapshot, engine.apply
// advancing the state. The advice-request flow needs a fake oracle
// factory and is covered by the backend lifecycle test; here we focus
// on the UI + HTTP plumbing.

test("reveals flop after preflop closes", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("new-hand").click();
  await expect(page.getByTestId("poker-table")).toBeVisible();

  // Hero call (SB limp) — wait for villain to become to-act before checking
  await page.getByTestId("action-call").click();
  await expect(page.getByTestId("seat-villain")).toHaveAttribute("data-to-act", "true");
  // Villain check (BB option closes preflop)
  await page.getByTestId("action-check").click();

  // Board picker should appear
  await expect(page.getByTestId("board-picker")).toBeVisible();

  // Fill 3 flop cards
  await page.getByTestId("board-grid-2c").click();
  await page.getByTestId("board-grid-3d").click();
  await page.getByTestId("board-grid-5s").click();
  await page.getByTestId("board-picker-confirm").click();

  // Picker gone, action bar visible for flop play
  await expect(page.getByTestId("board-picker")).toBeHidden();
  await expect(page.getByTestId("action-bar")).toBeVisible();
});

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
