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

    // 주요 기능 섹션 제목 확인 (더 구체적인 셀렉터 사용)
    await expect(page.getByText('주요 기능')).toBeVisible();

    // 4개의 주요 기능 타이틀 확인
    await expect(page.getByText('간편한 업로드')).toBeVisible();
    await expect(page.getByText('스마트 관리')).toBeVisible();
    await expect(page.getByText('세트리스트 구성')).toBeVisible();
    await expect(page.getByText('사용량 분석')).toBeVisible();

    // 기능 설명 텍스트 확인
    await expect(page.getByText('드래그 앤 드롭으로 PDF 악보를 쉽게 업로드하세요')).toBeVisible();
    await expect(page.getByText('태그와 검색으로 악보를 체계적으로 정리하고 찾아보세요')).toBeVisible();
    await expect(page.getByText('연주할 곡들을 세트리스트로 구성하고 순서를 정하세요')).toBeVisible();
    await expect(page.getByText('라이브러리 현황과 저장 공간 사용량을 한눈에 확인하세요')).toBeVisible();
  });

  test('should display header navigation', async ({ page }) => {
    await page.goto('/');

    // 로고 확인 (헤더의 ScoreMate 로고)
    await expect(page.locator('header').getByText('ScoreMate')).toBeVisible();

    // 비인증 사용자용 헤더 버튼 확인
    await expect(page.locator('header').getByRole('button', { name: '로그인' })).toBeVisible();
    await expect(page.locator('header').getByRole('button', { name: '회원가입' })).toBeVisible();
  });

  test('should display footer', async ({ page }) => {
    await page.goto('/');

    // 푸터 저작권 확인
    await expect(page.getByText('© 2025 ScoreMate. All rights reserved.')).toBeVisible();

    // 푸터 링크들 확인
    await expect(page.getByRole('link', { name: '개인정보처리방침' })).toBeVisible();
    await expect(page.getByRole('link', { name: '이용약관' })).toBeVisible();
    await expect(page.getByRole('link', { name: '고객지원' })).toBeVisible();
  });

  test('should be responsive on mobile', async ({ page }) => {
    // 모바일 뷰포트로 설정
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // 페이지 로딩 대기
    await page.waitForLoadState('networkidle');

    // 모바일에서도 주요 요소들이 보이는지 확인
    await expect(page.getByText('ScoreMate').first()).toBeVisible();
    await expect(page.getByRole('button', { name: '무료로 시작하기' })).toBeVisible();

    // 헤더가 모바일에서도 보이는지 확인
    await expect(page.locator('header').getByText('ScoreMate')).toBeVisible();
  });
});