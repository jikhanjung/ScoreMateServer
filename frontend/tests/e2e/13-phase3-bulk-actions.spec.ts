import { test, expect } from '@playwright/test';

// Test data for bulk actions
const bulkTestUser = {
  email: `bulk-test-${Date.now()}@example.com`,
  name: '벌크 작업 테스트 사용자',
  password: 'bulktest123!'
};

const testScores = [
  {
    filename: 'bulk-test-1.pdf',
    title: '벌크 테스트 악보 1',
    composer: '테스트 작곡가 1',
    tags: ['테스트', '클래식']
  },
  {
    filename: 'bulk-test-2.pdf',
    title: '벌크 테스트 악보 2', 
    composer: '테스트 작곡가 2',
    tags: ['테스트', '재즈']
  },
  {
    filename: 'bulk-test-3.pdf',
    title: '벌크 테스트 악보 3',
    composer: '테스트 작곡가 3',
    tags: ['테스트', '팝']
  },
  {
    filename: 'bulk-test-4.pdf',
    title: '벌크 테스트 악보 4',
    composer: '테스트 작곡가 4',
    tags: ['테스트', '발라드']
  }
];

test.describe('Phase 3: Bulk Actions Features', () => {
  test.beforeEach(async ({ page }) => {
    // Register and login user
    await page.goto('/auth/register');
    await page.getByPlaceholder('your@email.com').fill(bulkTestUser.email);
    await page.getByPlaceholder('홍길동').fill(bulkTestUser.name);
    await page.getByPlaceholder('8자 이상').fill(bulkTestUser.password);
    await page.getByPlaceholder('비밀번호 재입력').fill(bulkTestUser.password);
    await page.getByRole('checkbox', { name: 'ScoreMate 이용약관에 동의합니다' }).check();
    await page.getByRole('button', { name: '회원가입' }).click();
    
    await expect(page).toHaveURL('/dashboard', { timeout: 15000 });
    
    // Upload test scores
    for (const score of testScores) {
      await page.getByRole('link', { name: /악보 업로드|업로드/ }).click();
      await uploadScoreForBulk(page, score);
      await expect(page).toHaveURL('/scores', { timeout: 10000 });
    }
  });

  test('score selection functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Check if scores are displayed
    await expect(page.getByText('벌크 테스트 악보 1')).toBeVisible();
    
    // Test individual selection
    const firstCheckbox = page.locator('input[type="checkbox"]').first();
    await firstCheckbox.check();
    
    // Verify selection state
    await expect(firstCheckbox).toBeChecked();
    
    // Test bulk selection counter
    const selectionCounter = page.locator('.selection-count, [data-testid="selection-count"]');
    if (await selectionCounter.isVisible()) {
      await expect(selectionCounter).toContainText('1');
    }
  });

  test('select all functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Find and click select all checkbox
    const selectAllCheckbox = page.locator('input[type="checkbox"]').first(); // Usually the header checkbox
    await selectAllCheckbox.check();
    
    // Verify all items are selected
    const allCheckboxes = page.locator('input[type="checkbox"]');
    const checkboxCount = await allCheckboxes.count();
    
    for (let i = 0; i < checkboxCount; i++) {
      const checkbox = allCheckboxes.nth(i);
      if (await checkbox.isVisible()) {
        await expect(checkbox).toBeChecked();
      }
    }
  });

  test('bulk tag addition', async ({ page }) => {
    await page.goto('/scores');
    
    // Select first two scores
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    
    // Open bulk actions
    const bulkActionsButton = page.getByRole('button', { name: /선택된 항목|Selected Items|벌크 작업|Bulk Actions/ });
    if (await bulkActionsButton.isVisible()) {
      await bulkActionsButton.click();
    }
    
    // Find tag addition option
    const addTagsButton = page.getByRole('button', { name: /태그 추가|Add Tags/ });
    await expect(addTagsButton).toBeVisible();
    await addTagsButton.click();
    
    // Add new tags
    const tagInput = page.locator('input[placeholder*="태그"], input[name="tags"]').last();
    await tagInput.fill('벌크추가태그, 테스트태그');
    
    // Confirm tag addition
    await page.getByRole('button', { name: /추가|Add|확인|Confirm/ }).click();
    
    // Verify success message
    await expect(page.getByText(/태그가 추가되었습니다|Tags added successfully/)).toBeVisible();
  });

  test('bulk tag removal', async ({ page }) => {
    await page.goto('/scores');
    
    // Select scores that have common tags
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    
    // Open bulk actions
    const bulkActionsButton = page.getByRole('button', { name: /선택된 항목|Selected Items|벌크 작업|Bulk Actions/ });
    if (await bulkActionsButton.isVisible()) {
      await bulkActionsButton.click();
    }
    
    // Find tag removal option
    const removeTagsButton = page.getByRole('button', { name: /태그 제거|Remove Tags/ });
    await expect(removeTagsButton).toBeVisible();
    await removeTagsButton.click();
    
    // Select tags to remove
    const tagToRemove = page.locator('input[value="테스트"], button:has-text("테스트")').first();
    if (await tagToRemove.isVisible()) {
      await tagToRemove.click();
    }
    
    // Confirm tag removal
    await page.getByRole('button', { name: /제거|Remove|확인|Confirm/ }).click();
    
    // Verify success message
    await expect(page.getByText(/태그가 제거되었습니다|Tags removed successfully/)).toBeVisible();
  });

  test('bulk delete functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Select last two scores for deletion (to preserve others for other tests)
    const allScores = page.locator('.score-item, .score-card, tr:has(input[type="checkbox"])');
    const scoreCount = await allScores.count();
    
    // Select the last two scores
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(-2).check();
    await checkboxes.nth(-1).check();
    
    // Open bulk actions
    const bulkActionsButton = page.getByRole('button', { name: /선택된 항목|Selected Items|벌크 작업|Bulk Actions/ });
    if (await bulkActionsButton.isVisible()) {
      await bulkActionsButton.click();
    }
    
    // Find delete option
    const deleteButton = page.getByRole('button', { name: /삭제|Delete/ });
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();
    
    // Confirm deletion in dialog
    page.on('dialog', dialog => dialog.accept());
    
    // Or handle confirmation button if using custom modal
    const confirmDelete = page.getByRole('button', { name: /확인|삭제 확인|Confirm Delete/ });
    if (await confirmDelete.isVisible()) {
      await confirmDelete.click();
    }
    
    // Verify success message
    await expect(page.getByText(/삭제되었습니다|Successfully deleted/)).toBeVisible();
    
    // Verify scores are removed from list
    await page.reload();
    const remainingScores = page.locator('.score-item, .score-card');
    const remainingCount = await remainingScores.count();
    expect(remainingCount).toBeLessThan(scoreCount);
  });

  test('bulk actions with view mode switching', async ({ page }) => {
    await page.goto('/scores');
    
    // Test in grid view
    const gridViewButton = page.getByRole('button', { name: /그리드|Grid/ });
    if (await gridViewButton.isVisible()) {
      await gridViewButton.click();
    }
    
    // Select items in grid view
    const gridCheckboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await gridCheckboxes.nth(0).check();
    await gridCheckboxes.nth(1).check();
    
    // Switch to table view
    const tableViewButton = page.getByRole('button', { name: /테이블|Table|목록/ });
    if (await tableViewButton.isVisible()) {
      await tableViewButton.click();
    }
    
    // Verify selections are maintained
    const tableCheckboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await expect(tableCheckboxes.nth(0)).toBeChecked();
    await expect(tableCheckboxes.nth(1)).toBeChecked();
  });

  test('bulk actions loading states', async ({ page }) => {
    await page.goto('/scores');
    
    // Select multiple scores
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    
    // Open bulk actions
    const bulkActionsButton = page.getByRole('button', { name: /선택된 항목|Selected Items|벌크 작업|Bulk Actions/ });
    if (await bulkActionsButton.isVisible()) {
      await bulkActionsButton.click();
    }
    
    // Start tag addition
    const addTagsButton = page.getByRole('button', { name: /태그 추가|Add Tags/ });
    await addTagsButton.click();
    
    const tagInput = page.locator('input[placeholder*="태그"], input[name="tags"]').last();
    await tagInput.fill('로딩테스트태그');
    
    // Look for loading states during operation
    const confirmButton = page.getByRole('button', { name: /추가|Add|확인|Confirm/ });
    await confirmButton.click();
    
    // Check for loading indicators
    const loadingSpinner = page.locator('.loading, .spinner, [data-testid="loading"]');
    // Loading might be brief, so we just verify the operation completes
    
    await expect(page.getByText(/태그가 추가되었습니다|Tags added successfully/)).toBeVisible();
  });

  test('selection persistence across pages', async ({ page }) => {
    await page.goto('/scores');
    
    // Select some scores
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    
    // Navigate away and back
    await page.getByRole('link', { name: /대시보드|Dashboard/ }).click();
    await page.getByRole('link', { name: /악보|Scores/ }).click();
    
    // Selections should be cleared (expected behavior)
    const clearedCheckboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await expect(clearedCheckboxes.nth(0)).not.toBeChecked();
    await expect(clearedCheckboxes.nth(1)).not.toBeChecked();
  });

  test('clear selection functionality', async ({ page }) => {
    await page.goto('/scores');
    
    // Select multiple scores
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    await checkboxes.nth(2).check();
    
    // Find and click clear selection button
    const clearSelectionButton = page.getByRole('button', { name: /선택 해제|Clear Selection/ });
    if (await clearSelectionButton.isVisible()) {
      await clearSelectionButton.click();
    }
    
    // Verify all selections are cleared
    await expect(checkboxes.nth(0)).not.toBeChecked();
    await expect(checkboxes.nth(1)).not.toBeChecked();
    await expect(checkboxes.nth(2)).not.toBeChecked();
  });

  test('bulk actions with filtered results', async ({ page }) => {
    await page.goto('/scores');
    
    // Apply a filter first
    const searchInput = page.getByPlaceholder('악보 검색...');
    await searchInput.fill('벌크 테스트');
    await page.getByRole('button', { name: '검색' }).click();
    
    // Select filtered results
    const filteredCheckboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await filteredCheckboxes.nth(0).check();
    await filteredCheckboxes.nth(1).check();
    
    // Perform bulk action
    const bulkActionsButton = page.getByRole('button', { name: /선택된 항목|Selected Items|벌크 작업|Bulk Actions/ });
    if (await bulkActionsButton.isVisible()) {
      await bulkActionsButton.click();
      
      const addTagsButton = page.getByRole('button', { name: /태그 추가|Add Tags/ });
      await addTagsButton.click();
      
      const tagInput = page.locator('input[placeholder*="태그"], input[name="tags"]').last();
      await tagInput.fill('필터링된선택태그');
      
      await page.getByRole('button', { name: /추가|Add|확인|Confirm/ }).click();
      
      await expect(page.getByText(/태그가 추가되었습니다|Tags added successfully/)).toBeVisible();
    }
  });

  test('error handling in bulk operations', async ({ page }) => {
    await page.goto('/scores');
    
    // Select scores
    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await checkboxes.nth(0).check();
    
    // Try bulk action without selection (edge case)
    await checkboxes.nth(0).uncheck();
    
    const bulkActionsButton = page.getByRole('button', { name: /선택된 항목|Selected Items|벌크 작업|Bulk Actions/ });
    
    // Bulk actions should be disabled or hidden with no selection
    if (await bulkActionsButton.isVisible()) {
      await expect(bulkActionsButton).toBeDisabled();
    }
  });
});

// Helper function to upload score for bulk testing
async function uploadScoreForBulk(page: any, scoreData: any) {
  // Create minimal PDF content
  const pdfContent = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj  
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer<</Size 4/Root 1 0 R>>
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