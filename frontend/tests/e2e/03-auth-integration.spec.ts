import { test, expect } from '@playwright/test';

// Test data
const testUser = {
  email: 'test-e2e@example.com',
  name: '테스트 사용자',
  password: 'TestPassword2024!@#Complex'
};

test.describe('Authentication Integration Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any existing auth state
    await page.context().clearCookies();
    await page.goto('/');
  });

  test('complete user registration and login flow', async ({ page }) => {
    // Step 1: Navigate to registration page
    await page.goto('/auth/register');
    await expect(page.getByRole('heading', { name: 'ScoreMate 회원가입' })).toBeVisible();

    // Step 2: Fill registration form
    await page.getByPlaceholder('your@email.com').fill(testUser.email);
    await page.getByPlaceholder('홍길동').fill(testUser.name);
    await page.getByPlaceholder('8자 이상').fill(testUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(testUser.password);
    await page.getByRole('checkbox', { name: /이용약관.*동의합니다/ }).check();

    // Step 3: Submit registration form
    await page.getByRole('button', { name: '회원가입' }).click();

    // Step 4: Verify registration success or handle existing user
    try {
      // If user doesn't exist, registration should succeed
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    } catch {
      // If user already exists, we'll get an error - navigate to login
      await page.goto('/auth/login');
    }

    // Step 5: If we're not on dashboard, perform login
    if (page.url().includes('/auth/login')) {
      await page.getByPlaceholder('이메일').fill(testUser.email);
      await page.getByPlaceholder('비밀번호').fill(testUser.password);
      await page.getByRole('button', { name: '로그인' }).click();

      // Wait for login to complete
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    }

    // Step 6: Verify we're logged in and on dashboard
    await expect(page.getByText(/안녕하세요.*님/)).toBeVisible();
    await expect(page.getByText('ScoreMate 대시보드에 오신 것을 환영합니다')).toBeVisible();
  });

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/auth/login');

    // Fill form with invalid credentials
    await page.getByPlaceholder('이메일').fill('invalid@example.com');
    await page.getByPlaceholder('비밀번호').fill('wrongpassword');
    await page.getByRole('button', { name: '로그인' }).click();

    // Verify error message appears
    await expect(page.getByText(/로그인에 실패했습니다|이메일 또는 비밀번호가 올바르지 않습니다/)).toBeVisible();
    await expect(page).toHaveURL('/auth/login');
  });

  test('logout functionality works correctly', async ({ page }) => {
    // First login
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(testUser.email);
    await page.getByPlaceholder('비밀번호').fill(testUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 10000 });

    // Wait for dashboard to fully load and header to appear
    await expect(page.getByText(/안녕하세요.*님/)).toBeVisible();
    
    // Wait for header logout button to appear
    await expect(page.getByTestId('logout-button')).toBeVisible({ timeout: 5000 });

    // Then logout using the header logout button
    await page.getByTestId('logout-button').click();
    
    // Verify redirect to login page
    await expect(page).toHaveURL('/auth/login');
    
    // Verify accessing protected page redirects to login
    await page.goto('/dashboard');
    await expect(page).toHaveURL('/auth/login');
  });

  test('authentication persistence across page reloads', async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(testUser.email);
    await page.getByPlaceholder('비밀번호').fill(testUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 10000 });

    // Reload page
    await page.reload();
    
    // Should still be on dashboard (auth persisted)
    await expect(page).toHaveURL('/dashboard');
    await expect(page.getByText(/안녕하세요.*님/)).toBeVisible();
  });
});