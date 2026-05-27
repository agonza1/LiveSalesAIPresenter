import { test, expect } from '@playwright/test';

test('homepage, pricing, and full demo are separated into distinct screens', async ({ page, baseURL }) => {
  expect(baseURL, 'Playwright baseURL must be configured').toBeTruthy();

  await page.goto(`${baseURL}/`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: /prove your ai agent can actually do the job/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /run the real benchmark workflow/i })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Simulate scenario' })).toHaveCount(0);
  await page.getByRole('link', { name: 'See pricing' }).click();

  await expect(page).toHaveURL(/\/pricing$/);
  await expect(page.getByRole('heading', { name: /price the eval loop, not just another dashboard/i })).toBeVisible();
  await expect(page.getByText(/\$4k/)).toBeVisible();
  await page.getByRole('link', { name: 'Open full demo' }).click();

  await expect(page).toHaveURL(/\/benchmarks$/);
  await expect(page.getByRole('heading', { name: /run the real benchmark workflow/i })).toBeVisible();
  await expect(page.getByText('Scenario simulation')).toBeVisible();
  await expect(page.getByLabel('Benchmark suite')).toContainText('Call Center Voice AI', { timeout: 30_000 });
});
