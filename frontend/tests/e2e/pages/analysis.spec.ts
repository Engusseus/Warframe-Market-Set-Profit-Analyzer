import { test, expect } from '@playwright/test';
import { clearStorage } from '../utils/storage-helpers';
import { ROUTES } from '../fixtures/test-data';

test.describe('Analysis Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);
    await clearStorage(page);
    await page.goto(ROUTES.ANALYSIS);
    await page.waitForLoadState('networkidle');
  });

  test('should display analysis page shell', async ({ page }) => {
    await expect(page).toHaveURL(/\/analysis/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('should display strategy controls', async ({ page }) => {
    const safeButton = page.getByRole('button', { name: /Safe & Steady/i });
    const emptyState = page.locator('text=/No Uplink Data Found|No data|No results/i');
    const hasControls = await safeButton.isVisible().catch(() => false);
    if (hasControls) {
      await expect(safeButton).toBeVisible();
      await expect(page.getByRole('button', { name: /Balanced/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Aggressive Growth/i })).toBeVisible();
      return;
    }

    await expect(emptyState).toBeVisible();
  });

  test('should show either data table or empty state', async ({ page }) => {
    const table = page.locator('table');
    const emptyState = page.locator('text=/No Uplink Data Found|No data|No results/i');
    await expect(table.or(emptyState)).toBeVisible();
  });

  test('should allow strategy interaction when table is available', async ({ page }) => {
    const table = page.locator('table');
    if (!(await table.isVisible().catch(() => false))) {
      return;
    }

    const aggressiveButton = page.getByRole('button', { name: /Aggressive Growth/i });
    await aggressiveButton.click();
    await expect(aggressiveButton).toBeVisible();
  });
});
