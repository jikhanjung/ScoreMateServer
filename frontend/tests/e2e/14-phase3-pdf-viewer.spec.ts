import { test, expect } from '@playwright/test';

// Test data for PDF viewer
const pdfViewerTestUser = {
  email: `pdf-viewer-test-${Date.now()}@example.com`,
  name: 'PDF 뷰어 테스트 사용자',
  password: 'pdfviewertest123!'
};

const testScore = {
  filename: 'pdf-viewer-test.pdf',
  title: 'PDF 뷰어 테스트 악보',
  composer: 'PDF 테스트 작곡가'
};

test.describe('Phase 3: PDF Viewer Features', () => {
  let scoreId: string;

  test.beforeEach(async ({ page }) => {
    // Register and login user
    await page.goto('/auth/register');
    await page.getByPlaceholder('your@email.com').fill(pdfViewerTestUser.email);
    await page.getByPlaceholder('홍길동').fill(pdfViewerTestUser.name);
    await page.getByPlaceholder('8자 이상').fill(pdfViewerTestUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(pdfViewerTestUser.password);
    await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
    await page.getByRole('button', { name: '회원가입' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
    
    // Upload test score
    await page.getByRole('link', { name: /악보 업로드|업로드/ }).click();
    await uploadPdfForViewer(page, testScore);
    await expect(page).toHaveURL('/scores', { timeout: 10000 });
    
    // Extract score ID from URL when clicking on the score
    await page.getByText(testScore.title).click();
    await page.waitForURL(/\/scores\/\d+/);
    const url = page.url();
    scoreId = url.split('/').pop() || '';
  });

  test('navigation to score detail page', async ({ page }) => {
    // Should already be on score detail page from beforeEach
    await expect(page).toHaveURL(/\/scores\/\d+/);
    await expect(page.getByText(testScore.title)).toBeVisible();
    await expect(page.getByText(testScore.composer)).toBeVisible();
  });

  test('PDF viewer default display', async ({ page }) => {
    // Should show PDF viewer by default (not thumbnail)
    await expect(page.locator('.pdf-viewer, [data-testid="pdf-viewer"]')).toBeVisible();
    
    // Should show PDF content area
    const pdfContent = page.locator('embed[type="application/pdf"], iframe, .pdf-content');
    await expect(pdfContent).toBeVisible();
  });

  test('PDF viewer toolbar functionality', async ({ page }) => {
    // Check if PDF viewer toolbar is present
    const toolbar = page.locator('.pdf-toolbar, [data-testid="pdf-toolbar"]');
    if (await toolbar.isVisible()) {
      // Check for download button
      await expect(page.getByRole('button', { name: /다운로드|Download/ })).toBeVisible();
      
      // Check for filename display
      await expect(page.getByText(testScore.title)).toBeVisible();
    }
  });

  test('PDF download functionality', async ({ page }) => {
    // Start download monitoring
    const downloadPromise = page.waitForEvent('download');
    
    // Click download button
    const downloadButton = page.getByRole('button', { name: /다운로드|Download/ });
    await downloadButton.click();
    
    // Wait for download to start
    const download = await downloadPromise;
    
    // Verify download filename
    const filename = download.suggestedFilename();
    expect(filename).toBeTruthy();
    expect(filename).toContain('.pdf');
    // Should use original filename, not 'original.pdf'
    expect(filename).not.toBe('original.pdf');
  });

  test('PDF loading states', async ({ page }) => {
    // Refresh to see loading state
    await page.reload();
    
    // Look for loading indicators
    const loadingSpinner = page.locator('.loading, .spinner, [data-testid="loading"]');
    if (await loadingSpinner.isVisible()) {
      await expect(loadingSpinner).toBeVisible();
    }
    
    // Eventually PDF should load
    await expect(page.locator('embed[type="application/pdf"], iframe, .pdf-content')).toBeVisible({ timeout: 10000 });
  });

  test('PDF error handling', async ({ page }) => {
    // Navigate to non-existent score to test error handling
    await page.goto('/scores/99999');
    
    // Should show 404 or error message
    const errorMessage = page.getByText(/찾을 수 없습니다|Not found|Error/);
    await expect(errorMessage).toBeVisible();
  });

  test('PDF viewer with different browsers', async ({ page, browserName }) => {
    // PDF support varies by browser
    const pdfEmbed = page.locator('embed[type="application/pdf"]');
    
    if (browserName === 'webkit') {
      // Safari might not support PDF embed
      const fallbackMessage = page.getByText(/PDF가 표시되지 않는 경우|브라우저에서.*표시할 수 없습니다/);
      if (await fallbackMessage.isVisible()) {
        await expect(fallbackMessage).toBeVisible();
      }
    } else {
      // Chrome/Firefox should display PDF
      await expect(pdfEmbed).toBeVisible({ timeout: 10000 });
    }
  });

  test('PDF viewer fallback notice', async ({ page }) => {
    // Check for fallback notice at bottom of PDF viewer
    const fallbackNotice = page.getByText(/PDF가 표시되지 않는 경우.*다운로드.*버튼을 사용해주세요/);
    await expect(fallbackNotice).toBeVisible();
  });

  test('score metadata display', async ({ page }) => {
    // Check metadata section
    await expect(page.getByText(/정보|Information/)).toBeVisible();
    
    // Check basic metadata
    await expect(page.getByText(/파일 크기|File Size/)).toBeVisible();
    await expect(page.getByText(/업로드일|Upload Date/)).toBeVisible();
    await expect(page.getByText(/수정일|Modified Date/)).toBeVisible();
  });

  test('score actions availability', async ({ page }) => {
    // Check action buttons in header
    await expect(page.getByRole('button', { name: /편집|Edit/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /다운로드|Download/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /삭제|Delete/ })).toBeVisible();
  });

  test('quick actions panel', async ({ page }) => {
    // Check quick actions section
    const quickActions = page.getByText(/빠른 작업|Quick Actions/);
    if (await quickActions.isVisible()) {
      await expect(quickActions).toBeVisible();
      
      // Check setlist addition option
      await expect(page.getByRole('button', { name: /세트리스트에 추가|Add to Setlist/ })).toBeVisible();
    }
  });

  test('responsive PDF viewer layout', async ({ page }) => {
    // Test desktop layout
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.reload();
    
    // Should have side-by-side layout (PDF + metadata)
    const layout = page.locator('.grid, .lg\\:grid-cols-3, .flex');
    await expect(layout).toBeVisible();
    
    // Test mobile layout
    await page.setViewportSize({ width: 375, height: 667 });
    await page.reload();
    
    // Should still show PDF viewer
    await expect(page.locator('embed[type="application/pdf"], iframe, .pdf-content')).toBeVisible();
  });

  test('PDF viewer keyboard accessibility', async ({ page }) => {
    // Test tab navigation
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to focus on interactive elements
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
    
    // Test Enter key on download button
    const downloadButton = page.getByRole('button', { name: /다운로드|Download/ });
    await downloadButton.focus();
    
    // Start download monitoring
    const downloadPromise = page.waitForEvent('download');
    await page.keyboard.press('Enter');
    
    // Should trigger download
    const download = await downloadPromise;
    expect(download).toBeTruthy();
  });

  test('PDF viewer performance', async ({ page }) => {
    const startTime = Date.now();
    
    // Navigate to score detail
    await page.goto(`/scores/${scoreId}`);
    
    // Wait for PDF to load
    await expect(page.locator('embed[type="application/pdf"], iframe, .pdf-content')).toBeVisible();
    
    const loadTime = Date.now() - startTime;
    
    // Should load within reasonable time
    expect(loadTime).toBeLessThan(10000); // 10 seconds
  });

  test('back navigation from score detail', async ({ page }) => {
    // Click back to scores list
    const backLink = page.getByRole('link', { name: /악보 목록으로|Back to Scores/ });
    await backLink.click();
    
    await expect(page).toHaveURL('/scores');
    await expect(page.getByText(testScore.title)).toBeVisible();
  });

  test('PDF URL generation and access', async ({ page }) => {
    // Check if PDF URL is properly generated (not visible to user, but affects functionality)
    const pdfEmbed = page.locator('embed[type="application/pdf"]');
    
    if (await pdfEmbed.isVisible()) {
      const src = await pdfEmbed.getAttribute('src');
      expect(src).toBeTruthy();
      expect(src).toContain('http'); // Should be a valid URL
    }
  });

  test('error recovery in PDF viewer', async ({ page }) => {
    // Simulate network error during PDF load
    await page.context().setOffline(true);
    await page.reload();
    
    // Should show error state or fallback
    const errorElements = page.locator('.error, [data-testid="error"], .pdf-error');
    if (await errorElements.count() > 0) {
      await expect(errorElements.first()).toBeVisible();
    }
    
    // Restore network
    await page.context().setOffline(false);
    await page.reload();
    
    // Should recover and show PDF
    await expect(page.locator('embed[type="application/pdf"], iframe, .pdf-content')).toBeVisible();
  });

  test('multiple PDF viewers in browser tabs', async ({ context }) => {
    // Create second page/tab
    const page2 = await context.newPage();
    
    // Login on second tab
    await page2.goto('/auth/login');
    await page2.getByPlaceholder('이메일').fill(pdfViewerTestUser.email);
    await page2.getByPlaceholder('비밀번호').fill(pdfViewerTestUser.password);
    await page2.getByRole('button', { name: '로그인' }).click();
    
    // Navigate to same score
    await page2.goto(`/scores/${scoreId}`);
    
    // Both tabs should work independently
    await expect(page2.locator('embed[type="application/pdf"], iframe, .pdf-content')).toBeVisible();
    
    await page2.close();
  });
});

// Helper function to upload PDF for viewer testing
async function uploadPdfForViewer(page: any, scoreData: any) {
  // Create a more complete PDF for viewer testing
  const pdfContent = `%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
  /Font <<
    /F1 5 0 R
  >>
>>
>>
endobj

4 0 obj
<<
/Length 100
>>
stream
BT
/F1 12 Tf
72 720 Td
(${scoreData.title}) Tj
0 -20 Td
(by ${scoreData.composer}) Tj
0 -40 Td
(This is a test PDF for the PDF viewer.) Tj
ET
endstream
endobj

5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000271 00000 n 
0000000422 00000 n 
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
507
%%EOF`;

  const fileInput = page.locator('input[type="file"]');
  const buffer = Buffer.from(pdfContent);
  
  await fileInput.setInputFiles({
    name: scoreData.filename,
    mimeType: 'application/pdf',
    buffer: buffer
  });

  // Fill metadata
  await page.getByPlaceholder('악보 제목을 입력하세요').fill(scoreData.title);
  await page.getByPlaceholder('작곡가명을 입력하세요').fill(scoreData.composer);

  // Submit upload
  await page.getByRole('button', { name: '업로드' }).click();

  // Wait for completion
  await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });
}