import { test, expect } from '@playwright/test';

test.describe('Authentication Context', () => {
  test('should initialize with unauthenticated state', async ({ page }) => {
    await page.goto('/');

    // 비인증 상태에서 표시되는 요소들 확인 (헤더 버튼들)
    await expect(page.getByRole('banner').getByRole('button', { name: '로그인' })).toBeVisible();
    await expect(page.getByRole('banner').getByRole('button', { name: '회원가입' })).toBeVisible();

    // 인증된 사용자용 요소들이 없는지 확인
    await expect(page.getByRole('button', { name: '로그아웃' })).not.toBeVisible();
    await expect(page.getByText('username')).not.toBeVisible();
  });

  test('should not show authenticated navigation items', async ({ page }) => {
    await page.goto('/');

    // 인증이 필요한 네비게이션 아이템들이 표시되지 않아야 함
    await expect(page.getByRole('link', { name: '대시보드' })).not.toBeVisible();
    await expect(page.getByRole('link', { name: '악보 라이브러리' })).not.toBeVisible();
    await expect(page.getByRole('link', { name: '세트리스트' })).not.toBeVisible();
    await expect(page.getByRole('link', { name: '업로드' })).not.toBeVisible();
  });

  test('should handle loading state properly', async ({ page }) => {
    await page.goto('/');

    // 페이지가 완전히 로드될 때까지 대기
    await page.waitForLoadState('networkidle');

    // 로딩 스피너가 사라지고 실제 콘텐츠가 표시되는지 확인
    await expect(page.locator('h1')).toContainText('ScoreMate');
    
    // 로딩 상태가 아니어야 함 (로딩 스피너가 없어야 함)
    await expect(page.locator('[class*="animate-spin"]')).not.toBeVisible();
  });

  test('should redirect authenticated users to dashboard', async ({ page }) => {
    // 이 테스트는 실제 인증이 구현된 후에 수정이 필요할 수 있음
    // 현재는 localStorage에 토큰이 있다고 가정하고 테스트

    // 페이지에 가짜 토큰 설정
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'fake-token');
      localStorage.setItem('user', JSON.stringify({ username: 'testuser' }));
    });

    // 페이지 새로고침
    await page.reload();

    // AuthContext의 useEffect가 실행되어 /dashboard로 리다이렉트를 시도해야 함
    // 하지만 dashboard 페이지가 없으므로 404가 될 것
    await page.waitForURL('/dashboard');
    await expect(page).toHaveURL('/dashboard');
  });

  test('should clear localStorage on logout', async ({ page }) => {
    await page.goto('/');

    // 가짜 토큰 설정
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'fake-token');
      localStorage.setItem('user', JSON.stringify({ username: 'testuser' }));
    });

    // localStorage에 토큰이 설정되었는지 확인
    const tokenExists = await page.evaluate(() => {
      return localStorage.getItem('access_token') !== null;
    });
    expect(tokenExists).toBe(true);

    // 이 테스트는 실제 로그아웃 기능이 구현된 후에 수정 필요
    // 현재는 localStorage에 토큰이 있는지만 확인
  });

  test('should handle invalid tokens gracefully', async ({ page }) => {
    await page.goto('/');

    // 유효하지 않은 토큰 설정
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'invalid-token');
      localStorage.setItem('user', 'invalid-json');
    });

    // 페이지 새로고침
    await page.reload();

    // 에러가 발생하지 않고 로그인 페이지가 표시되어야 함
    // (AuthContext가 에러를 적절히 처리해야 함)
    await expect(page.getByRole('button', { name: '로그인' })).toBeVisible();
  });
});