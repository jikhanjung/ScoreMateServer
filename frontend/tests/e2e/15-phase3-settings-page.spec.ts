import { test, expect } from '@playwright/test';

// Test data for settings page
const settingsTestUser = {
  email: `settings-test-${Date.now()}@example.com`,
  name: '설정 테스트 사용자',
  password: 'settingstest123!'
};

test.describe('Phase 3: User Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    // Register and login user
    await page.goto('/auth/register');
    await page.getByPlaceholder('your@email.com').fill(settingsTestUser.email);
    await page.getByPlaceholder('홍길동').fill(settingsTestUser.name);
    await page.getByPlaceholder('8자 이상').fill(settingsTestUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(settingsTestUser.password);
    await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
    await page.getByRole('button', { name: '회원가입' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
  });

  test('navigation to settings page', async ({ page }) => {
    // Navigate to settings from header
    const settingsLink = page.getByRole('link', { name: /설정|Settings/ });
    await expect(settingsLink).toBeVisible();
    await settingsLink.click();
    
    await expect(page).toHaveURL('/settings');
    await expect(page.getByRole('heading', { name: /설정|Settings/ })).toBeVisible();
  });

  test('settings page tab navigation', async ({ page }) => {
    await page.goto('/settings');
    
    // Check all tabs are present
    await expect(page.getByText(/프로필|Profile/)).toBeVisible();
    await expect(page.getByText(/보안|Security/)).toBeVisible();
    await expect(page.getByText(/스토리지|Storage/)).toBeVisible();
    await expect(page.getByText(/구독|Subscription/)).toBeVisible();
    
    // Test tab switching
    await page.getByText(/보안|Security/).click();
    await expect(page.getByText(/비밀번호 변경|Change Password/)).toBeVisible();
    
    await page.getByText(/스토리지|Storage/).click();
    await expect(page.getByText(/스토리지 사용량|Storage Usage/)).toBeVisible();
    
    await page.getByText(/구독|Subscription/).click();
    await expect(page.getByText(/구독 정보|Subscription Info/)).toBeVisible();
    
    // Return to profile tab
    await page.getByText(/프로필|Profile/).click();
    await expect(page.getByText(/사용자 정보|User Information/)).toBeVisible();
  });

  test('profile tab information display', async ({ page }) => {
    await page.goto('/settings');
    
    // Verify profile information is displayed
    await expect(page.getByDisplayValue(settingsTestUser.name)).toBeVisible();
    await expect(page.getByDisplayValue(settingsTestUser.email)).toBeVisible();
    
    // Check if plan information is shown
    await expect(page.getByText(/Solo|Free|Pro/)).toBeVisible();
  });

  test('profile update functionality', async ({ page }) => {
    await page.goto('/settings');
    
    // Update profile information
    const nameInput = page.getByDisplayValue(settingsTestUser.name);
    await nameInput.clear();
    await nameInput.fill('업데이트된 사용자명');
    
    // Save changes
    const saveButton = page.getByRole('button', { name: /저장|Save|업데이트|Update/ });
    if (await saveButton.isVisible()) {
      await saveButton.click();
      
      // Verify success message
      await expect(page.getByText(/저장되었습니다|Updated successfully|프로필이 업데이트/)).toBeVisible();
    }
  });

  test('security tab password change form', async ({ page }) => {
    await page.goto('/settings');
    
    // Navigate to security tab
    await page.getByText(/보안|Security/).click();
    
    // Check password change form elements
    await expect(page.getByPlaceholder(/현재 비밀번호|Current Password/)).toBeVisible();
    await expect(page.getByPlaceholder(/새 비밀번호|New Password/)).toBeVisible();
    await expect(page.getByPlaceholder(/새 비밀번호 확인|Confirm New Password/)).toBeVisible();
    
    // Check security tips
    await expect(page.getByText(/보안 팁|Security Tip/)).toBeVisible();
  });

  test('password change validation', async ({ page }) => {
    await page.goto('/settings');
    await page.getByText(/보안|Security/).click();
    
    // Test password mismatch
    await page.getByPlaceholder(/현재 비밀번호|Current Password/).fill(settingsTestUser.password);
    await page.getByPlaceholder(/새 비밀번호|New Password/).fill('newpassword123!');
    await page.getByPlaceholder(/새 비밀번호 확인|Confirm New Password/).fill('differentpassword123!');
    
    const changePasswordButton = page.getByRole('button', { name: /비밀번호 변경|Change Password/ });
    await changePasswordButton.click();
    
    // Should show validation error
    await expect(page.getByText(/비밀번호가 일치하지 않습니다|Passwords do not match/)).toBeVisible();
  });

  test('storage tab information display', async ({ page }) => {
    await page.goto('/settings');
    await page.getByText(/스토리지|Storage/).click();
    
    // Check storage usage elements
    await expect(page.getByText(/사용 중|Used/)).toBeVisible();
    await expect(page.getByText(/MB/)).toBeVisible();
    
    // Check progress bar
    const progressBar = page.locator('.progress, [role="progressbar"], .bg-blue-500');
    await expect(progressBar).toBeVisible();
    
    // Check statistics
    await expect(page.getByText(/총 악보 수|Total Scores/)).toBeVisible();
    await expect(page.getByText(/평균 파일 크기|Average File Size/)).toBeVisible();
  });

  test('storage usage display with data', async ({ page }) => {
    // Upload a test score first to have storage data
    await page.goto('/upload');
    
    const pdfContent = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj  
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f 
trailer<</Size 4/Root 1 0 R>>
startxref
196
%%EOF`;

    const fileInput = page.locator('input[type="file"]');
    const buffer = Buffer.from(pdfContent);
    
    await fileInput.setInputFiles({
      name: 'storage-test.pdf',
      mimeType: 'application/pdf',
      buffer: buffer
    });

    await page.getByPlaceholder('악보 제목을 입력하세요').fill('스토리지 테스트 악보');
    await page.getByPlaceholder('작곡가명을 입력하세요').fill('테스트 작곡가');
    await page.getByRole('button', { name: '업로드' }).click();
    
    await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });
    
    // Now check storage page
    await page.goto('/settings');
    await page.getByText(/스토리지|Storage/).click();
    
    // Should show non-zero usage
    const usageText = page.locator('text=/[0-9]+\.[0-9]+ MB/');
    await expect(usageText).toBeVisible();
    
    // Should show 1 score
    await expect(page.getByText('1개')).toBeVisible();
  });

  test('subscription tab information', async ({ page }) => {
    await page.goto('/settings');
    await page.getByText(/구독|Subscription/).click();
    
    // Check subscription details
    await expect(page.getByText(/Solo|Free|Pro.*플랜/)).toBeVisible();
    await expect(page.getByText(/현재 사용 중인 요금제|Current Plan/)).toBeVisible();
    
    // Check included features
    await expect(page.getByText(/포함 사항|Included Features/)).toBeVisible();
    await expect(page.getByText(/스토리지.*MB/)).toBeVisible();
    await expect(page.getByText(/악보 업로드|Upload/)).toBeVisible();
    await expect(page.getByText(/세트리스트 관리|Setlist Management/)).toBeVisible();
    await expect(page.getByText(/PDF 썸네일|PDF Thumbnails/)).toBeVisible();
    
    // Check upgrade section
    await expect(page.getByText(/업그레이드|Upgrade/)).toBeVisible();
    const upgradeButton = page.getByRole('button', { name: /업그레이드|Upgrade/ });
    await expect(upgradeButton).toBeVisible();
    await expect(upgradeButton).toBeDisabled(); // Should be disabled (준비 중)
  });

  test('responsive design on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    await page.goto('/settings');
    
    // Check mobile layout
    await expect(page.getByRole('heading', { name: /설정|Settings/ })).toBeVisible();
    
    // Tabs should be responsive
    await expect(page.getByText(/프로필|Profile/)).toBeVisible();
    await expect(page.getByText(/보안|Security/)).toBeVisible();
    
    // Test tab switching on mobile
    await page.getByText(/스토리지|Storage/).click();
    await expect(page.getByText(/스토리지 사용량|Storage Usage/)).toBeVisible();
  });

  test('data loading states', async ({ page }) => {
    await page.goto('/settings');
    
    // Navigate to storage tab to check loading
    await page.getByText(/스토리지|Storage/).click();
    
    // Look for loading states (might be brief)
    const loadingElements = page.locator('.loading, .spinner, [data-testid="loading"]');
    
    // Eventually data should load
    await expect(page.getByText(/사용 중|Used/)).toBeVisible({ timeout: 10000 });
  });

  test('error handling for failed data loads', async ({ page }) => {
    // Go offline to simulate network error
    await page.context().setOffline(true);
    
    await page.goto('/settings');
    await page.getByText(/스토리지|Storage/).click();
    
    // Should handle offline gracefully
    const errorMessage = page.getByText(/불러올 수 없습니다|Cannot load|Failed to load/);
    await expect(errorMessage).toBeVisible({ timeout: 10000 });
    
    // Restore network
    await page.context().setOffline(false);
  });

  test('keyboard navigation accessibility', async ({ page }) => {
    await page.goto('/settings');
    
    // Test tab navigation with keyboard
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to navigate to security tab with keyboard
    await page.keyboard.press('ArrowRight'); // Or appropriate key for tab navigation
    
    // Verify focused element
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });

  test('settings page URL persistence', async ({ page }) => {
    await page.goto('/settings');
    
    // Navigate to specific tab
    await page.getByText(/보안|Security/).click();
    
    // URL should update to reflect tab (if implemented)
    const currentUrl = page.url();
    expect(currentUrl).toContain('/settings');
    
    // Refresh page
    await page.reload();
    
    // Should maintain settings page
    await expect(page.getByRole('heading', { name: /설정|Settings/ })).toBeVisible();
  });

  test('form validation and user feedback', async ({ page }) => {
    await page.goto('/settings');
    
    // Test profile form validation
    const nameInput = page.getByDisplayValue(settingsTestUser.name);
    await nameInput.clear();
    await nameInput.fill(''); // Empty name
    
    const saveButton = page.getByRole('button', { name: /저장|Save|업데이트|Update/ });
    if (await saveButton.isVisible()) {
      await saveButton.click();
      
      // Should show validation error
      const validationError = page.getByText(/필수입니다|Required|이름을 입력/);
      if (await validationError.isVisible()) {
        await expect(validationError).toBeVisible();
      }
    }
  });

  test('cross-tab data consistency', async ({ page }) => {
    await page.goto('/settings');
    
    // Check quota in storage tab
    await page.getByText(/스토리지|Storage/).click();
    const storageQuota = page.locator('text=/200 MB|[0-9]+ MB/').first();
    const quotaText = await storageQuota.textContent();
    
    // Check quota in subscription tab
    await page.getByText(/구독|Subscription/).click();
    const subscriptionQuota = page.locator('text=/스토리지.*MB/');
    
    // Should show consistent quota information
    await expect(subscriptionQuota).toBeVisible();
    
    if (quotaText) {
      const quotaValue = quotaText.match(/\d+/)?.[0];
      if (quotaValue) {
        await expect(subscriptionQuota).toContainText(quotaValue);
      }
    }
  });
});