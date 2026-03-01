import { test, expect } from '@playwright/test';
import { clearStorage, hasStoredAnalysis } from '../utils/storage-helpers';
import { ROUTES, TIMEOUTS } from '../fixtures/test-data';

test.describe('Live Analysis Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);
    await clearStorage(page);
    await page.reload();
  });

  test('should show live monitor and connection telemetry', async ({ page }) => {
    await expect(page.locator('text=Live Run Monitor')).toBeVisible();
    await expect(page.locator('text=Live Updating').first()).toBeVisible();
    await expect(page.locator('text=/Connection|Latest Run ID|Loaded At/i').first()).toBeVisible();
  });

  test('should persist analysis data when a run is loaded', async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);
    await page.waitForTimeout(2000);
    await page.waitForTimeout(1500);

    const hasData = await hasStoredAnalysis(page);
    if (!hasData) {
      return;
    }

    await page.reload();
    await page.waitForTimeout(1500);
    const hasDataAfterReload = await hasStoredAnalysis(page);
    expect(hasDataAfterReload).toBe(true);
  });

  test('should navigate to analysis grid when data link is available', async ({ page }) => {
    const accessDataGrid = page.locator('a:has-text("Access Data Grid"), button:has-text("Access Data Grid")');
    const isVisible = await accessDataGrid.first().isVisible().catch(() => false);
    if (!isVisible) {
      return;
    }

    await accessDataGrid.first().click();
    await expect(page).toHaveURL(/\/analysis/, { timeout: TIMEOUTS.NAVIGATION });

    const table = page.locator('table');
    const emptyState = page.locator('text=/No Uplink Data Found|No data|No results/i');
    await expect(table.or(emptyState)).toBeVisible();
  });

  test('should keep monitoring state across navigation', async ({ page }) => {
    await page.waitForTimeout(1500);
    await page.goto(ROUTES.HISTORY);
    await expect(page).toHaveURL(/\/history/);

    await page.goto(ROUTES.DASHBOARD);
    await page.waitForTimeout(1500);
    await expect(page.locator('text=Live Updating').first()).toBeVisible({ timeout: TIMEOUTS.ANALYSIS });
  });
});

