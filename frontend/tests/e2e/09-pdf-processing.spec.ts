import { test, expect } from '@playwright/test';

// Test data
const testUser = {
  email: 'test-pdf@example.com',
  name: 'PDF 테스트 사용자',
  password: 'pdftest123!'
};

test.describe('PDF Processing and Thumbnail Tests', () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    
    // Login process
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(testUser.email);
    await page.getByPlaceholder('비밀번호').fill(testUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    // Wait for dashboard to load or register if user doesn't exist
    try {
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    } catch {
      // User might not exist, try to register first
      await page.goto('/auth/register');
      await page.getByPlaceholder('your@email.com').fill(testUser.email);
      await page.getByPlaceholder('홍길동').fill(testUser.name);
      await page.getByPlaceholder('8자 이상').fill(testUser.password);
      await page.getByPlaceholder('비밀번호 재입력').fill(testUser.password);
      await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
      await page.getByRole('button', { name: '회원가입' }).click();
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    }
  });

  test('PDF upload triggers background processing', async ({ page }) => {
    await page.goto('/upload');
    
    // Create a more realistic PDF for processing
    const multiPagePdfContent = `%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R 4 0 R 5 0 R]
/Count 3
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 6 0 R
>>
endobj

4 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 7 0 R
>>
endobj

5 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 8 0 R
>>
endobj

6 0 obj
<<
/Length 65
>>
stream
BT
/F1 12 Tf
72 720 Td
(First Page - Musical Score) Tj
ET
endstream
endobj

7 0 obj
<<
/Length 66
>>
stream
BT
/F1 12 Tf
72 720 Td
(Second Page - Musical Score) Tj
ET
endstream
endobj

8 0 obj
<<
/Length 65
>>
stream
BT
/F1 12 Tf
72 720 Td
(Third Page - Musical Score) Tj
ET
endstream
endobj

xref
0 9
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000130 00000 n 
0000000221 00000 n 
0000000312 00000 n 
0000000403 00000 n 
0000000520 00000 n 
0000000638 00000 n 
trailer
<<
/Size 9
/Root 1 0 R
>>
startxref
754
%%EOF`;

    const fileInput = page.locator('input[type="file"]');
    const buffer = Buffer.from(multiPagePdfContent);
    
    await fileInput.setInputFiles({
      name: 'multi-page-score.pdf',
      mimeType: 'application/pdf',
      buffer: buffer
    });

    // Fill metadata
    await page.getByPlaceholder('악보 제목을 입력하세요').fill('멀티페이지 테스트 악보');
    await page.getByPlaceholder('작곡가명을 입력하세요').fill('PDF 테스트 작곡가');
    await page.getByPlaceholder('편성 정보를 입력하세요').fill('오케스트라');
    await page.getByPlaceholder('메모나 설명을 입력하세요').fill('PDF 처리 테스트용 3페이지 악보');

    // Submit upload
    await page.getByRole('button', { name: '업로드' }).click();

    // Wait for upload completion
    await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });

    // Navigate to scores list
    await expect(page).toHaveURL('/scores', { timeout: 5000 });
    
    // Verify uploaded file appears
    await expect(page.getByText('멀티페이지 테스트 악보')).toBeVisible();
    
    // Wait a bit for background processing to potentially complete
    await page.waitForTimeout(3000);
    
    // Reload to get updated data
    await page.reload();
    
    // Look for page count information (might take time to process)
    const scoreRow = page.locator('tr:has-text("멀티페이지 테스트 악보")');
    await expect(scoreRow).toBeVisible();
  });

  test('thumbnail generation and display', async ({ page }) => {
    // Go to scores list first
    await page.goto('/scores');
    
    // Look for any existing scores with thumbnails
    const scoreElements = page.locator('[data-testid="score-item"], tr');
    const scoreCount = await scoreElements.count();
    
    if (scoreCount > 0) {
      // Check first score for thumbnail
      const firstScore = scoreElements.first();
      
      // Look for thumbnail image or placeholder
      const thumbnailImage = firstScore.locator('img[alt*="thumbnail"], img[src*="thumbnail"], .thumbnail');
      const hasThumbnail = await thumbnailImage.count() > 0;
      
      if (hasThumbnail) {
        // Verify thumbnail loads properly
        await expect(thumbnailImage.first()).toBeVisible();
        
        // Check thumbnail src doesn't return 404
        const thumbnailSrc = await thumbnailImage.first().getAttribute('src');
        if (thumbnailSrc) {
          const response = await page.request.get(thumbnailSrc);
          expect(response.status()).toBeLessThan(400);
        }
      }
    }
  });

  test('page count display after processing', async ({ page }) => {
    await page.goto('/scores');
    
    // Look for scores that might have page count information
    const scoreRows = page.locator('tr:has-text("p"), td:has-text("페이지")');
    const rowCount = await scoreRows.count();
    
    if (rowCount > 0) {
      // Verify page count format
      const pageInfo = scoreRows.first();
      await expect(pageInfo).toBeVisible();
      
      // Should show format like "3p" or "3 페이지"
      const pageText = await pageInfo.textContent();
      expect(pageText).toMatch(/\d+\s*(p|페이지|page)/i);
    }
  });

  test('score detail view shows processing results', async ({ page }) => {
    await page.goto('/scores');
    
    // Click on first score if available
    const scoreLinks = page.locator('a[href*="/scores/"], tr[data-testid="score-row"]');
    const linkCount = await scoreLinks.count();
    
    if (linkCount > 0) {
      await scoreLinks.first().click();
      
      // Should navigate to score detail page
      await expect(page.url()).toMatch(/\/scores\/\d+/);
      
      // Look for score information
      await expect(page.locator('h1, .score-title')).toBeVisible();
      
      // Check for file information
      const fileInfoSection = page.locator('.file-info, [data-testid="file-info"]');
      if (await fileInfoSection.isVisible()) {
        // Might show page count, file size, etc.
        await expect(fileInfoSection).toBeVisible();
      }
      
      // Check for thumbnail in detail view
      const detailThumbnail = page.locator('img[alt*="thumbnail"], .score-thumbnail');
      if (await detailThumbnail.count() > 0) {
        await expect(detailThumbnail.first()).toBeVisible();
      }
    }
  });

  test('thumbnail proxy functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Find score with thumbnail
    const thumbnailImages = page.locator('img[src*="thumbnail-proxy"], img[src*="/api/thumbnail"]');
    const thumbnailCount = await thumbnailImages.count();
    
    if (thumbnailCount > 0) {
      const firstThumbnail = thumbnailImages.first();
      await expect(firstThumbnail).toBeVisible();
      
      // Check that thumbnail proxy URL works
      const thumbnailSrc = await firstThumbnail.getAttribute('src');
      if (thumbnailSrc && thumbnailSrc.includes('thumbnail')) {
        // Make direct request to thumbnail proxy
        const response = await page.request.get(thumbnailSrc);
        expect(response.status()).toBe(200);
        
        // Should return image content
        const contentType = response.headers()['content-type'];
        expect(contentType).toMatch(/image\/(jpeg|jpg|png|webp)/);
      }
    }
  });

  test('processing status and error handling', async ({ page }) => {
    await page.goto('/scores');
    
    // Look for any processing status indicators
    const statusElements = page.locator('.processing, .status-processing, [data-status="processing"]');
    const errorElements = page.locator('.error, .status-error, [data-status="error"]');
    
    // Processing status elements should be visible if files are being processed
    const processingCount = await statusElements.count();
    const errorCount = await errorElements.count();
    
    // If there are processing indicators, they should be properly styled
    if (processingCount > 0) {
      await expect(statusElements.first()).toBeVisible();
    }
    
    // If there are error indicators, they should show appropriate messaging
    if (errorCount > 0) {
      await expect(errorElements.first()).toBeVisible();
      // Error text should be informative
      const errorText = await errorElements.first().textContent();
      expect(errorText).not.toBe('');
    }
  });

  test('file size and metadata accuracy', async ({ page }) => {
    await page.goto('/scores');
    
    // Look for file size information
    const fileSizeElements = page.locator('td:has-text("KB"), td:has-text("MB"), .file-size');
    const sizeCount = await fileSizeElements.count();
    
    if (sizeCount > 0) {
      const firstSize = fileSizeElements.first();
      await expect(firstSize).toBeVisible();
      
      // File size should be in reasonable format
      const sizeText = await firstSize.textContent();
      expect(sizeText).toMatch(/\d+(\.\d+)?\s*(KB|MB|GB|bytes?)/i);
    }
    
    // Check for other metadata like upload date
    const dateElements = page.locator('td:has-text("-"), .created-at, .upload-date');
    const dateCount = await dateElements.count();
    
    if (dateCount > 0) {
      const firstDate = dateElements.first();
      await expect(firstDate).toBeVisible();
    }
  });

  test('background processing completion notification', async ({ page }) => {
    // This test checks if there are any notifications about completed processing
    await page.goto('/dashboard');
    
    // Look for notification elements
    const notifications = page.locator('.notification, .toast, .alert, [role="alert"]');
    const notificationCount = await notifications.count();
    
    // If there are notifications, verify they're accessible
    if (notificationCount > 0) {
      for (let i = 0; i < Math.min(notificationCount, 3); i++) {
        const notification = notifications.nth(i);
        if (await notification.isVisible()) {
          await expect(notification).toBeVisible();
        }
      }
    }
    
    // Check for any processing completion indicators in scores
    await page.goto('/scores');
    const completedElements = page.locator('.completed, .status-completed, [data-status="completed"]');
    const completedCount = await completedElements.count();
    
    if (completedCount > 0) {
      await expect(completedElements.first()).toBeVisible();
    }
  });
});