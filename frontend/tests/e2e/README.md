# E2E Tests for ScoreMate Frontend

This directory contains end-to-end tests for the ScoreMate application using Playwright.

## Test Structure

Tests are organized in logical execution order based on user journey and dependencies:

### 1️⃣ Foundation & Authentication (01-05)
- `01-landing-page.spec.ts` - Landing page functionality and responsiveness
- `02-auth-flow.spec.ts` - Authentication flow tests (registration, login, logout)
- `03-auth-integration.spec.ts` - Authentication integration tests
- `04-auth-context.spec.ts` - Authentication context and state management
- `05-navigation.spec.ts` - Navigation flows and routing

### 2️⃣ Dashboard & Core UI (06-07)
- `06-dashboard.spec.ts` - Dashboard functionality and widgets
- `07-dashboard-integration.spec.ts` - Dashboard integration with backend APIs

### 3️⃣ File Management (08-09)
- `08-file-upload-workflow.spec.ts` - File upload processes and validation
- `09-pdf-processing.spec.ts` - PDF processing, thumbnails, and metadata extraction

### 4️⃣ Setlist Management (10-11)
- `10-setlist-management.spec.ts` - Setlist CRUD operations
- `11-setlist-drag-drop.spec.ts` - Drag and drop functionality for setlists

### 5️⃣ Phase 3 Advanced Features (12-15)
- `12-phase3-advanced-filtering.spec.ts` - Advanced filtering and search functionality
- `13-phase3-bulk-actions.spec.ts` - Bulk operations on scores (tag management, deletion)
- `14-phase3-pdf-viewer.spec.ts` - PDF viewer features in score detail pages
- `15-phase3-settings-page.spec.ts` - User settings page functionality

### 6️⃣ Integration & Quality Assurance (16-17)
- `16-complete-workflow.spec.ts` - End-to-end user workflows
- `17-accessibility.spec.ts` - Accessibility compliance and keyboard navigation

## Running Tests

### Prerequisites
```bash
# Install Playwright browsers (required once)
npx playwright install
```

### Run All Tests
```bash
npm run test:e2e
```

### Run Specific Test Suite
```bash
# Run tests by category
npm run test:e2e -- tests/e2e/01-*.spec.ts    # Foundation & Auth
npm run test:e2e -- tests/e2e/06-*.spec.ts    # Dashboard tests
npm run test:e2e -- tests/e2e/12-*.spec.ts    # Phase 3 features
npm run test:e2e -- tests/e2e/1[2-5]-*.spec.ts # All Phase 3 tests

# Run specific test file
npm run test:e2e -- tests/e2e/01-landing-page.spec.ts

# Run tests in order (foundation first)
npm run test:e2e -- tests/e2e/0[1-5]-*.spec.ts # Foundation tests
npm run test:e2e -- tests/e2e/0[6-9]-*.spec.ts # Core functionality
npm run test:e2e -- tests/e2e/1[0-7]-*.spec.ts # Advanced features

# Run with different browser
npm run test:e2e -- --project=webkit
```

### Debug Mode
```bash
# Run tests in headed mode
npm run test:headed

# Run tests with UI
npm run test:ui

# Generate test report
npm run test:report
```

## Phase 3 Test Coverage

### Advanced Filtering (`phase3-advanced-filtering.spec.ts`)
- ✅ Basic search functionality (title, composer)
- ✅ Advanced filters toggle
- ✅ Genre filtering
- ✅ Difficulty range filtering
- ✅ Tag-based filtering
- ✅ Combined filters
- ✅ Filter reset functionality
- ✅ Filter state persistence
- ✅ No results handling
- ✅ Sorting with filters

### Bulk Actions (`phase3-bulk-actions.spec.ts`)
- ✅ Individual score selection
- ✅ Select all functionality
- ✅ Bulk tag addition
- ✅ Bulk tag removal
- ✅ Bulk delete operations
- ✅ View mode switching with selections
- ✅ Loading states during bulk operations
- ✅ Selection persistence
- ✅ Clear selection functionality
- ✅ Bulk actions with filtered results
- ✅ Error handling

### User Settings (`phase3-settings-page.spec.ts`)
- ✅ Navigation to settings page
- ✅ Tab navigation (Profile, Security, Storage, Subscription)
- ✅ Profile information display and updates
- ✅ Password change form and validation
- ✅ Storage usage display with real data
- ✅ Subscription information
- ✅ Responsive design
- ✅ Data loading states
- ✅ Error handling
- ✅ Keyboard accessibility
- ✅ Cross-tab data consistency

### PDF Viewer (`phase3-pdf-viewer.spec.ts`)
- ✅ Navigation to score detail page
- ✅ PDF viewer default display
- ✅ PDF toolbar functionality
- ✅ Download functionality with correct filenames
- ✅ Loading states
- ✅ Error handling and fallbacks
- ✅ Browser compatibility
- ✅ Score metadata display
- ✅ Quick actions availability
- ✅ Responsive layout
- ✅ Keyboard accessibility
- ✅ Performance testing
- ✅ Error recovery
- ✅ Multiple viewer instances

## Test Data Management

Each test suite uses unique user accounts to avoid conflicts:
- `filter-test-{timestamp}@example.com` - Advanced filtering tests
- `bulk-test-{timestamp}@example.com` - Bulk actions tests
- `settings-test-{timestamp}@example.com` - Settings page tests
- `pdf-viewer-test-{timestamp}@example.com` - PDF viewer tests

Tests automatically create test data (scores, setlists) as needed and clean up after themselves.

## Test Patterns

### User Registration Pattern
```typescript
const testUser = {
  email: `test-${Date.now()}@example.com`,
  name: 'Test User',
  password: 'testpassword123!'
};

await page.goto('/auth/register');
await page.getByPlaceholder('your@email.com').fill(testUser.email);
// ... rest of registration
```

### Score Upload Pattern
```typescript
const pdfContent = `%PDF-1.4...`; // Minimal valid PDF
const buffer = Buffer.from(pdfContent);

await fileInput.setInputFiles({
  name: 'test-score.pdf',
  mimeType: 'application/pdf',
  buffer: buffer
});
```

### Error Handling Pattern
```typescript
// Test offline behavior
await page.context().setOffline(true);
// ... perform action
// Verify graceful degradation

await page.context().setOffline(false);
// Verify recovery
```

## Continuous Integration

These tests are designed to run in CI/CD environments:
- All tests use headless browsers by default
- Unique user accounts prevent conflicts
- Comprehensive error handling
- Performance assertions included
- Accessibility compliance verification

## Troubleshooting

### Browser Installation Issues
```bash
npx playwright install chromium
```

### Test Timeouts
Increase timeout in `playwright.config.ts` if needed:
```typescript
timeout: 30000 // 30 seconds
```

### Flaky Tests
Tests include appropriate waits and retries for UI elements:
```typescript
await expect(element).toBeVisible({ timeout: 10000 });
```