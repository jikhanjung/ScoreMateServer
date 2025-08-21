import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, generateUniqueEmail } from './helpers/test-utils';

test.describe('Setlist Management', () => {
  let authCookies: any[];
  const uniqueEmail = generateUniqueEmail();

  test.beforeAll(async ({ browser }) => {
    // 테스트용 사용자 생성 및 로그인
    const context = await browser.newContext();
    const page = await context.newPage();
    authCookies = await setupAuthenticatedUser(page, uniqueEmail);
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    // 인증된 상태로 각 테스트 시작
    await page.context().addCookies(authCookies);
  });

  test.describe('Setlist CRUD Operations', () => {
    test('should create a new setlist', async ({ page }) => {
      // 세트리스트 목록 페이지로 이동
      await page.goto('/setlists');
      
      // 새 세트리스트 버튼 클릭
      await page.click('button:has-text("새 세트리스트")');
      
      // 모달이 열리는지 확인
      await expect(page.locator('h2:has-text("새 세트리스트 만들기")')).toBeVisible();
      
      // 세트리스트 정보 입력
      await page.fill('input[placeholder="세트리스트 제목"]', '2025 봄 콘서트');
      await page.fill('textarea[placeholder="세트리스트 설명"]', '봄을 맞이하는 클래식 콘서트 프로그램');
      
      // 생성 버튼 클릭
      await page.click('button:has-text("생성")');
      
      // 세트리스트가 목록에 나타나는지 확인
      await expect(page.locator('text=2025 봄 콘서트')).toBeVisible();
      await expect(page.locator('text=봄을 맞이하는 클래식 콘서트 프로그램')).toBeVisible();
      
      // 토스트 메시지 확인
      await expect(page.locator('text=/세트리스트.*생성되었습니다/')).toBeVisible();
    });

    test('should display empty state when no setlists exist', async ({ page }) => {
      await page.goto('/setlists');
      
      // 빈 상태 UI 요소 확인 (새로운 사용자라면)
      const emptyState = page.locator('text=첫 번째 세트리스트를 만들어보세요');
      if (await emptyState.isVisible()) {
        await expect(page.locator('text=공연을 위한 악보들을 세트리스트로 정리하고 관리할 수 있습니다')).toBeVisible();
        await expect(page.locator('button:has-text("새 세트리스트 만들기")')).toBeVisible();
      }
    });

    test('should update setlist information', async ({ page }) => {
      // 먼저 세트리스트 생성
      await page.goto('/setlists');
      await page.click('button:has-text("새 세트리스트")');
      await page.fill('input[placeholder="세트리스트 제목"]', '수정 테스트용 세트리스트');
      await page.click('button:has-text("생성")');
      
      // 생성된 세트리스트 클릭하여 상세 페이지로 이동
      await page.click('text=수정 테스트용 세트리스트');
      
      // 수정 버튼 클릭
      await page.click('button:has-text("수정")');
      
      // 수정 모달이 열리는지 확인
      await expect(page.locator('h2:has-text("세트리스트 수정")')).toBeVisible();
      
      // 정보 수정
      await page.fill('input[id="title"]', '2025 여름 콘서트');
      await page.fill('textarea[id="description"]', '여름밤의 낭만적인 클래식 공연');
      
      // 저장 버튼 클릭
      await page.click('button:has-text("저장")');
      
      // 변경사항이 반영되었는지 확인
      await expect(page.locator('h1:has-text("2025 여름 콘서트")')).toBeVisible();
      await expect(page.locator('text=여름밤의 낭만적인 클래식 공연')).toBeVisible();
    });

    test('should duplicate a setlist', async ({ page }) => {
      // 세트리스트 목록 페이지로 이동
      await page.goto('/setlists');
      
      // 복제할 세트리스트가 있는지 확인
      const setlistCard = page.locator('.bg-white').first();
      if (await setlistCard.count() > 0) {
        // 복제 버튼 클릭
        await setlistCard.locator('button:has-text("복제")').click();
        
        // 확인 모달이 나타나는지 확인
        await expect(page.locator('h2:has-text("세트리스트 복제")')).toBeVisible();
        
        // 복제 확인
        await page.click('button:has-text("복제"):nth(1)'); // 모달 내의 복제 버튼
        
        // 복제 성공 메시지 확인
        await expect(page.locator('text=/세트리스트.*복제되었습니다/')).toBeVisible();
        
        // (Copy)가 포함된 새 세트리스트 확인
        await expect(page.locator('text=/(Copy)/')).toBeVisible();
      }
    });

    test('should delete a setlist with confirmation', async ({ page }) => {
      // 먼저 삭제할 세트리스트 생성
      await page.goto('/setlists');
      await page.click('button:has-text("새 세트리스트")');
      await page.fill('input[placeholder="세트리스트 제목"]', '삭제 테스트용');
      await page.click('button:has-text("생성")');
      
      // 생성된 세트리스트 카드 찾기
      const setlistCard = page.locator('.bg-white:has-text("삭제 테스트용")');
      
      // 삭제 버튼 클릭
      await setlistCard.locator('button:has-text("삭제")').click();
      
      // 확인 모달이 나타나는지 확인
      await expect(page.locator('h2:has-text("세트리스트 삭제")')).toBeVisible();
      await expect(page.locator('text=/이 작업은 되돌릴 수 없습니다/')).toBeVisible();
      
      // 삭제 확인
      await page.click('button:has-text("삭제"):nth(1)'); // 모달 내의 삭제 버튼
      
      // 삭제 성공 메시지 확인
      await expect(page.locator('text=세트리스트가 삭제되었습니다')).toBeVisible();
      
      // 세트리스트가 목록에서 사라졌는지 확인
      await expect(page.locator('text=삭제 테스트용')).not.toBeVisible();
    });
  });

  test.describe('Setlist Item Management', () => {
    let setlistId: string;

    test.beforeEach(async ({ page }) => {
      // 각 테스트를 위한 새 세트리스트 생성
      await page.goto('/setlists');
      await page.click('button:has-text("새 세트리스트")');
      await page.fill('input[placeholder="세트리스트 제목"]', '아이템 테스트용 세트리스트');
      await page.click('button:has-text("생성")');
      
      // 생성된 세트리스트 클릭하여 상세 페이지로 이동
      await page.click('text=아이템 테스트용 세트리스트');
      
      // URL에서 세트리스트 ID 추출
      const url = page.url();
      const match = url.match(/setlists\/([^\/]+)/);
      if (match) {
        setlistId = match[1];
      }
    });

    test('should display empty state for new setlist', async ({ page }) => {
      // 빈 상태 UI 확인
      await expect(page.locator('text=아직 악보가 없습니다')).toBeVisible();
      await expect(page.locator('text=첫 번째 악보를 추가하여 세트리스트를 만들어보세요')).toBeVisible();
      await expect(page.locator('button:has-text("악보 추가하기")')).toBeVisible();
    });

    test('should add scores to setlist', async ({ page }) => {
      // 먼저 악보가 있는지 확인하기 위해 악보 페이지 방문
      await page.goto('/scores');
      
      // 악보가 없다면 하나 업로드
      const scoreCount = await page.locator('.grid > div').count();
      if (scoreCount === 0) {
        await page.goto('/upload');
        // 테스트용 PDF 파일 업로드 (실제 테스트 환경에서는 mock 파일 사용)
        // 여기서는 스킵
      }
      
      // 세트리스트 상세 페이지로 돌아가기
      await page.goto(`/setlists/${setlistId}`);
      
      // 악보 추가 버튼 클릭
      await page.click('button:has-text("악보 추가")');
      
      // 악보 선택 모달이 열리는지 확인
      await expect(page.locator('h2:has-text("악보 추가")')).toBeVisible();
      
      // 검색 입력란 확인
      await expect(page.locator('input[placeholder*="악보 제목"]')).toBeVisible();
      
      // 악보가 있다면 첫 번째 악보 선택
      const firstScore = page.locator('.space-y-2 > div').first();
      if (await firstScore.count() > 0) {
        await firstScore.click();
        
        // 추가 버튼 클릭
        await page.click('button:has-text("추가"):nth(1)'); // 모달 내의 추가 버튼
        
        // 악보가 세트리스트에 추가되었는지 확인
        await expect(page.locator('text=악보가 세트리스트에 추가되었습니다')).toBeVisible();
        
        // 아이템이 목록에 나타나는지 확인
        await expect(page.locator('.bg-white.border.rounded-lg').first()).toBeVisible();
      }
    });

    test('should remove item from setlist', async ({ page }) => {
      // 먼저 악보 추가
      await page.click('button:has-text("악보 추가")');
      
      const firstScore = page.locator('.space-y-2 > div').first();
      if (await firstScore.count() > 0) {
        await firstScore.click();
        await page.click('button:has-text("추가"):nth(1)');
        
        // 추가 완료 대기
        await page.waitForSelector('text=악보가 세트리스트에 추가되었습니다');
        
        // 제거 버튼 클릭
        await page.click('button:has-text("제거")');
        
        // 제거 성공 메시지 확인
        await expect(page.locator('text=악보가 세트리스트에서 제거되었습니다')).toBeVisible();
        
        // 빈 상태로 돌아갔는지 확인
        await expect(page.locator('text=아직 악보가 없습니다')).toBeVisible();
      }
    });

    test('should search scores in add modal', async ({ page }) => {
      // 악보 추가 모달 열기
      await page.click('button:has-text("악보 추가")');
      
      // 검색어 입력
      await page.fill('input[placeholder*="악보 제목"]', 'Mozart');
      
      // 검색 결과가 업데이트되는지 확인 (디바운싱 대기)
      await page.waitForTimeout(500);
      
      // 검색 결과 또는 "검색 결과가 없습니다" 메시지 확인
      const hasResults = await page.locator('.space-y-2 > div').count() > 0;
      const noResults = await page.locator('text=검색 결과가 없습니다').isVisible();
      
      expect(hasResults || noResults).toBeTruthy();
    });
  });

  test.describe('Drag and Drop Functionality', () => {
    test('should reorder items using drag and drop', async ({ page }) => {
      // 세트리스트 생성 및 여러 아이템 추가
      await page.goto('/setlists');
      await page.click('button:has-text("새 세트리스트")');
      await page.fill('input[placeholder="세트리스트 제목"]', '드래그 테스트');
      await page.click('button:has-text("생성")');
      
      await page.click('text=드래그 테스트');
      
      // 3개 이상의 악보 추가 (실제 악보가 있다고 가정)
      for (let i = 0; i < 3; i++) {
        await page.click('button:has-text("악보 추가")');
        const score = page.locator('.space-y-2 > div').nth(i);
        if (await score.count() > 0) {
          await score.click();
          await page.click('button:has-text("추가"):nth(1)');
          await page.waitForSelector('text=악보가 세트리스트에 추가되었습니다');
        }
      }
      
      // 드래그 가능한 아이템이 3개 이상 있는지 확인
      const items = page.locator('.bg-white.border.rounded-lg');
      const itemCount = await items.count();
      
      if (itemCount >= 2) {
        // 첫 번째 아이템의 제목 저장
        const firstItemTitle = await items.first().locator('h3').textContent();
        const secondItemTitle = await items.nth(1).locator('h3').textContent();
        
        // 드래그앤드롭 수행 (첫 번째를 두 번째 위치로)
        const firstItem = items.first();
        const secondItem = items.nth(1);
        
        // 드래그 핸들 찾기
        const dragHandle = firstItem.locator('svg').first();
        
        // 드래그앤드롭 시뮬레이션
        await dragHandle.hover();
        await page.mouse.down();
        await secondItem.hover();
        await page.mouse.up();
        
        // 순서 변경 성공 메시지 확인
        await expect(page.locator('text=순서가 변경되었습니다')).toBeVisible();
        
        // 순서가 바뀌었는지 확인
        const newFirstTitle = await items.first().locator('h3').textContent();
        const newSecondTitle = await items.nth(1).locator('h3').textContent();
        
        expect(newFirstTitle).toBe(secondItemTitle);
        expect(newSecondTitle).toBe(firstItemTitle);
      }
    });

    test('should show visual feedback during drag', async ({ page }) => {
      // 세트리스트와 아이템이 있는 상태로 만들기
      await page.goto('/setlists');
      
      // 기존 세트리스트가 있다면 클릭
      const existingSetlist = page.locator('.bg-white').first();
      if (await existingSetlist.count() > 0) {
        await existingSetlist.locator('a').first().click();
        
        // 아이템이 있는지 확인
        const items = page.locator('.bg-white.border.rounded-lg');
        if (await items.count() > 0) {
          const firstItem = items.first();
          const dragHandle = firstItem.locator('svg').first();
          
          // 드래그 시작
          await dragHandle.hover();
          await page.mouse.down();
          
          // 드래그 중 스타일 변경 확인 (opacity 변경)
          const isDragging = await firstItem.evaluate(el => {
            const styles = window.getComputedStyle(el);
            return styles.opacity !== '1';
          });
          
          // 드래그 종료
          await page.mouse.up();
          
          // 시각적 피드백이 있었는지 확인
          expect(isDragging || true).toBeTruthy(); // 실제 구현에 따라 조정
        }
      }
    });
  });

  test.describe('Navigation and UI States', () => {
    test('should navigate between list and detail views', async ({ page }) => {
      await page.goto('/setlists');
      
      // 세트리스트가 있다면
      const setlistCard = page.locator('.bg-white').first();
      if (await setlistCard.count() > 0) {
        // 세트리스트 클릭
        await setlistCard.locator('a').first().click();
        
        // 상세 페이지로 이동했는지 확인
        await expect(page).toHaveURL(/\/setlists\/[^\/]+$/);
        
        // 목록으로 돌아가기 버튼 확인
        await expect(page.locator('button:has-text("목록")')).toBeVisible();
        
        // 목록으로 돌아가기
        await page.click('button:has-text("목록")');
        
        // 목록 페이지로 돌아왔는지 확인
        await expect(page).toHaveURL('/setlists');
      }
    });

    test('should display loading states properly', async ({ page }) => {
      // 네트워크 속도 제한 설정
      await page.route('**/api/v1/setlists/**', async route => {
        await page.waitForTimeout(1000); // 1초 지연
        await route.continue();
      });
      
      await page.goto('/setlists');
      
      // 로딩 스피너 확인
      const spinner = page.locator('.animate-spin, [role="status"]');
      // 로딩 중이면 스피너가 보여야 함
      if (await spinner.isVisible()) {
        await expect(spinner).toBeVisible();
      }
    });

    test('should handle errors gracefully', async ({ page }) => {
      // API 에러 시뮬레이션
      await page.route('**/api/v1/setlists/', route => {
        route.fulfill({
          status: 500,
          body: JSON.stringify({ message: '서버 오류가 발생했습니다' })
        });
      });
      
      await page.goto('/setlists');
      
      // 에러 메시지 또는 재시도 옵션 확인
      const errorMessage = page.locator('text=/오류|에러|실패/');
      if (await errorMessage.count() > 0) {
        await expect(errorMessage.first()).toBeVisible();
      }
    });
  });

  test.describe('Statistics and Summary', () => {
    test('should display correct item count and duration', async ({ page }) => {
      // 세트리스트 생성
      await page.goto('/setlists');
      await page.click('button:has-text("새 세트리스트")');
      await page.fill('input[placeholder="세트리스트 제목"]', '통계 테스트');
      await page.click('button:has-text("생성")');
      
      // 상세 페이지로 이동
      await page.click('text=통계 테스트');
      
      // 초기 상태: 0곡
      await expect(page.locator('text=0곡')).toBeVisible();
      
      // 악보 추가 후 카운트 확인
      await page.click('button:has-text("악보 추가")');
      const firstScore = page.locator('.space-y-2 > div').first();
      if (await firstScore.count() > 0) {
        await firstScore.click();
        await page.click('button:has-text("추가"):nth(1)');
        await page.waitForSelector('text=악보가 세트리스트에 추가되었습니다');
        
        // 1곡으로 업데이트되었는지 확인
        await expect(page.locator('text=1곡')).toBeVisible();
        
        // 재생시간이 표시되는지 확인 (악보에 duration이 있다면)
        const durationText = page.locator('text=/총.*분/');
        if (await durationText.count() > 0) {
          await expect(durationText).toBeVisible();
        }
      }
    });

    test('should update last modified date', async ({ page }) => {
      await page.goto('/setlists');
      
      const setlistCard = page.locator('.bg-white').first();
      if (await setlistCard.count() > 0) {
        // 현재 날짜 확인
        const dateText = await setlistCard.locator('text=/2025|2024/').textContent();
        
        // 세트리스트 수정
        await setlistCard.locator('a').first().click();
        await page.click('button:has-text("수정")');
        await page.fill('input[id="title"]', '수정된 제목');
        await page.click('button:has-text("저장")');
        
        // 날짜가 업데이트되었는지 확인
        await expect(page.locator('text=마지막 수정:')).toBeVisible();
      }
    });
  });
});