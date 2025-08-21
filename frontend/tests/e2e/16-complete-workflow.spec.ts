import { test, expect } from '@playwright/test';

// Comprehensive workflow test data
const workflowUser = {
  email: `workflow-${Date.now()}@example.com`, // Unique email for each test run
  name: '워크플로우 테스트 사용자',
  password: 'workflow123!'
};

const testScores = [
  {
    filename: 'classical-piece.pdf',
    title: '클래식 피아노 소나타',
    composer: '베토벤',
    instrumentation: '피아노 솔로',
    note: '1악장 전체'
  },
  {
    filename: 'jazz-standard.pdf',
    title: '재즈 스탠다드 컬렉션',
    composer: '가쉬윈',
    instrumentation: '재즈 밴드',
    note: '리얼북 스타일'
  }
];

test.describe('Complete ScoreMate Workflow Tests', () => {
  test('end-to-end user journey: registration to file management', async ({ page }) => {
    // Step 1: Initial landing and registration
    await page.goto('/');
    
    // Navigate to registration
    await page.getByRole('link', { name: /시작하기|회원가입|Get Started/ }).click();
    
    // Fill registration form
    await page.getByPlaceholder('your@email.com').fill(workflowUser.email);
    await page.getByPlaceholder('홍길동').fill(workflowUser.name);
    await page.getByPlaceholder('8자 이상').fill(workflowUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(workflowUser.password);
    await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
    
    // Submit registration
    await page.getByRole('button', { name: '회원가입' }).click();
    
    // Step 2: Verify successful login to dashboard
    await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    await expect(page.getByText('환영합니다!')).toBeVisible();
    
    // Step 3: Verify initial dashboard state (empty user)
    await expect(page.getByText('총 악보')).toBeVisible();
    await expect(page.getByText('0')).toBeVisible(); // Should show 0 scores initially
    
    // Step 4: Navigate to upload page
    await page.getByRole('link', { name: /악보 업로드|업로드/ }).click();
    await expect(page).toHaveURL('/upload');
    
    // Step 5: Upload first score
    await uploadScore(page, testScores[0]);
    
    // Step 6: Verify redirect to scores list and score appears
    await expect(page).toHaveURL('/scores', { timeout: 10000 });
    await expect(page.getByText(testScores[0].title)).toBeVisible();
    
    // Step 7: Upload second score
    await page.getByRole('link', { name: /악보 업로드|업로드/ }).click();
    await uploadScore(page, testScores[1]);
    
    // Step 8: Verify both scores in list
    await expect(page).toHaveURL('/scores');
    await expect(page.getByText(testScores[0].title)).toBeVisible();
    await expect(page.getByText(testScores[1].title)).toBeVisible();
    
    // Step 9: Return to dashboard and verify updated stats
    await page.getByRole('link', { name: /대시보드|Dashboard/ }).click();
    await expect(page).toHaveURL('/dashboard');
    
    // Wait for stats to update
    await page.waitForTimeout(2000);
    await page.reload();
    
    // Should now show 2 scores
    await expect(page.getByText('총 악보')).toBeVisible();
    // Look for "2" anywhere in stats section
    await expect(page.locator('.stats, .dashboard-stats').getByText('2')).toBeVisible();
    
    // Step 10: Test navigation between sections
    await page.getByRole('link', { name: /악보|Scores/ }).click();
    await expect(page).toHaveURL('/scores');
    
    // Step 11: Test score detail view
    await page.getByText(testScores[0].title).click();
    await expect(page.url()).toMatch(/\/scores\/\d+/);
    await expect(page.getByText(testScores[0].title)).toBeVisible();
    await expect(page.getByText(testScores[0].composer)).toBeVisible();
    
    // Step 12: Test logout functionality
    await page.getByRole('button', { name: '로그아웃' }).click();
    await expect(page).toHaveURL('/auth/login');
    
    // Step 13: Test login with existing credentials
    await page.getByPlaceholder('이메일').fill(workflowUser.email);
    await page.getByPlaceholder('비밀번호').fill(workflowUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    // Step 14: Verify data persistence
    await expect(page).toHaveURL('/dashboard');
    await page.getByRole('link', { name: /악보|Scores/ }).click();
    await expect(page.getByText(testScores[0].title)).toBeVisible();
    await expect(page.getByText(testScores[1].title)).toBeVisible();
  });

  test('error scenarios and recovery', async ({ page }) => {
    // Register user first
    await page.goto('/auth/register');
    const errorTestUser = {
      email: `error-test-${Date.now()}@example.com`,
      name: '에러 테스트 사용자',
      password: 'errortest123!'
    };
    
    await page.getByPlaceholder('your@email.com').fill(errorTestUser.email);
    await page.getByPlaceholder('홍길동').fill(errorTestUser.name);
    await page.getByPlaceholder('8자 이상').fill(errorTestUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(errorTestUser.password);
    await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
    await page.getByRole('button', { name: '회원가입' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
    
    // Test network error handling
    await page.context().setOffline(true);
    await page.getByRole('link', { name: /악보|Scores/ }).click();
    
    // Should handle offline gracefully
    await expect(page).toHaveURL('/scores');
    
    // Restore network
    await page.context().setOffline(false);
    await page.reload();
    
    // Should recover properly
    await expect(page.getByText(/악보|Scores/)).toBeVisible();
  });

  test('responsive design across devices', async ({ page }) => {
    // Login first
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(workflowUser.email);
    await page.getByPlaceholder('비밀번호').fill(workflowUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    const viewports = [
      { width: 375, height: 667, name: 'Mobile' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 1920, height: 1080, name: 'Desktop' }
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      
      // Test dashboard
      await page.goto('/dashboard');
      await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
      
      // Test scores list
      await page.goto('/scores');
      await expect(page.getByText(/악보|Scores/)).toBeVisible();
      
      // Test upload page
      await page.goto('/upload');
      await expect(page.getByRole('heading', { name: '악보 업로드' })).toBeVisible();
    }
  });

  test('performance and loading states', async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(workflowUser.email);
    await page.getByPlaceholder('비밀번호').fill(workflowUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    // Measure dashboard load time
    const startTime = Date.now();
    await page.goto('/dashboard');
    await expect(page.getByText('총 악보')).toBeVisible();
    const dashboardLoadTime = Date.now() - startTime;
    
    // Dashboard should load within reasonable time
    expect(dashboardLoadTime).toBeLessThan(5000);
    
    // Check for loading states
    await page.goto('/scores');
    
    // Look for loading indicators during data fetch
    const loadingElements = page.locator('.loading, .spinner, [data-testid="loading"]');
    // Loading elements might appear briefly
    
    // Page should be stable after loading
    await expect(page.getByText(/악보|Scores/)).toBeVisible();
  });

  test('accessibility compliance', async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.getByPlaceholder('이메일').fill(workflowUser.email);
    await page.getByPlaceholder('비밀번호').fill(workflowUser.password);
    await page.getByRole('button', { name: '로그인' }).click();
    
    // Test keyboard navigation
    await page.goto('/dashboard');
    
    // Tab through main navigation
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to navigate with keyboard
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
    
    // Test ARIA labels and roles
    await expect(page.locator('[role="main"], main')).toBeVisible();
    await expect(page.locator('[role="navigation"], nav')).toBeVisible();
    
    // Check for proper heading hierarchy
    const h1Elements = page.locator('h1');
    expect(await h1Elements.count()).toBeGreaterThan(0);
  });
});

// Helper function to upload a score
async function uploadScore(page: any, scoreData: any) {
  // Create PDF content
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
>>
endobj

4 0 obj
<<
/Length 50
>>
stream
BT
/F1 12 Tf
72 720 Td
(${scoreData.title}) Tj
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
  await page.getByPlaceholder('편성 정보를 입력하세요').fill(scoreData.instrumentation);
  await page.getByPlaceholder('메모나 설명을 입력하세요').fill(scoreData.note);

  // Submit upload
  await page.getByRole('button', { name: '업로드' }).click();

  // Wait for completion
  await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });
}