import { Page } from '@playwright/test';

/**
 * Clear all localStorage and sessionStorage before test.
 */
export async function clearStorage(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}

/**
 * Get current analysis data from localStorage.
 */
export async function getStoredAnalysis(page: Page): Promise<unknown | null> {
  return await page.evaluate(() => {
    const storage = localStorage.getItem('wf-analysis-storage');
    if (!storage) return null;
    try {
      return JSON.parse(storage)?.state?.currentAnalysis;
    } catch {
      return null;
    }
  });
}

/**
 * Get the current strategy from localStorage.
 */
export async function getStoredStrategy(page: Page): Promise<string | null> {
  return await page.evaluate(() => {
    const storage = localStorage.getItem('wf-analysis-storage');
    if (!storage) return null;
    try {
      return JSON.parse(storage)?.state?.strategy;
    } catch {
      return null;
    }
  });
}

/**
 * Check if localStorage has analysis data.
 */
export async function hasStoredAnalysis(page: Page): Promise<boolean> {
  const analysis = await getStoredAnalysis(page);
  return analysis !== null;
}

/**
 * Seed localStorage with analysis data for tests that need it.
 * This is useful for testing pages that require prior analysis data.
 */
export async function seedAnalysisData(
  page: Page,
  data: {
    run_id?: number;
    timestamp?: string;
    sets?: unknown[];
    total_sets?: number;
    profitable_sets?: number;
    strategy?: string;
  }
): Promise<void> {
  const defaultData = {
    run_id: 1,
    timestamp: new Date().toISOString(),
    sets: [],
    total_sets: 0,
    profitable_sets: 0,
    strategy: 'balanced',
    weights: { strategy: 'balanced', profit_weight: 1.0, volume_weight: 1.2 },
    cached: false,
    ...data,
  };

  await page.evaluate((analysisData) => {
    localStorage.setItem(
      'wf-analysis-storage',
      JSON.stringify({
        state: {
          currentAnalysis: analysisData,
          strategy: analysisData.strategy || 'balanced',
          weights: analysisData.weights || {
            strategy: 'balanced',
            profit_weight: 1.0,
            volume_weight: 1.2,
          },
          sortBy: 'score',
          sortOrder: 'desc',
          isLoading: false,
          error: null,
          progress: null,
        },
        version: 0,
      })
    );
  }, defaultData);
}
