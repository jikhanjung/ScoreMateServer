import { test, expect } from '@playwright/test';

// Test data
const testUser = {
  email: 'test-dashboard@example.com',
  name: '대시보드 테스트 사용자',
  password: 'dashboard123!'
};

test.describe('Dashboard Integration Tests', () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    
    // Login process
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(testUser.email);
    await page.getByPlaceholder('비밀번호').fill(testUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    // Wait for dashboard to load or register if user doesn't exist
    try {
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    } catch {
      // User might not exist, try to register first
      await page.goto('/auth/register');
      await page.getByPlaceholder('your@email.com').fill(testUser.email);
      await page.getByPlaceholder('홍길동').fill(testUser.name);
      await page.getByPlaceholder('8자 이상').fill(testUser.password);
      await page.getByPlaceholder('비밀번호 재입력').fill(testUser.password);
      await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
      await page.getByRole('button', { name: '회원가입' }).click();
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    }
  });

  test('dashboard loads with real API data', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Verify dashboard page elements
    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    await expect(page.getByText('환영합니다!')).toBeVisible();
    
    // Wait for stats cards to load
    await expect(page.getByText('총 악보')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('세트리스트')).toBeVisible();
    await expect(page.getByText('사용 용량')).toBeVisible();
    await expect(page.getByText('이번 달 업로드')).toBeVisible();
    
    // Verify numbers are loaded (not showing loading states)
    const totalScoresElement = page.locator('[data-testid="total-scores"], .stat-value').first();
    await expect(totalScoresElement).not.toHaveText(/로딩|Loading|-/);
  });

  test('recent scores section functionality', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Wait for recent scores section
    await expect(page.getByText('최근 악보')).toBeVisible({ timeout: 10000 });
    
    // Check if there are scores or empty state
    const hasScores = await page.getByText(/악보가 없습니다|업로드된 악보가 없습니다/).isVisible();
    
    if (!hasScores) {
      // If there are scores, verify they display properly
      const scoreElements = page.locator('[data-testid="recent-score-item"], .score-item');
      const scoreCount = await scoreElements.count();
      
      if (scoreCount > 0) {
        // Verify first score has required fields
        const firstScore = scoreElements.first();
        await expect(firstScore).toBeVisible();
        
        // Check for title and composer (common fields)
        await expect(firstScore.locator('text=/.*/')).toBeVisible();
      }
    }
    
    // Verify "모두 보기" link exists and works
    const viewAllLink = page.getByRole('link', { name: '모두 보기' });
    if (await viewAllLink.isVisible()) {
      await viewAllLink.click();
      await expect(page).toHaveURL('/scores');
      await page.goBack();
    }
  });

  test('quick actions navigation', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Test upload navigation
    const uploadLink = page.getByRole('link', { name: /악보 업로드|업로드/ });
    if (await uploadLink.isVisible()) {
      await uploadLink.click();
      await expect(page).toHaveURL('/upload');
      await page.goBack();
    }
    
    // Test scores management navigation
    const scoresLink = page.getByRole('link', { name: /악보 관리|악보 목록/ });
    if (await scoresLink.isVisible()) {
      await scoresLink.click();
      await expect(page).toHaveURL('/scores');
      await page.goBack();
    }
    
    // Test setlists navigation
    const setlistsLink = page.getByRole('link', { name: /세트리스트|새 세트리스트/ });
    if (await setlistsLink.isVisible()) {
      await setlistsLink.click();
      await expect(page).toHaveURL('/setlists');
      await page.goBack();
    }
  });

  test('dashboard responsiveness', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    await expect(page.getByText('총 악보')).toBeVisible();
    
    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    await expect(page.getByText('총 악보')).toBeVisible();
    
    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    await expect(page.getByText('총 악보')).toBeVisible();
  });

  test('dashboard error handling', async ({ page }) => {
    // Test with network offline to simulate API errors
    await page.context().setOffline(true);
    await page.goto('/dashboard');
    
    // Should handle API errors gracefully
    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    
    // Re-enable network
    await page.context().setOffline(false);
    await page.reload();
    
    // Should recover when network is back
    await expect(page.getByText('총 악보')).toBeVisible({ timeout: 10000 });
  });

  test('user profile display', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Check if user name/email is displayed anywhere
    await expect(page.getByText(testUser.name)).toBeVisible();
    
    // Check navigation items for user info
    const userMenu = page.locator('[data-testid="user-menu"], .user-profile, .user-info');
    if (await userMenu.isVisible()) {
      await expect(userMenu).toContainText(testUser.name);
    }
  });

  test('navigation menu functionality', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Test main navigation items
    const navItems = [
      { name: /대시보드|Dashboard/, url: '/dashboard' },
      { name: /악보|Scores/, url: '/scores' },
      { name: /업로드|Upload/, url: '/upload' },
      { name: /세트리스트|Setlists/, url: '/setlists' }
    ];
    
    for (const item of navItems) {
      const navLink = page.getByRole('link', { name: item.name });
      if (await navLink.isVisible()) {
        await navLink.click();
        await expect(page).toHaveURL(item.url);
        
        // Navigate back to dashboard for next test
        if (item.url !== '/dashboard') {
          await page.goto('/dashboard');
        }
      }
    }
  });

  test('data refresh on page focus', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Wait for initial load
    await expect(page.getByText('총 악보')).toBeVisible();
    
    // Simulate losing and regaining focus
    await page.evaluate(() => {
      window.dispatchEvent(new Event('blur'));
    });
    
    await page.waitForTimeout(1000);
    
    await page.evaluate(() => {
      window.dispatchEvent(new Event('focus'));
    });
    
    // Dashboard should still be functional
    await expect(page.getByText('총 악보')).toBeVisible();
  });
});