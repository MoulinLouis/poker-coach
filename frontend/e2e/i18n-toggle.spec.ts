import { test, expect } from "@playwright/test";

test("locale toggle switches nav labels and persists across reload", async ({ page }) => {
  await page.goto("/");

  // Default EN
  await expect(page.getByTestId("nav-live")).toHaveText(/Live Coach/);
  await expect(page.getByTestId("nav-history")).toHaveText(/History/);

  // Flip to FR
  await page.getByTestId("locale-fr").click();
  await expect(page.getByTestId("nav-live")).toHaveText(/Coach en direct/);
  await expect(page.getByTestId("nav-history")).toHaveText(/Historique/);

  // Reload — FR persists
  await page.reload();
  await expect(page.getByTestId("nav-live")).toHaveText(/Coach en direct/);

  // Back to EN
  await page.getByTestId("locale-en").click();
  await expect(page.getByTestId("nav-live")).toHaveText(/Live Coach/);
});
