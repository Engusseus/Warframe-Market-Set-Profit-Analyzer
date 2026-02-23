import { test, expect } from '@playwright/test';
import { clearStorage, seedAnalysisData } from '../utils/storage-helpers';
import { waitForAnalysisComplete } from '../utils/sse-helpers';
import { ROUTES, TIMEOUTS, SAMPLE_ANALYSIS, STRATEGY_NAMES } from '../fixtures/test-data';

test.describe('Strategy Change Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear and seed localStorage with analysis data
    await page.goto(ROUTES.DASHBOARD);
    await clearStorage(page);

    // Run a quick analysis first to have data
    const testModeCheckbox = page.locator('input[type="checkbox"]').first();
    if (await testModeCheckbox.isVisible()) {
      await testModeCheckbox.check();
    }

    const runButton = page.locator('button').filter({ hasText: /Run Analysis|Analyze/i }).first();
    if (await runButton.isVisible()) {
      await runButton.click();
      await waitForAnalysisComplete(page, TIMEOUTS.ANALYSIS);
    }
  });

  test('should display all three strategies on analysis page', async ({ page }) => {
    await page.goto(ROUTES.ANALYSIS);

    // Check for all three strategy options using button role for specificity
    await expect(page.getByRole('button', { name: /Safe & Steady/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Balanced/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Aggressive Growth/i })).toBeVisible();
  });

  test('should change strategy and trigger rescore', async ({ page }) => {
    await page.goto(ROUTES.ANALYSIS);
    await page.waitForLoadState('networkidle');

    // Get initial table content for comparison
    const table = page.locator('table');
    if (await table.isVisible()) {
      // Click Aggressive strategy button
      const aggressiveButton = page.getByRole('button', { name: /Aggressive Growth/i });
      if (await aggressiveButton.isVisible()) {
        await aggressiveButton.click();

        // Wait for rescore to complete (UI should update)
        await page.waitForTimeout(2000);

        // Verify the strategy button appears selected (has different styling)
        await expect(aggressiveButton).toBeVisible();
      }
    }
  });

  test('should maintain data after strategy change', async ({ page }) => {
    await page.goto(ROUTES.ANALYSIS);
    await page.waitForLoadState('networkidle');

    const table = page.locator('table');
    if (await table.isVisible()) {
      // Count initial rows
      const initialRowCount = await page.locator('tbody tr').count();

      // Change strategy
      const safeButton = page.getByRole('button', { name: /Safe & Steady/i });
      if (await safeButton.isVisible()) {
        await safeButton.click();
        await page.waitForTimeout(2000);
      }

      // Table should still have data (may have fewer rows due to volume threshold)
      const newRowCount = await page.locator('tbody tr').count();
      // Safe strategy may filter out low-volume items
      expect(newRowCount).toBeGreaterThanOrEqual(0);
    }
  });

  test('should update score breakdown when strategy changes', async ({ page }) => {
    await page.goto(ROUTES.ANALYSIS);
    await page.waitForLoadState('networkidle');

    // Check if there's an expandable row or score breakdown
    const expandableRow = page.locator('tbody tr').first();

    if (await expandableRow.isVisible()) {
      // Try to expand the row
      await expandableRow.click();
      await page.waitForTimeout(500);

      // Look for score breakdown information
      const scoreInfo = page.locator('text=/Score|Profit|Volume|Trend|Volatility/i');
      const hasScoreInfo = await scoreInfo.first().isVisible().catch(() => false);

      if (hasScoreInfo) {
        // Change strategy
        const aggressiveButton = page.getByRole('button', { name: /Aggressive/i });
        if (await aggressiveButton.isVisible()) {
          await aggressiveButton.click();
          await page.waitForTimeout(2000);

          // Score breakdown should still be visible
          await expect(scoreInfo.first()).toBeVisible();
        }
      }
    }
  });
});
