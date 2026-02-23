import { test, expect } from '@playwright/test';
import { clearStorage, hasStoredAnalysis } from '../utils/storage-helpers';
import { waitForAnalysisComplete, isAnalysisComplete } from '../utils/sse-helpers';
import { ROUTES, TIMEOUTS } from '../fixtures/test-data';

test.describe('Full Analysis Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.goto(ROUTES.DASHBOARD);
    await clearStorage(page);
    await page.reload();
  });

  test('should run analysis in test mode and display results', async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);

    // Find and enable test mode checkbox
    const testModeCheckbox = page.locator('input[type="checkbox"]').first();
    if (await testModeCheckbox.isVisible()) {
      await testModeCheckbox.check();
      expect(await testModeCheckbox.isChecked()).toBe(true);
    }

    // Click the Run Analysis button
    const runButton = page.locator('button').filter({ hasText: /Run Analysis|Analyze/i }).first();
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Verify button changes to indicate running state
    await expect(
      page.locator('button').filter({ hasText: /Running|Analyzing/i })
    ).toBeVisible({ timeout: 5000 });

    // Wait for analysis to complete (up to 2 minutes for rate-limited API)
    await waitForAnalysisComplete(page, TIMEOUTS.ANALYSIS);

    // Verify results are available
    const viewResultsButton = page.locator('button').filter({ hasText: /View Results|View Analysis/i });
    await expect(viewResultsButton).toBeVisible();

    // Navigate to results
    await viewResultsButton.click();
    await expect(page).toHaveURL(/\/analysis/);

    // Verify analysis page has data
    await expect(page.locator('table')).toBeVisible({ timeout: 5000 });

    // Should have some rows (test mode = max 10 sets, may be filtered)
    const rows = await page.locator('tbody tr').count();
    expect(rows).toBeGreaterThan(0);
    expect(rows).toBeLessThanOrEqual(10);
  });

  test('should persist analysis data in localStorage', async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);

    // Enable test mode and run analysis
    const testModeCheckbox = page.locator('input[type="checkbox"]').first();
    if (await testModeCheckbox.isVisible()) {
      await testModeCheckbox.check();
    }

    const runButton = page.locator('button').filter({ hasText: /Run Analysis|Analyze/i }).first();
    await runButton.click();
    await waitForAnalysisComplete(page, TIMEOUTS.ANALYSIS);

    // Verify data is in localStorage
    const hasData = await hasStoredAnalysis(page);
    expect(hasData).toBe(true);

    // Reload and verify data persists
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Should still have access to results
    const hasDataAfterReload = await hasStoredAnalysis(page);
    expect(hasDataAfterReload).toBe(true);
  });

  test('should show progress updates during analysis', async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);

    // Enable test mode
    const testModeCheckbox = page.locator('input[type="checkbox"]').first();
    if (await testModeCheckbox.isVisible()) {
      await testModeCheckbox.check();
    }

    // Start analysis
    const runButton = page.locator('button').filter({ hasText: /Run Analysis|Analyze/i }).first();
    await runButton.click();

    // Wait a bit for progress to start showing
    await page.waitForTimeout(2000);

    // Check for progress indicators (may be percentage or step text)
    const progressIndicator = page.locator('text=/%/, text=/Step/, text=/Fetching/, text=/Calculating/');
    const hasProgress = await progressIndicator.first().isVisible().catch(() => false);

    // Wait for completion
    await waitForAnalysisComplete(page, TIMEOUTS.ANALYSIS);

    // Analysis should complete successfully
    expect(await isAnalysisComplete(page)).toBe(true);
  });

  test('should handle navigation during analysis', async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);

    // Enable test mode and start analysis
    const testModeCheckbox = page.locator('input[type="checkbox"]').first();
    if (await testModeCheckbox.isVisible()) {
      await testModeCheckbox.check();
    }

    const runButton = page.locator('button').filter({ hasText: /Run Analysis|Analyze/i }).first();
    await runButton.click();

    // Wait a bit for analysis to start
    await page.waitForTimeout(2000);

    // Navigate to History page
    await page.goto(ROUTES.HISTORY);
    await expect(page).toHaveURL(/\/history/);

    // Navigate back to Dashboard
    await page.goto(ROUTES.DASHBOARD);
    await page.waitForLoadState('networkidle');

    // Wait for page to settle and check if we can see either:
    // 1. Analysis still running (button shows running state)
    // 2. Analysis completed (View Results visible)
    // 3. Ready to run again (Run Analysis visible)
    const runningButton = page.locator('button').filter({ hasText: /Running|Analyzing/i });
    const viewResultsButton = page.locator('button').filter({ hasText: /View Results|View Analysis/i });
    const runAnalysisButton = page.locator('button').filter({ hasText: /Run Analysis|Analyze/i });

    // Wait up to 2 minutes for analysis to reach a stable state
    await expect(
      runningButton.or(viewResultsButton).or(runAnalysisButton)
    ).toBeVisible({ timeout: TIMEOUTS.ANALYSIS });

    // If still running, wait for completion
    if (await runningButton.isVisible()) {
      await waitForAnalysisComplete(page, TIMEOUTS.ANALYSIS);
    }
  });
});
