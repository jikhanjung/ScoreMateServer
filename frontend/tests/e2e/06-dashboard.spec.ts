import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authentication by setting localStorage
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock_token');
      localStorage.setItem('refresh_token', 'mock_refresh_token');
    });
    
    // Mock API responses
    await page.route('**/api/dashboard/stats/', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_scores: 10,
          total_setlists: 3,
          used_storage_mb: 25.5,
          uploads_this_month: 5
        })
      });
    });
    
    await page.route('**/api/scores/*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            {
              id: '1',
              title: 'Test Score 1',
              composer: 'Composer A',
              file_size: 1024000,
              created_at: new Date().toISOString()
            },
            {
              id: '2',
              title: 'Test Score 2',
              composer: 'Composer B',
              file_size: 2048000,
              created_at: new Date().toISOString()
            }
          ]
        })
      });
    });
    
    await page.route('**/api/auth/me/', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '1',
          email: 'test@example.com',
          name: '테스트 사용자'
        })
      });
    });
  });

  test('should display dashboard stats', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Check header
    await expect(page.getByText('안녕하세요')).toBeVisible();
    
    // Check stats cards
    await expect(page.getByText('총 악보')).toBeVisible();
    await expect(page.getByText('10')).toBeVisible();
    
    await expect(page.getByText('세트리스트')).toBeVisible();
    await expect(page.getByText('3')).toBeVisible();
    
    await expect(page.getByText('사용 용량')).toBeVisible();
    await expect(page.getByText('25.5 MB')).toBeVisible();
    
    await expect(page.getByText('이번 달 업로드')).toBeVisible();
    await expect(page.getByText('5')).toBeVisible();
  });

  test('should display recent scores', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Check recent scores section
    await expect(page.getByText('최근 악보')).toBeVisible();
    await expect(page.getByText('Test Score 1')).toBeVisible();
    await expect(page.getByText('Test Score 2')).toBeVisible();
    await expect(page.getByText('Composer A')).toBeVisible();
    await expect(page.getByText('Composer B')).toBeVisible();
  });

  test('should display quick actions', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Check quick actions
    await expect(page.getByText('악보 업로드')).toBeVisible();
    await expect(page.getByText('PDF 파일을 업로드하세요')).toBeVisible();
    
    await expect(page.getByText('새 세트리스트')).toBeVisible();
    await expect(page.getByText('공연용 세트리스트를 만드세요')).toBeVisible();
    
    await expect(page.getByText('악보 관리')).toBeVisible();
    await expect(page.getByText('모든 악보를 관리하세요')).toBeVisible();
  });

  test('should navigate to scores page', async ({ page }) => {
    await page.goto('/dashboard');
    
    await page.getByRole('link', { name: '모두 보기' }).click();
    await expect(page).toHaveURL('/scores');
  });

  test('should navigate to upload page', async ({ page }) => {
    await page.goto('/dashboard');
    
    await page.getByRole('link', { name: '악보 업로드' }).first().click();
    await expect(page).toHaveURL('/upload');
  });
});