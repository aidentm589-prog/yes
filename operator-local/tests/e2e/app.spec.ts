import { test } from "@playwright/test";

test.describe.skip("operator console smoke", () => {
  test("loads the home page", async ({ page }) => {
    await page.goto("/");
  });
});
