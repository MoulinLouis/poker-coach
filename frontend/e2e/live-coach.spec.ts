import { test, expect } from "@playwright/test";

// Covers the engine-path happy flow end-to-end without hitting any LLM:
// session creation, hand creation, engine.start snapshot, engine.apply
// advancing the state. The advice-request flow needs a fake oracle
// factory and is covered by the backend lifecycle test; here we focus
// on the UI + HTTP plumbing.

test("start a hand and take the first action", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Live Coach" })).toBeVisible();

  await page.getByRole("button", { name: "New hand" }).click();
  await expect(page.getByTestId("game-state")).toBeVisible();

  const stateText = await page.getByTestId("game-state").innerText();
  expect(stateText).toContain("preflop");
  expect(stateText).toContain("To act: hero");

  // Hero raises to 3bb (300 chips = 3.0 bb)
  await page.getByTestId("size-raise").fill("3");
  await page.getByTestId("action-raise").click();

  await expect(page.getByTestId("game-state")).toContainText("To act: villain");
  await expect(page.getByTestId("game-state")).toContainText("hero raise to 3.0bb");
});
