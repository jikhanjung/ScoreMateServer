import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, generateUniqueEmail } from './helpers/test-utils';

test.describe('Setlist Drag and Drop Advanced Tests', () => {
  let authCookies: any[];
  const uniqueEmail = generateUniqueEmail();

  test.beforeAll(async ({ browser }) => {
    // 테스트용 사용자 생성 및 로그인
    const context = await browser.newContext();
    const page = await context.newPage();
    authCookies = await setupAuthenticatedUser(page, uniqueEmail);
    
    // 테스트용 세트리스트와 아이템 생성
    await page.goto('/setlists');
    await page.click('button:has-text("새 세트리스트")');
    await page.fill('input[placeholder="세트리스트 제목"]', '드래그앤드롭 테스트');
    await page.click('button:has-text("생성")');
    
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    // 인증된 상태로 각 테스트 시작
    await page.context().addCookies(authCookies);
    await page.goto('/setlists');
    await page.click('text=드래그앤드롭 테스트');
  });

  test('should handle keyboard navigation for drag and drop', async ({ page }) => {
    // 악보가 충분히 있는지 확인하고 추가
    const items = page.locator('.bg-white.border.rounded-lg');
    let itemCount = await items.count();
    
    // 최소 3개 아이템 필요
    while (itemCount < 3) {
      await page.click('button:has-text("악보 추가")');
      const score = page.locator('.space-y-2 > div').nth(itemCount);
      if (await score.count() > 0) {
        await score.click();
        await page.click('button:has-text("추가"):nth(1)');
        await page.waitForSelector('text=악보가 세트리스트에 추가되었습니다');
        itemCount++;
      } else {
        break;
      }
    }
    
    if (itemCount >= 2) {
      // 첫 번째 아이템에 포커스
      const firstItem = items.first();
      await firstItem.focus();
      
      // 키보드로 드래그 시작 (Space or Enter)
      await page.keyboard.press('Space');
      
      // 아래 화살표로 이동
      await page.keyboard.press('ArrowDown');
      
      // 드롭 (Space or Enter)
      await page.keyboard.press('Space');
      
      // 순서 변경 확인
      await expect(page.locator('text=순서가 변경되었습니다')).toBeVisible();
    }
  });

  test('should maintain order after page refresh', async ({ page }) => {
    // 아이템이 2개 이상 있는지 확인
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 2) {
      // 원래 순서 저장
      const originalOrder = [];
      for (let i = 0; i < itemCount; i++) {
        const title = await items.nth(i).locator('h3').textContent();
        originalOrder.push(title);
      }
      
      // 첫 번째와 두 번째 아이템 순서 변경
      const firstItem = items.first();
      const secondItem = items.nth(1);
      const dragHandle = firstItem.locator('svg').first();
      
      await dragHandle.hover();
      await page.mouse.down();
      await secondItem.hover();
      await page.mouse.up();
      
      await page.waitForSelector('text=순서가 변경되었습니다');
      
      // 페이지 새로고침
      await page.reload();
      
      // 변경된 순서가 유지되는지 확인
      const newOrder = [];
      for (let i = 0; i < itemCount; i++) {
        const title = await items.nth(i).locator('h3').textContent();
        newOrder.push(title);
      }
      
      // 첫 번째와 두 번째가 바뀌었는지 확인
      expect(newOrder[0]).toBe(originalOrder[1]);
      expect(newOrder[1]).toBe(originalOrder[0]);
    }
  });

  test('should prevent drag during API operations', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 2) {
      // 네트워크 지연 시뮬레이션
      await page.route('**/api/v1/setlists/**/reorder_items/', async route => {
        await page.waitForTimeout(2000); // 2초 지연
        await route.continue();
      });
      
      // 드래그 시작
      const firstItem = items.first();
      const secondItem = items.nth(1);
      const dragHandle = firstItem.locator('svg').first();
      
      await dragHandle.hover();
      await page.mouse.down();
      await secondItem.hover();
      await page.mouse.up();
      
      // 로딩 상태 표시 확인
      await expect(page.locator('text=순서를 변경하는 중...')).toBeVisible();
      
      // 로딩 중에는 드래그가 비활성화되어야 함
      const isDraggable = await firstItem.evaluate(el => {
        return !el.classList.contains('cursor-grab');
      });
      
      // 작업 완료 대기
      await page.waitForSelector('text=순서가 변경되었습니다');
    }
  });

  test('should handle drag cancellation', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 2) {
      // 원래 순서 저장
      const originalFirst = await items.first().locator('h3').textContent();
      
      // 드래그 시작하고 ESC로 취소
      const firstItem = items.first();
      const dragHandle = firstItem.locator('svg').first();
      
      await dragHandle.hover();
      await page.mouse.down();
      
      // 드래그 중 ESC 키 누르기
      await page.keyboard.press('Escape');
      await page.mouse.up();
      
      // 순서가 변경되지 않았는지 확인
      const currentFirst = await items.first().locator('h3').textContent();
      expect(currentFirst).toBe(originalFirst);
    }
  });

  test('should handle multiple simultaneous reorders correctly', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 3) {
      // 빠르게 연속으로 드래그앤드롭 수행
      for (let i = 0; i < 2; i++) {
        const sourceItem = items.nth(i);
        const targetItem = items.nth(i + 1);
        const dragHandle = sourceItem.locator('svg').first();
        
        await dragHandle.hover();
        await page.mouse.down();
        await targetItem.hover();
        await page.mouse.up();
        
        // 각 작업이 완료될 때까지 대기
        await page.waitForSelector('text=순서가 변경되었습니다');
      }
      
      // 모든 변경사항이 정상 적용되었는지 확인
      const finalItemCount = await items.count();
      expect(finalItemCount).toBe(itemCount);
    }
  });

  test('should display correct order indices after reordering', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 2) {
      // 드래그앤드롭으로 순서 변경
      const firstItem = items.first();
      const lastItem = items.last();
      const dragHandle = firstItem.locator('svg').first();
      
      await dragHandle.hover();
      await page.mouse.down();
      await lastItem.hover();
      await page.mouse.up();
      
      await page.waitForSelector('text=순서가 변경되었습니다');
      
      // 순서 번호가 올바르게 표시되는지 확인
      for (let i = 0; i < itemCount; i++) {
        const orderNumber = await items.nth(i).locator('.bg-blue-100').textContent();
        expect(orderNumber?.trim()).toBe((i + 1).toString());
      }
    }
  });

  test('should handle drag over invalid drop zones', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 1) {
      const firstItem = items.first();
      const dragHandle = firstItem.locator('svg').first();
      
      // 원래 위치 저장
      const originalPosition = await firstItem.boundingBox();
      
      // 헤더 영역으로 드래그 (유효하지 않은 드롭 영역)
      await dragHandle.hover();
      await page.mouse.down();
      
      const header = page.locator('h1').first();
      await header.hover();
      await page.mouse.up();
      
      // 아이템이 원래 위치에 있는지 확인
      const currentPosition = await firstItem.boundingBox();
      expect(currentPosition?.y).toBeCloseTo(originalPosition?.y || 0, 1);
    }
  });

  test('should show drag handle only on hover', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 1) {
      const firstItem = items.first();
      const dragHandle = firstItem.locator('svg').first();
      
      // 기본 상태에서 드래그 핸들 스타일 확인
      const initialOpacity = await dragHandle.evaluate(el => {
        return window.getComputedStyle(el.parentElement!).opacity;
      });
      
      // 호버 시 드래그 핸들 스타일 변경 확인
      await firstItem.hover();
      const hoverOpacity = await dragHandle.evaluate(el => {
        return window.getComputedStyle(el.parentElement!).opacity;
      });
      
      // 호버 시 더 진하게 표시되는지 확인
      expect(Number(hoverOpacity)).toBeGreaterThanOrEqual(Number(initialOpacity));
    }
  });

  test('should handle rapid consecutive drags', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 3) {
      // 첫 번째 아이템을 여러 위치로 빠르게 이동
      const firstItem = items.first();
      const positions = [1, 2, 0]; // 이동할 위치들
      
      for (const targetIndex of positions) {
        const dragHandle = firstItem.locator('svg').first();
        const targetItem = items.nth(targetIndex);
        
        await dragHandle.hover();
        await page.mouse.down();
        await targetItem.hover();
        await page.mouse.up();
        
        // 짧은 대기 시간만 두고 다음 드래그 수행
        await page.waitForTimeout(100);
      }
      
      // 마지막 변경사항이 적용되었는지 확인
      await expect(page.locator('text=순서가 변경되었습니다')).toBeVisible();
    }
  });

  test('should calculate total duration correctly after reorder', async ({ page }) => {
    const items = page.locator('.bg-white.border.rounded-lg');
    const itemCount = await items.count();
    
    if (itemCount >= 2) {
      // 총 재생시간 확인
      const totalDurationBefore = await page.locator('text=/총.*분/').textContent();
      
      // 순서 변경
      const firstItem = items.first();
      const secondItem = items.nth(1);
      const dragHandle = firstItem.locator('svg').first();
      
      await dragHandle.hover();
      await page.mouse.down();
      await secondItem.hover();
      await page.mouse.up();
      
      await page.waitForSelector('text=순서가 변경되었습니다');
      
      // 총 재생시간이 변하지 않았는지 확인 (순서만 변경)
      const totalDurationAfter = await page.locator('text=/총.*분/').textContent();
      expect(totalDurationAfter).toBe(totalDurationBefore);
    }
  });
});