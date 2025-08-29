import { test, expect } from '@playwright/test';

test.describe('Admin Navigation', () => {
  test('should not show 관리자 link for unauthenticated users', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: '관리자' })).not.toBeVisible();
  });

  test('should show 관리자 link for admin users and navigate to dashboard', async ({ page }) => {
    // Intercept profile call to simulate admin user
    await page.route('**/api/v1/user/profile/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          email: 'admin@example.com',
          username: 'admin',
          is_staff: true,
          plan: 'pro',
          total_quota_mb: 200,
          used_quota_mb: 10,
          referral_code: 'ABCD1234',
          date_joined: new Date().toISOString(),
          last_login: new Date().toISOString(),
          available_quota_mb: 190,
          quota_usage_percentage: 5,
        }),
      });
    });

    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'test-access');
      localStorage.setItem('refresh_token', 'test-refresh');
    });
    await page.reload();

    // 관리자 링크 노출 확인
    const adminLink = page.getByRole('link', { name: '관리자' }).first();
    await expect(adminLink).toBeVisible();
    await adminLink.click();
    await page.waitForURL('/admin/dashboard');
    await expect(page).toHaveURL('/admin/dashboard');
  });

  test('should not show 관리자 link for non-admin authenticated users', async ({ page }) => {
    // Intercept profile call to simulate normal user
    await page.route('**/api/v1/user/profile/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 2,
          email: 'user@example.com',
          username: 'user',
          is_staff: false,
          plan: 'solo',
          total_quota_mb: 200,
          used_quota_mb: 0,
          referral_code: 'EFGH5678',
          date_joined: new Date().toISOString(),
          last_login: new Date().toISOString(),
          available_quota_mb: 200,
          quota_usage_percentage: 0,
        }),
      });
    });

    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'test-access');
      localStorage.setItem('refresh_token', 'test-refresh');
    });
    await page.reload();

    await expect(page.getByRole('link', { name: '관리자' })).not.toBeVisible();
  });
});

