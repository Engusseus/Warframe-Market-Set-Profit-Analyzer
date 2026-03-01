/**
 * Test data constants and fixtures for E2E tests.
 */

export const STRATEGIES = {
  SAFE_STEADY: 'safe_steady',
  BALANCED: 'balanced',
  AGGRESSIVE: 'aggressive',
} as const;

export const STRATEGY_NAMES = {
  [STRATEGIES.SAFE_STEADY]: 'Safe & Steady',
  [STRATEGIES.BALANCED]: 'Balanced',
  [STRATEGIES.AGGRESSIVE]: 'Aggressive Growth',
} as const;

export const ROUTES = {
  DASHBOARD: '/',
  ANALYSIS: '/analysis',
  HISTORY: '/history',
  EXPORT: '/export',
} as const;

export const SELECTORS = {
  // Dashboard
  LIVE_STATUS_BADGE: 'text=Live Updating',
  PROGRESS_BAR: '[role="progressbar"], .bg-mint',
  VIEW_RESULTS_BUTTON: 'button:has-text("Access Data Grid"), a:has-text("Access Data Grid")',

  // Analysis
  PROFIT_TABLE: 'table',
  STRATEGY_SELECTOR: 'button:has-text("Safe & Steady"), button:has-text("Balanced"), button:has-text("Aggressive")',

  // Navigation
  NAV_DASHBOARD: 'a[href="/"], button:has-text("Dashboard")',
  NAV_ANALYSIS: 'a[href="/analysis"]',
  NAV_HISTORY: 'a[href="/history"]',
  NAV_EXPORT: 'a[href="/export"]',
} as const;

/**
 * Sample scored set data for seeding tests.
 */
export const SAMPLE_SCORED_SET = {
  set_slug: 'saryn_prime_set',
  set_name: 'Saryn Prime Set',
  set_price: 150.0,
  part_cost: 100.0,
  profit_margin: 50.0,
  profit_percentage: 50.0,
  volume: 150,
  normalized_profit: 1.0,
  normalized_volume: 0.5,
  profit_score: 1.0,
  volume_score: 0.6,
  total_score: 1.6,
  composite_score: 150.0,
  trend_slope: 0.5,
  trend_multiplier: 1.1,
  trend_direction: 'rising',
  volatility: 0.15,
  volatility_penalty: 1.3,
  risk_level: 'Medium',
  profit_contribution: 50.0,
  volume_contribution: 2.18,
  trend_contribution: 1.1,
  volatility_contribution: 1.3,
  part_details: [],
};

/**
 * Sample analysis response for seeding tests.
 */
export const SAMPLE_ANALYSIS = {
  run_id: 1,
  timestamp: new Date().toISOString(),
  sets: [SAMPLE_SCORED_SET],
  total_sets: 1,
  profitable_sets: 1,
  weights: {
    strategy: 'balanced',
    profit_weight: 1.0,
    volume_weight: 1.2,
  },
  strategy: 'balanced',
  cached: false,
};

/**
 * Timeouts for different operations.
 */
export const TIMEOUTS = {
  ANALYSIS: 120000, // 2 minutes for full analysis with rate limiting
  NAVIGATION: 5000,
  ANIMATION: 1000,
  API_CALL: 10000,
} as const;
