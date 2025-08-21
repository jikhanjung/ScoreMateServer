import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should show login page when not authenticated', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL('/auth/login');
    await expect(page.getByRole('heading', { name: 'ScoreMate 로그인' })).toBeVisible();
  });

  test('should validate login form', async ({ page }) => {
    await page.goto('/auth/login');
    
    // Try to submit empty form
    await page.getByRole('button', { name: '로그인' }).click();
    
    // Check validation messages
    await expect(page.getByText('이메일을 입력해주세요')).toBeVisible();
    await expect(page.getByText('비밀번호를 입력해주세요')).toBeVisible();
    
    // Try invalid email
    await page.getByPlaceholder('이메일').fill('invalid-email');
    await page.getByRole('button', { name: '로그인' }).click();
    await expect(page.getByText('올바른 이메일 형식이 아닙니다')).toBeVisible();
    
    // Try short password
    await page.getByPlaceholder('이메일').fill('test@example.com');
    await page.getByPlaceholder('비밀번호').fill('123');
    await page.getByRole('button', { name: '로그인' }).click();
    await expect(page.getByText('비밀번호는 6자 이상이어야 합니다')).toBeVisible();
  });

  test('should navigate between login and register pages', async ({ page }) => {
    await page.goto('/auth/login');
    
    // Navigate to register page
    await page.getByRole('link', { name: '새 계정 만들기' }).click();
    await expect(page).toHaveURL('/auth/register');
    await expect(page.getByRole('heading', { name: 'ScoreMate 회원가입' })).toBeVisible();
    
    // Navigate back to login page
    await page.getByRole('link', { name: '로그인하기' }).click();
    await expect(page).toHaveURL('/auth/login');
  });

  test('should validate register form', async ({ page }) => {
    await page.goto('/auth/register');
    
    // Try to submit empty form
    await page.getByRole('button', { name: '회원가입' }).click();
    
    // Check validation messages
    await expect(page.getByText('이메일을 입력해주세요')).toBeVisible();
    await expect(page.getByText('이름을 입력해주세요')).toBeVisible();
    await expect(page.getByText('비밀번호를 입력해주세요')).toBeVisible();
    await expect(page.getByText('비밀번호 확인을 입력해주세요')).toBeVisible();
    await expect(page.getByText('이용약관에 동의해주세요')).toBeVisible();
    
    // Test password mismatch
    await page.getByPlaceholder('your@email.com').fill('test@example.com');
    await page.getByPlaceholder('홍길동').fill('테스트');
    await page.getByPlaceholder('8자 이상').fill('password123');
    await page.getByPlaceholder('비밀번호 재입력').fill('different123');
    await page.getByRole('button', { name: '회원가입' }).click();
    await expect(page.getByText('비밀번호가 일치하지 않습니다')).toBeVisible();
  });
});

test.describe('Authenticated Pages', () => {
  test('should redirect to login when accessing protected pages', async ({ page }) => {
    const protectedPages = [
      '/dashboard',
      '/scores',
      '/scores/123',
      '/upload',
      '/setlists'
    ];
    
    for (const url of protectedPages) {
      await page.goto(url);
      await expect(page).toHaveURL('/auth/login');
    }
  });
});