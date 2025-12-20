import { Page, expect } from '@playwright/test';

/**
 * Wait for analysis to complete by monitoring the UI state.
 * This is more reliable than trying to intercept SSE messages.
 */
export async function waitForAnalysisComplete(
  page: Page,
  timeoutMs = 120000
): Promise<void> {
  // Wait for either "View Results" button to appear or an error
  await expect(
    page.locator('button:has-text("View Results"), button:has-text("View Analysis Results"), .text-profit-negative')
  ).toBeVisible({ timeout: timeoutMs });
}

/**
 * Wait for progress bar to show completion or for results to be ready.
 */
export async function waitForProgress(
  page: Page,
  targetProgress: number,
  timeoutMs = 120000
): Promise<void> {
  // Look for progress indicator showing target percentage or higher
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const progressText = await page.locator('text=/%/').first().textContent().catch(() => null);
    if (progressText) {
      const progress = parseInt(progressText.replace('%', ''), 10);
      if (progress >= targetProgress) {
        return;
      }
    }

    // Check if analysis completed
    const viewResultsButton = page.locator(
      'button:has-text("View Results"), button:has-text("View Analysis Results")'
    );
    if (await viewResultsButton.isVisible().catch(() => false)) {
      return;
    }

    await page.waitForTimeout(500);
  }

  throw new Error(`Timeout waiting for progress to reach ${targetProgress}%`);
}

/**
 * Check if analysis is currently running.
 */
export async function isAnalysisRunning(page: Page): Promise<boolean> {
  const runningButton = page.locator('button:has-text("Running")');
  return await runningButton.isVisible().catch(() => false);
}

/**
 * Check if analysis has completed (results available).
 */
export async function isAnalysisComplete(page: Page): Promise<boolean> {
  const viewResultsButton = page.locator(
    'button:has-text("View Results"), button:has-text("View Analysis Results")'
  );
  return await viewResultsButton.isVisible().catch(() => false);
}

/**
 * Check if an error occurred during analysis.
 */
export async function hasAnalysisError(page: Page): Promise<boolean> {
  const errorIndicator = page.locator('.text-profit-negative, .text-red-500');
  return await errorIndicator.isVisible().catch(() => false);
}
