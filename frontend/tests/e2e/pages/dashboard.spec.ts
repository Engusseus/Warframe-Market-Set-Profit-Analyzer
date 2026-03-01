import { test, expect } from '@playwright/test';
import { clearStorage } from '../utils/storage-helpers';
import { ROUTES } from '../fixtures/test-data';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(ROUTES.DASHBOARD);
    await clearStorage(page);
    await page.reload();
  });

  test('should display terminal header and live status', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /System Terminal/i })).toBeVisible();
    await expect(page.locator('text=Live Updating').first()).toBeVisible();
  });

  test('should display monitoring cards', async ({ page }) => {
    await expect(page.locator('text=Total Operations')).toBeVisible();
    await expect(page.locator('text=Monitored Entities')).toBeVisible();
    await expect(page.locator('text=Last Synchronization')).toBeVisible();
  });

  test('should render live monitor panel', async ({ page }) => {
    await expect(page.locator('text=Live Run Monitor')).toBeVisible();
    await expect(page.locator('text=/Connection|Latest Run ID|Loaded At/i').first()).toBeVisible();
  });

  test('should display navigation links', async ({ page }) => {
    await expect(page.locator('a[href="/analysis"]')).toBeVisible();
    await expect(page.locator('a[href="/history"]')).toBeVisible();
    await expect(page.locator('a[href="/export"]')).toBeVisible();
  });

  test('should be responsive', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.getByRole('heading', { name: /System Terminal/i })).toBeVisible();
    await expect(page.locator('text=Live Updating').first()).toBeVisible();
    await page.setViewportSize({ width: 1280, height: 720 });
  });
});

