import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("renders terminal and DG panel", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Data Guardian Desktop/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Scan" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Redact" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Settings" })).toBeVisible();
});

