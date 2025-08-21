import { test, expect } from '@playwright/test';

// Test data for advanced filtering
const filterTestUser = {
  email: `filter-test-${Date.now()}@example.com`,
  name: '고급 필터 테스트 사용자',
  password: 'filtertest123!'
};

const testScores = [
  {
    filename: 'classical-beethoven.pdf',
    title: '월광 소나타',
    composer: '베토벤',
    genre: '클래식',
    difficulty: 4,
    tags: ['클래식', '소나타', '피아노']
  },
  {
    filename: 'jazz-gershwin.pdf',
    title: '썸머타임',
    composer: '거쉬윈',
    genre: '재즈',
    difficulty: 2,
    tags: ['재즈', '스탠다드', '오페라']
  },
  {
    filename: 'pop-ballad.pdf',
    title: '이마진',
    composer: '존 레논',
    genre: '팝',
    difficulty: 1,
    tags: ['팝', '발라드', '평화']
  },
  {
    filename: 'classical-chopin.pdf',
    title: '녹턴 E플랫 장조',
    composer: '쇼팽',
    genre: '클래식',
    difficulty: 3,
    tags: ['클래식', '녹턴', '피아노']
  }
];

test.describe('Phase 3: Advanced Filtering Features', () => {
  test.beforeEach(async ({ page }) => {
    // Register and login user
    await page.goto('/auth/register');
    await page.getByPlaceholder('your@email.com').fill(filterTestUser.email);
    await page.getByPlaceholder('홍길동').fill(filterTestUser.name);
    await page.getByPlaceholder('8자 이상').fill(filterTestUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(filterTestUser.password);
    await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
    await page.getByRole('button', { name: '회원가입' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
    
    // Upload test scores
    for (const score of testScores) {
      await page.getByRole('link', { name: /악보 업로드|업로드/ }).click();
      await uploadScoreWithMetadata(page, score);
      await expect(page).toHaveURL('/scores', { timeout: 10000 });
    }
  });

  test('basic search functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Test title search
    await page.getByPlaceholder('악보 검색...').fill('월광');
    await page.getByRole('button', { name: '검색' }).click();
    
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('썸머타임')).not.toBeVisible();
    
    // Clear search
    await page.getByPlaceholder('악보 검색...').clear();
    await page.getByRole('button', { name: '검색' }).click();
    
    // All scores should be visible again
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('썸머타임')).toBeVisible();
  });

  test('composer search functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Search by composer
    await page.getByPlaceholder('악보 검색...').fill('베토벤');
    await page.getByRole('button', { name: '검색' }).click();
    
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('베토벤')).toBeVisible();
    await expect(page.getByText('거쉬윈')).not.toBeVisible();
  });

  test('advanced filters toggle', async ({ page }) => {
    await page.goto('/scores');
    
    // Check if advanced filters button exists
    const advancedFiltersButton = page.getByRole('button', { name: /고급 필터|Advanced Filters/ });
    await expect(advancedFiltersButton).toBeVisible();
    
    // Open advanced filters
    await advancedFiltersButton.click();
    
    // Check if filter panel is visible
    await expect(page.locator('.advanced-filters, [data-testid="advanced-filters"]')).toBeVisible();
    
    // Check for filter options
    await expect(page.getByText(/장르|Genre/)).toBeVisible();
    await expect(page.getByText(/작곡가|Composer/)).toBeVisible();
    await expect(page.getByText(/난이도|Difficulty/)).toBeVisible();
    await expect(page.getByText(/태그|Tags/)).toBeVisible();
  });

  test('genre filtering', async ({ page }) => {
    await page.goto('/scores');
    
    // Open advanced filters
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    // Filter by genre - Classical
    const genreSelect = page.locator('select[name="genre"], input[name="genre"]').first();
    await genreSelect.selectOption('클래식');
    
    // Apply filters
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Should show only classical scores
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('녹턴 E플랫 장조')).toBeVisible();
    await expect(page.getByText('썸머타임')).not.toBeVisible();
    await expect(page.getByText('이마진')).not.toBeVisible();
  });

  test('difficulty filtering', async ({ page }) => {
    await page.goto('/scores');
    
    // Open advanced filters
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    // Filter by difficulty - Easy (1-2)
    const difficultyMin = page.locator('input[name="difficulty_min"], input[type="range"]').first();
    const difficultyMax = page.locator('input[name="difficulty_max"], input[type="range"]').last();
    
    await difficultyMin.fill('1');
    await difficultyMax.fill('2');
    
    // Apply filters
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Should show only easy scores
    await expect(page.getByText('썸머타임')).toBeVisible(); // difficulty 2
    await expect(page.getByText('이마진')).toBeVisible();    // difficulty 1
    await expect(page.getByText('월광 소나타')).not.toBeVisible(); // difficulty 4
  });

  test('tag filtering', async ({ page }) => {
    await page.goto('/scores');
    
    // Open advanced filters
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    // Filter by tag
    const tagInput = page.locator('input[name="tags"], input[placeholder*="태그"]').first();
    await tagInput.fill('피아노');
    await page.keyboard.press('Enter');
    
    // Apply filters
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Should show only piano scores
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('녹턴 E플랫 장조')).toBeVisible();
    await expect(page.getByText('썸머타임')).not.toBeVisible();
  });

  test('combined filters', async ({ page }) => {
    await page.goto('/scores');
    
    // Open advanced filters
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    // Apply multiple filters
    const genreSelect = page.locator('select[name="genre"], input[name="genre"]').first();
    await genreSelect.selectOption('클래식');
    
    const difficultyMin = page.locator('input[name="difficulty_min"], input[type="range"]').first();
    await difficultyMin.fill('3');
    
    // Apply filters
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Should show only classical scores with difficulty >= 3
    await expect(page.getByText('월광 소나타')).toBeVisible(); // classical, difficulty 4
    await expect(page.getByText('녹턴 E플랫 장조')).toBeVisible(); // classical, difficulty 3
    await expect(page.getByText('썸머타임')).not.toBeVisible(); // jazz
    await expect(page.getByText('이마진')).not.toBeVisible(); // pop
  });

  test('filter reset functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Open advanced filters and apply some filters
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    const genreSelect = page.locator('select[name="genre"], input[name="genre"]').first();
    await genreSelect.selectOption('재즈');
    
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Verify filter is applied
    await expect(page.getByText('썸머타임')).toBeVisible();
    await expect(page.getByText('월광 소나타')).not.toBeVisible();
    
    // Reset filters
    await page.getByRole('button', { name: /초기화|Reset/ }).click();
    
    // All scores should be visible again
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('썸머타임')).toBeVisible();
    await expect(page.getByText('이마진')).toBeVisible();
    await expect(page.getByText('녹턴 E플랫 장조')).toBeVisible();
  });

  test('filter state persistence', async ({ page }) => {
    await page.goto('/scores');
    
    // Apply filters
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    const genreSelect = page.locator('select[name="genre"], input[name="genre"]').first();
    await genreSelect.selectOption('클래식');
    
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Navigate away and back
    await page.getByRole('link', { name: /대시보드|Dashboard/ }).click();
    await page.getByRole('link', { name: /악보|Scores/ }).click();
    
    // Filters should be maintained
    await expect(page.getByText('월광 소나타')).toBeVisible();
    await expect(page.getByText('썸머타임')).not.toBeVisible();
  });

  test('no results state', async ({ page }) => {
    await page.goto('/scores');
    
    // Search for something that doesn't exist
    await page.getByPlaceholder('악보 검색...').fill('존재하지않는악보');
    await page.getByRole('button', { name: '검색' }).click();
    
    // Should show no results message
    await expect(page.getByText(/검색 결과가 없습니다|No results found/)).toBeVisible();
    await expect(page.getByText('월광 소나타')).not.toBeVisible();
  });

  test('sorting with filters', async ({ page }) => {
    await page.goto('/scores');
    
    // Apply genre filter
    await page.getByRole('button', { name: /고급 필터|Advanced Filters/ }).click();
    
    const genreSelect = page.locator('select[name="genre"], input[name="genre"]').first();
    await genreSelect.selectOption('클래식');
    
    await page.getByRole('button', { name: /적용|Apply/ }).click();
    
    // Change sorting
    const sortSelect = page.locator('select[name="sort"], select:has-text("정렬")').first();
    if (await sortSelect.isVisible()) {
      await sortSelect.selectOption('title'); // Sort by title
    }
    
    // Verify filtered and sorted results
    const scoreElements = page.locator('.score-card, .score-item');
    const count = await scoreElements.count();
    
    // Should show only classical scores
    expect(count).toBe(2); // Should have 2 classical scores
  });
});

// Helper function to upload score with metadata
async function uploadScoreWithMetadata(page: any, scoreData: any) {
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
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
196
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
  
  if (scoreData.genre) {
    const genreInput = page.getByPlaceholder('장르를 입력하세요');
    if (await genreInput.isVisible()) {
      await genreInput.fill(scoreData.genre);
    }
  }
  
  if (scoreData.difficulty) {
    const difficultySelect = page.locator('select[name="difficulty"]');
    if (await difficultySelect.isVisible()) {
      await difficultySelect.selectOption(scoreData.difficulty.toString());
    }
  }
  
  if (scoreData.tags && scoreData.tags.length > 0) {
    const tagsInput = page.getByPlaceholder('태그를 입력하세요');
    if (await tagsInput.isVisible()) {
      await tagsInput.fill(scoreData.tags.join(', '));
    }
  }

  // Submit upload
  await page.getByRole('button', { name: '업로드' }).click();

  // Wait for completion
  await expect(page.getByText('업로드가 완료되었습니다')).toBeVisible({ timeout: 30000 });
}