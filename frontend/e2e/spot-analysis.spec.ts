import { test, expect } from "@playwright/test";

test("navigate to spot analysis and start a hand", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-spot").click();
  await expect(page.getByRole("heading", { name: "Spot Analysis" })).toBeVisible();

  await page.getByTestId("spot-start").click();
  await expect(page.getByTestId("spot-state")).toContainText("preflop");
  await expect(page.getByTestId("spot-state")).toContainText("hero");
});
