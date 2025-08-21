import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('should attempt to navigate to register page when clicking signup button', async ({ page }) => {
    await page.goto('/');

    // 회원가입 버튼 클릭
    await page.getByRole('button', { name: '무료로 시작하기' }).click();

    // /auth/register 페이지로 이동을 시도했는지 확인 (현재는 404가 될 것)
    await expect(page).toHaveURL('/auth/register');
  });

  test('should attempt to navigate to login page when clicking login button', async ({ page }) => {
    await page.goto('/');

    // 헤더의 로그인 버튼 클릭 (첫 번째 로그인 버튼 - 헤더에 있는 것)
    await page.getByRole('banner').getByRole('button', { name: '로그인' }).click();

    // /auth/login 페이지로 이동을 시도했는지 확인 (현재는 404가 될 것)
    await expect(page).toHaveURL('/auth/login');
  });

  test('should attempt to navigate to register from CTA section', async ({ page }) => {
    await page.goto('/');

    // CTA 섹션의 회원가입 버튼 클릭
    await page.getByRole('button', { name: '무료 계정 만들기' }).click();

    // /auth/register 페이지로 이동을 시도했는지 확인
    await expect(page).toHaveURL('/auth/register');
  });

  test('should show 404 for non-existent auth pages', async ({ page }) => {
    // 직접 로그인 페이지로 이동 시도 (아직 구현되지 않음)
    await page.goto('/auth/login');
    
    // Next.js 기본 404 페이지 또는 not-found 페이지가 표시되어야 함
    // 404 페이지나 에러 메시지가 있어야 함
    await expect(page.locator('body')).toContainText(/404|Not Found|This page could not be found/i);
  });

  test('should show 404 for non-existent register page', async ({ page }) => {
    // 직접 회원가입 페이지로 이동 시도 (아직 구현되지 않음)  
    await page.goto('/auth/register');
    
    // Next.js 기본 404 페이지 또는 not-found 페이지가 표시되어야 함
    // 404 페이지나 에러 메시지가 있어야 함
    await expect(page.locator('body')).toContainText(/404|Not Found|This page could not be found/i);
  });

  test('should navigate footer links', async ({ page }) => {
    await page.goto('/');

    // 푸터 링크들이 올바른 href를 가지고 있는지 확인
    await expect(page.getByRole('link', { name: '개인정보처리방침' })).toHaveAttribute('href', '/privacy');
    await expect(page.getByRole('link', { name: '이용약관' })).toHaveAttribute('href', '/terms');
    await expect(page.getByRole('link', { name: '고객지원' })).toHaveAttribute('href', '/support');
  });

  test('should have correct logo link behavior', async ({ page }) => {
    await page.goto('/');

    // 로고 클릭 시 홈으로 이동하는지 확인
    const logo = page.locator('a').filter({ hasText: 'ScoreMate' }).first();
    await expect(logo).toHaveAttribute('href', '/');
  });
});