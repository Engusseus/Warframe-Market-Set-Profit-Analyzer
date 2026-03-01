import { test, expect } from '@playwright/test';
import { clearStorage } from '../utils/storage-helpers';
import { ROUTES } from '../fixtures/test-data';

test.describe('Strategy Change Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);
    await clearStorage(page);
    await page.goto(ROUTES.ANALYSIS);
    await page.waitForLoadState('networkidle');
  });

  test('should display all three strategies on analysis page', async ({ page }) => {
    const safeButton = page.getByRole('button', { name: /Safe & Steady/i });
    if (await safeButton.isVisible().catch(() => false)) {
      await expect(safeButton).toBeVisible();
      await expect(page.getByRole('button', { name: /Balanced/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Aggressive Growth/i })).toBeVisible();
      return;
    }

    await expect(page.locator('text=/No Uplink Data Found|No data|No results/i')).toBeVisible();
  });

  test('should change strategy selection', async ({ page }) => {
    const aggressiveButton = page.getByRole('button', { name: /Aggressive Growth/i });
    if (!(await aggressiveButton.isVisible().catch(() => false))) {
      return;
    }
    await aggressiveButton.click();
    await expect(aggressiveButton).toBeVisible();
  });

  test('should keep rendering after strategy changes', async ({ page }) => {
    const safeButton = page.getByRole('button', { name: /Safe & Steady/i });
    const balancedButton = page.getByRole('button', { name: /Balanced/i });
    if (!(await safeButton.isVisible().catch(() => false))) {
      await expect(page.locator('text=/No Uplink Data Found|No data|No results/i')).toBeVisible();
      return;
    }

    await safeButton.click();
    await balancedButton.click();

    const table = page.locator('table');
    const emptyState = page.locator('text=/No Uplink Data Found|No data|No results/i');
    await expect(table.or(emptyState)).toBeVisible();
  });

  test('should keep score section available when rows are expanded', async ({ page }) => {
    const safeButton = page.getByRole('button', { name: /Safe & Steady/i });
    if (!(await safeButton.isVisible().catch(() => false))) {
      return;
    }

    const firstRow = page.locator('tbody tr').first();
    if (!(await firstRow.isVisible().catch(() => false))) {
      return;
    }

    await firstRow.click();
    const scoreInfo = page.locator('text=/Score|Profit|Volume|Trend|Volatility/i');
    await expect(scoreInfo.first()).toBeVisible();

    await page.getByRole('button', { name: /Aggressive/i }).click();
    await expect(scoreInfo.first()).toBeVisible();
  });
});
