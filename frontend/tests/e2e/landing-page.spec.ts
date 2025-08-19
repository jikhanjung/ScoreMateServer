import { test, expect } from '@playwright/test';

test.describe('Landing Page', () => {
  test('should display main landing page elements', async ({ page }) => {
    await page.goto('/');

    // 로딩 상태 확인 (AuthContext가 로딩 중일 수 있음)
    await expect(page.locator('body')).toBeVisible();

    // 메인 제목 확인
    await expect(page.locator('h1')).toContainText('ScoreMate');

    // 서브타이틀 확인 (첫 번째 p 태그 - hero section의 설명)
    await expect(page.locator('p').first()).toContainText('PDF 악보를 업로드하고 세트리스트를 관리하는');

    // 주요 버튼들 확인
    await expect(page.getByRole('button', { name: '무료로 시작하기' })).toBeVisible();
    // hero section의 로그인 버튼 (두 번째 로그인 버튼)
    await expect(page.getByRole('main').getByRole('button', { name: '로그인' })).toBeVisible();
  });

  test('should display main features section', async ({ page }) => {
    await page.goto('/');

    // 주요 기능 섹션 제목 확인
    await expect(page.locator('h2').first()).toContainText('주요 기능');

    // 4개의 주요 기능 카드 확인
    const featureCards = page.locator('div[class*="grid"] > div').filter({ hasText: /간편한 업로드|스마트 관리|세트리스트 구성|사용량 분석/ });
    await expect(featureCards).toHaveCount(4);

    // 각 기능의 제목 확인
    await expect(page.locator('h3').nth(0)).toContainText('간편한 업로드');
    await expect(page.locator('h3').nth(1)).toContainText('스마트 관리');
    await expect(page.locator('h3').nth(2)).toContainText('세트리스트 구성');
    await expect(page.locator('h3').nth(3)).toContainText('사용량 분석');
  });

  test('should display header navigation', async ({ page }) => {
    await page.goto('/');

    // 로고 확인 (헤더의 ScoreMate 로고)
    await expect(page.getByRole('banner').getByText('ScoreMate')).toBeVisible();

    // 비인증 사용자용 헤더 버튼 확인
    await expect(page.getByRole('banner').getByRole('button', { name: '로그인' })).toBeVisible();
    await expect(page.getByRole('banner').getByRole('button', { name: '회원가입' })).toBeVisible();
  });

  test('should display footer', async ({ page }) => {
    await page.goto('/');

    // 푸터 저작권 확인
    await expect(page.getByText('© 2024 ScoreMate. All rights reserved.')).toBeVisible();

    // 푸터 링크들 확인
    await expect(page.getByRole('link', { name: '개인정보처리방침' })).toBeVisible();
    await expect(page.getByRole('link', { name: '이용약관' })).toBeVisible();
    await expect(page.getByRole('link', { name: '고객지원' })).toBeVisible();
  });

  test('should be responsive on mobile', async ({ page }) => {
    // 모바일 뷰포트로 설정
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // 모바일에서도 주요 요소들이 보이는지 확인
    await expect(page.locator('h1')).toContainText('ScoreMate');
    await expect(page.getByRole('button', { name: '무료로 시작하기' })).toBeVisible();

    // 모바일에서는 숨겨진 텍스트가 있을 수 있음 (예: "로그아웃" 버튼의 텍스트)
    // 하지만 기본 기능은 모두 작동해야 함
  });
});