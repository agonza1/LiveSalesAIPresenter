import { test, expect, type Page } from '@playwright/test';

async function gotoWithRetry(page: Page, url: string, attempts = 3) {
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20_000 });
      return;
    } catch (error) {
      lastError = error;
      if (attempt === attempts) throw error;
      await page.waitForTimeout(1000 * attempt);
    }
  }
  throw lastError;
}

test('benchmark runner simulates passing and failure scenario reports', async ({ page, baseURL }) => {
  expect(baseURL, 'Playwright baseURL must be configured').toBeTruthy();
  await gotoWithRetry(page, `${baseURL}/benchmarks`);

  await expect(page.getByRole('heading', { name: /run the real benchmark workflow/i })).toBeVisible();
  await expect(page.getByLabel('Benchmark suite')).toContainText('Call Center Voice AI', { timeout: 30_000 });
  await expect(page.getByLabel('Scenario')).toContainText('Billing Address Change');
  await expect(page.getByRole('link', { name: 'Suite contract' })).toHaveAttribute('href', /\/api\/benchmarks\/suites\/call-center-voice-ai\/contract/);
  await expect(page.getByRole('link', { name: 'Scenario contract' })).toHaveAttribute('href', /\/api\/benchmarks\/suites\/call-center-voice-ai\/scenarios\/billing-address-change\/contract/);
  await page.getByText('Scenario rubric').click();
  await expect(page.getByText('Caller only knows the old ZIP code at first.')).toBeVisible();
  await expect(page.getByText('The account is verified, the billing address update is confirmed')).toBeVisible();

  await page.getByLabel('Agent profile').fill('playwright text agent');
  await page.getByLabel('Agent version').fill('agent-playwright-v2');
  await page.getByLabel('Prompt version').fill('prompt-playwright');
  await page.getByLabel('Model').fill('model-playwright');
  await page.getByRole('button', { name: 'Simulate scenario' }).click();

  await expect(page.getByRole('heading', { name: /pass/i })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Agent agent-playwright-v2 · Prompt prompt-playwright · Model model-playwright')).toBeVisible();
  await expect(page.getByText('Synthetic conversation')).toBeVisible();
  await expect(page.getByText('Evidence quality')).toBeVisible();
  await expect(page.getByText('Synthetic user')).toBeVisible();
  await expect(page.getByText(/playwright text agent/)).toBeVisible();
  await expect(page.getByText('vCon artifact')).toBeVisible();
  await expect(page.getByText(/"vcon": "0\.0\.2"/)).toBeVisible();
  await expect(page.getByLabel('Call or vCon JSON')).toHaveValue(/"vcon": "0\.0\.2"/);
  await expect(page.getByRole('link', { name: 'Report JSON' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'JUnit' })).toBeVisible();
  await expect(page.getByText('No missing required actions reported.')).toBeVisible();
  await expect(page.getByText('No forbidden actions observed.')).toBeVisible();

  const transcript = page.getByLabel('Transcript');
  await expect(transcript).toHaveValue(/playwright text agent/);
  await expect(page.getByLabel('Action/tool trace')).toHaveValue(/verify account using at least two identifiers/);
  await expect(page.getByLabel('Final observed state')).toHaveValue(/"complete": true/);

  await page.getByLabel('Failure baseline').check();
  await page.getByRole('button', { name: 'Simulate scenario' }).click();

  await expect(page.getByRole('heading', { name: /needs_review/i })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('state refill timing expectations').or(page.getByText('explain next invoice impact'))).toBeVisible();
  await expect(page.getByLabel('Final observed state')).toHaveValue(/"complete": false/);
  await expect(page.getByText('Top failure')).toBeVisible();
  await expect(page.getByText(/required_action_execution|forbidden_action_avoidance|final_state_correctness/).first()).toBeVisible();

  await page.getByRole('button', { name: 'Simulate suite' }).click();
  await expect(page.getByText('Suite run')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Runs saved')).toBeVisible();
  await expect(page.getByText('Pass rate')).toBeVisible();
  await expect(page.getByText(/missing|forbidden|No missing actions/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Export CSV' })).toHaveAttribute('href', /\/api\/benchmarks\/runs\.csv\?.*suite_id=call-center-voice-ai/);
  await expect(page.getByRole('link', { name: 'Export Markdown' })).toHaveAttribute('href', /\/api\/benchmarks\/runs\.md\?.*suite_id=call-center-voice-ai/);
  await expect(page.getByRole('link', { name: 'Export JSONL' })).toHaveAttribute('href', /\/api\/benchmarks\/runs\.jsonl\?.*suite_id=call-center-voice-ai/);
  await expect(page.getByRole('link', { name: 'Export JUnit' })).toHaveAttribute('href', /\/api\/benchmarks\/runs\.junit\.xml\?.*suite_id=call-center-voice-ai/);
  await expect(page.getByRole('link', { name: 'Markdown' }).first()).toBeVisible();
});
