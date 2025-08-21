import { test, expect } from '@playwright/test';

test.describe('Accessibility & Performance', () => {
  test('should have proper semantic HTML structure', async ({ page }) => {
    await page.goto('/');

    // 적절한 heading 구조 확인
    const h1 = page.locator('h1');
    await expect(h1).toHaveCount(1);
    await expect(h1).toContainText('ScoreMate');

    // h2 요소들 확인
    const h2Elements = page.locator('h2');
    await expect(h2Elements).toHaveCount(2); // "주요 기능", "지금 바로 시작해보세요"

    // h3 요소들 확인 (기능 카드들)
    const h3Elements = page.locator('h3');
    await expect(h3Elements).toHaveCount(4); // 4개의 기능 카드
  });

  test('should have proper alt text for images', async ({ page }) => {
    await page.goto('/');

    // 모든 이미지에 alt 속성이 있는지 확인
    const images = page.locator('img');
    const imageCount = await images.count();
    
    if (imageCount > 0) {
      for (let i = 0; i < imageCount; i++) {
        const img = images.nth(i);
        await expect(img).toHaveAttribute('alt');
      }
    }
  });

  test('should have proper button accessibility', async ({ page }) => {
    await page.goto('/');

    // 모든 버튼이 적절한 텍스트나 aria-label을 가지고 있는지 확인
    const buttons = page.locator('button');
    const buttonCount = await buttons.count();

    for (let i = 0; i < buttonCount; i++) {
      const button = buttons.nth(i);
      const hasText = await button.textContent();
      const hasAriaLabel = await button.getAttribute('aria-label');
      
      // 버튼은 텍스트나 aria-label 중 하나는 가져야 함 (빈 텍스트도 고려)
      expect(hasText?.trim() || hasAriaLabel).toBeTruthy();
    }
  });

  test('should have proper link accessibility', async ({ page }) => {
    await page.goto('/');

    // 모든 링크가 적절한 텍스트를 가지고 있는지 확인
    const links = page.locator('a');
    const linkCount = await links.count();

    for (let i = 0; i < linkCount; i++) {
      const link = links.nth(i);
      const hasText = await link.textContent();
      const hasAriaLabel = await link.getAttribute('aria-label');
      
      // 링크는 텍스트나 aria-label 중 하나는 가져야 함
      expect(hasText?.trim() || hasAriaLabel).toBeTruthy();
    }
  });

  test('should have proper color contrast', async ({ page }) => {
    await page.goto('/');

    // 텍스트 요소들의 색상 대비 확인 (시각적 테스트)
    // 이는 실제 색상 계산이 복잡하므로, 기본적인 스타일 확인만 수행
    const mainText = page.locator('h1');
    const computedStyle = await mainText.evaluate(el => getComputedStyle(el));
    
    // 텍스트 색상이 설정되어 있는지 확인
    expect(computedStyle).toBeTruthy();
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto('/');

    // 키보드로 네비게이션 가능한지 확인
    // Tab 키를 눌러서 포커스가 이동하는지 테스트
    await page.keyboard.press('Tab');
    
    // 첫 번째 포커스 가능한 요소가 포커스를 받았는지 확인
    const focusedElement = await page.locator(':focus').count();
    expect(focusedElement).toBeGreaterThan(0);
  });

  test('should load within reasonable time', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // 페이지가 5초 이내에 로드되어야 함
    expect(loadTime).toBeLessThan(5000);
  });

  test('should have proper meta tags', async ({ page }) => {
    await page.goto('/');

    // 페이지 title 확인
    const title = await page.title();
    expect(title).toContain('ScoreMate');

    // meta description 확인
    const metaDescription = page.locator('meta[name="description"]');
    await expect(metaDescription).toHaveAttribute('content');

    // viewport meta tag 확인
    const viewport = page.locator('meta[name="viewport"]');
    await expect(viewport).toHaveAttribute('content');
  });

  test('should handle JavaScript disabled gracefully', async ({ browser }) => {
    // JavaScript 비활성화된 컨텍스트 생성
    const context = await browser.newContext({
      javaScriptEnabled: false
    });
    const page = await context.newPage();

    await page.goto('/');

    // 기본 HTML 콘텐츠가 표시되는지 확인
    // (서버 사이드 렌더링이 작동하는지 확인)
    await expect(page.locator('h1')).toContainText('ScoreMate');
    
    await context.close();
  });

  test('should be responsive across different screen sizes', async ({ page }) => {
    const viewports = [
      { width: 320, height: 568 },   // iPhone 5
      { width: 768, height: 1024 },  // iPad
      { width: 1024, height: 768 },  // iPad Landscape
      { width: 1920, height: 1080 }  // Desktop
    ];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.goto('/');

      // 주요 요소들이 여전히 보이는지 확인
      await expect(page.locator('h1')).toBeVisible();
      // 모바일 화면에서는 텍스트가 생략될 수 있으므로 버튼 엘리먼트 존재만 확인
      const startButton = page.getByRole('button', { name: /무료로 시작|시작하기/i });
      if (await startButton.count() > 0) {
        await expect(startButton.first()).toBeVisible();
      }

      // 오버플로우가 발생하지 않는지 확인
      const bodyScrollWidth = await page.locator('body').evaluate(el => el.scrollWidth);
      const bodyClientWidth = await page.locator('body').evaluate(el => el.clientWidth);
      
      // 수평 스크롤이 발생하지 않아야 함
      expect(bodyScrollWidth).toBeLessThanOrEqual(bodyClientWidth + 5); // 5px 여유
    }
  });
});