import { Page, expect } from '@playwright/test';

// Test utilities for common e2e operations

export const TEST_USERS = {
  WORKFLOW: {
    email: 'workflow-test@scoremate.com',
    name: '워크플로우 테스터',
    password: 'WorkflowTest2024!@#Complex'
  },
  UPLOAD: {
    email: 'upload-test@scoremate.com',
    name: '업로드 테스터',
    password: 'UploadTest2024!@#Complex'
  },
  DASHBOARD: {
    email: 'dashboard-test@scoremate.com',
    name: '대시보드 테스터',
    password: 'DashboardTest2024!@#Complex'
  }
};

export async function loginUser(page: Page, userCredentials: { email: string; password: string }) {
  await page.goto('/auth/login');
  await page.getByPlaceholder('이메일').fill(userCredentials.email);
  await page.getByPlaceholder('비밀번호').fill(userCredentials.password);
  await page.getByRole('button', { name: '로그인' }).click();
  
  try {
    await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
  } catch {
    // User might not exist, will be handled by calling test
    throw new Error('Login failed - user might not exist');
  }
}

export async function registerUser(page: Page, userData: { email: string; name: string; password: string }) {
  await page.goto('/auth/register');
  await page.getByPlaceholder('your@email.com').fill(userData.email);
  await page.getByPlaceholder('홍길동').fill(userData.name);
  await page.getByPlaceholder('8자 이상').fill(userData.password);
  await page.getByPlaceholder('비밀번호 재입력').fill(userData.password);
  await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
  await page.getByRole('button', { name: '회원가입' }).click();
  
  await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
}

export async function loginOrRegister(page: Page, userData: { email: string; name: string; password: string }) {
  try {
    await loginUser(page, userData);
  } catch {
    await registerUser(page, userData);
  }
}

export function createTestPDF(title: string = 'Test Score', pages: number = 1): Buffer {
  let pdfContent = `%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [`;

  // Add page references
  for (let i = 0; i < pages; i++) {
    pdfContent += `${3 + i} 0 R `;
  }
  
  pdfContent += `]
/Count ${pages}
>>
endobj
`;

  // Add page objects
  for (let i = 0; i < pages; i++) {
    const pageNum = 3 + i;
    const contentNum = 3 + pages + i;
    
    pdfContent += `
${pageNum} 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents ${contentNum} 0 R
>>
endobj
`;
  }

  // Add content objects
  for (let i = 0; i < pages; i++) {
    const contentNum = 3 + pages + i;
    const pageContent = `Page ${i + 1} - ${title}`;
    
    pdfContent += `
${contentNum} 0 obj
<<
/Length ${pageContent.length + 20}
>>
stream
BT
/F1 12 Tf
72 720 Td
(${pageContent}) Tj
ET
endstream
endobj
`;
  }

  // Add xref and trailer
  const xrefStart = pdfContent.length;
  pdfContent += `
xref
0 ${3 + pages * 2}
0000000000 65535 f `;

  // Add xref entries (simplified)
  for (let i = 1; i < 3 + pages * 2; i++) {
    pdfContent += `
0000000${String(i * 100).padStart(3, '0')} 00000 n `;
  }

  pdfContent += `
trailer
<<
/Size ${3 + pages * 2}
/Root 1 0 R
>>
startxref
${xrefStart}
%%EOF`;

  return Buffer.from(pdfContent);
}

export async function uploadTestScore(page: Page, scoreData: {
  filename: string;
  title: string;
  composer: string;
  instrumentation?: string;
  note?: string;
  pages?: number;
}) {
  // Navigate to upload page if not already there
  if (!page.url().includes('/upload')) {
    await page.goto('/upload');
  }

  const fileInput = page.locator('input[type="file"]');
  const pdfBuffer = createTestPDF(scoreData.title, scoreData.pages || 1);
  
  await fileInput.setInputFiles({
    name: scoreData.filename,
    mimeType: 'application/pdf',
    buffer: pdfBuffer
  });

  // Fill metadata
  await page.getByPlaceholder('악보 제목을 입력하세요').fill(scoreData.title);
  await page.getByPlaceholder('작곡가명을 입력하세요').fill(scoreData.composer);
  
  if (scoreData.instrumentation) {
    await page.getByPlaceholder('편성 정보를 입력하세요').fill(scoreData.instrumentation);
  }
  
  if (scoreData.note) {
    await page.getByPlaceholder('메모나 설명을 입력하세요').fill(scoreData.note);
  }

  // Submit upload
  await page.getByRole('button', { name: '업로드' }).click();

  // Wait for completion
  await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });
  
  // Should redirect to scores list
  await expect(page).toHaveURL('/scores', { timeout: 10000 });
}

export async function waitForProcessing(page: Page, timeout: number = 10000) {
  // Wait for any processing indicators to disappear
  const processingSelectors = [
    '.processing',
    '.loading',
    '[data-status="processing"]',
    '.spinner'
  ];
  
  for (const selector of processingSelectors) {
    try {
      await page.waitForSelector(selector, { state: 'hidden', timeout });
    } catch {
      // Selector might not exist, continue
    }
  }
}

export async function verifyScoreInList(page: Page, scoreTitle: string) {
  await page.goto('/scores');
  await expect(page.getByText(scoreTitle)).toBeVisible({ timeout: 10000 });
}

export async function verifyDashboardStats(page: Page, expectedScoreCount?: number) {
  await page.goto('/dashboard');
  await expect(page.getByText('총 악보')).toBeVisible();
  
  if (expectedScoreCount !== undefined) {
    await expect(page.getByText(expectedScoreCount.toString())).toBeVisible();
  }
}

export async function clearUserData(page: Page) {
  // Clear local storage and cookies
  await page.context().clearCookies();
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}

export const VIEWPORT_SIZES = {
  MOBILE: { width: 375, height: 667 },
  TABLET: { width: 768, height: 1024 },
  DESKTOP: { width: 1920, height: 1080 }
};