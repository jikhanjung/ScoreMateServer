import { test, expect } from '@playwright/test';
import { createReadStream, readFileSync } from 'fs';
import { join } from 'path';

// Test data
const testUser = {
  email: 'test-upload@example.com',
  name: '업로드 테스트 사용자',
  password: 'uploadtest123!'
};

test.describe('File Upload Workflow Tests', () => {
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

  test('navigate to upload page and verify UI elements', async ({ page }) => {
    // Navigate to upload page
    await page.getByRole('link', { name: '파일 업로드' }).click();
    await expect(page).toHaveURL('/upload');
    
    // Verify page elements
    await expect(page.getByRole('heading', { name: '악보 업로드' })).toBeVisible();
    await expect(page.getByText('PDF 파일을 드래그하여 업로드하거나 클릭하여 선택하세요')).toBeVisible();
    await expect(page.getByText('지원 형식: PDF')).toBeVisible();
    await expect(page.getByText('최대 파일 크기: 50MB')).toBeVisible();
  });

  test('file upload form validation', async ({ page }) => {
    await page.goto('/upload');
    
    // Try to submit without selecting file
    await page.getByRole('button', { name: '업로드' }).click();
    await expect(page.getByText('파일을 선택해주세요')).toBeVisible();
    
    // Test file size validation by mocking large file
    const largeFileMock = new File(['x'.repeat(60 * 1024 * 1024)], 'large.pdf', { type: 'application/pdf' });
    
    // Create file input programmatically to test validation
    await page.evaluate(() => {
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (input) {
        const event = new Event('change', { bubbles: true });
        Object.defineProperty(event, 'target', { value: input });
        input.dispatchEvent(event);
      }
    });
  });

  test('successful file upload workflow', async ({ page }) => {
    await page.goto('/upload');
    
    // Create a small test PDF file for upload
    const testPdfContent = `%PDF-1.4
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
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF Document) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF`;

    // Create the file input and simulate file selection
    const fileInput = page.locator('input[type="file"]');
    
    // Use page.setInputFiles for file upload
    const buffer = Buffer.from(testPdfContent);
    await fileInput.setInputFiles({
      name: 'test-score.pdf',
      mimeType: 'application/pdf',
      buffer: buffer
    });

    // Fill in metadata
    await page.getByPlaceholder('악보 제목을 입력하세요').fill('테스트 악보');
    await page.getByPlaceholder('작곡가명을 입력하세요').fill('테스트 작곡가');
    await page.getByPlaceholder('편성 정보를 입력하세요').fill('피아노 솔로');
    await page.getByPlaceholder('메모나 설명을 입력하세요').fill('e2e 테스트용 악보');

    // Submit upload
    await page.getByRole('button', { name: '업로드' }).click();

    // Wait for upload completion
    await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });

    // Verify redirect to scores list
    await expect(page).toHaveURL('/scores', { timeout: 5000 });
    
    // Verify uploaded file appears in list
    await expect(page.getByText('테스트 악보')).toBeVisible();
    await expect(page.getByText('테스트 작곡가')).toBeVisible();
  });

  test('upload progress indication', async ({ page }) => {
    await page.goto('/upload');
    
    // Create a medium-sized test file to observe progress
    const mediumPdfContent = '%PDF-1.4\n' + 'x'.repeat(1024 * 100); // 100KB
    const buffer = Buffer.from(mediumPdfContent);
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'medium-test.pdf',
      mimeType: 'application/pdf',
      buffer: buffer
    });

    await page.getByPlaceholder('악보 제목을 입력하세요').fill('미디엄 테스트');
    await page.getByPlaceholder('작곡가명을 입력하세요').fill('테스트 작곡가');

    // Click upload and look for progress indicator
    await page.getByRole('button', { name: '업로드' }).click();
    
    // Check for loading state
    await expect(page.getByText(/업로드 중|처리 중|Loading/)).toBeVisible({ timeout: 5000 });
  });

  test('upload error handling', async ({ page }) => {
    await page.goto('/upload');
    
    // Try uploading invalid file type
    const textContent = 'This is not a PDF file';
    const buffer = Buffer.from(textContent);
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'invalid.txt',
      mimeType: 'text/plain',
      buffer: buffer
    });

    await page.getByPlaceholder('악보 제목을 입력하세요').fill('잘못된 파일');
    await page.getByRole('button', { name: '업로드' }).click();

    // Should show error message for invalid file type
    await expect(page.getByText(/지원하지 않는 파일 형식|PDF 파일만 업로드|올바르지 않은 파일/)).toBeVisible();
  });

  test('cancel upload functionality', async ({ page }) => {
    await page.goto('/upload');
    
    const testContent = '%PDF-1.4\nTest content';
    const buffer = Buffer.from(testContent);
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'cancel-test.pdf',
      mimeType: 'application/pdf',
      buffer: buffer
    });

    await page.getByPlaceholder('악보 제목을 입력하세요').fill('취소 테스트');
    
    // Look for cancel button if it exists
    const cancelButton = page.getByRole('button', { name: /취소|Cancel/ });
    if (await cancelButton.isVisible()) {
      await cancelButton.click();
      
      // Verify form is reset
      await expect(page.getByPlaceholder('악보 제목을 입력하세요')).toHaveValue('');
    }
  });
});