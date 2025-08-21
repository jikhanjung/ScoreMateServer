# Phase 4 통합 구현 계획: 데이터 품질 강화 및 사용성 개선

**작성일**: 2025년 8월 21일  
**작성자**: Claude Code Assistant  
**상태**: 개발 착수  
**예상 기간**: 4주 (2025.08.21 - 2025.09.18)

## 📋 개요

Phase 4는 기존 Phase 3까지 구현된 핵심 기능들의 **완성도를 높이고 실용적 가치를 제공**하는 데 초점을 맞춥니다. 원래 계획의 기술적 고도화보다는 **사용자가 즉시 체감할 수 있는 개선**을 우선시합니다.

## 🎯 핵심 목표

1. **데이터 품질 향상**: 사용자가 직접 메타데이터를 관리할 수 있는 도구 제공
2. **대용량 처리 개선**: 수백 개 이상의 악보도 부드럽게 탐색 가능
3. **사용자 경험 완성**: Empty State, 로딩 상태 등 세부 UX 개선
4. **테스트 커버리지 확대**: 모든 신규 기능에 대한 철저한 테스트

## 📌 주요 구현 Task

### Task 1: 메타데이터 관리 기능 (1.5주)

#### 1.1 개별 악보 정보 편집 기능
**위치**: `/scores/[id]` (악보 상세 페이지)

**구현 사항**:
- 편집 모드 토글 버튼 추가
- 인라인 편집 가능한 필드:
  - 제목 (title)
  - 작곡가 (composer)
  - 장르 (genre)
  - 난이도 (difficulty)
  - 태그 (tags)
  - 설명 (description)
- **Optimistic Updates** 적용으로 즉각적인 UI 반영
- 유효성 검사 및 에러 처리
- 변경사항 저장/취소 기능

**기술 스택**:
```typescript
- react-hook-form for form management
- React Query mutation with optimistic updates
- Zod for validation
- API: PATCH /api/scores/{id}/
```

#### 1.2 일괄 메타데이터 편집 기능
**위치**: `/scores` (악보 목록 페이지)

**구현 사항**:
- Phase 3 벌크 액션 시스템 확장
- 일괄 편집 가능 작업:
  - 태그 추가/제거
  - 장르 일괄 변경
  - 난이도 일괄 설정
- 변경 미리보기 모달
- 일괄 작업 진행률 표시
- 작업 취소/롤백 기능

**UI 플로우**:
```
1. 악보 다중 선택 → 2. "편집" 버튼 → 3. 편집 모달 → 4. 변경사항 확인 → 5. 적용
```

### Task 2: 성능 최적화 - 무한 스크롤 (1주)

**위치**: `/scores`, `/setlists`

**구현 사항**:
- React Query `useInfiniteQuery` 도입
- 가상 스크롤링 (React Window) 검토
- 스크롤 위치 복원
- 로딩 인디케이터 및 스켈레톤 UI
- 에러 발생 시 재시도 버튼

**성능 목표**:
- 초기 로딩: 20개 항목
- 추가 로딩: 스크롤 80% 도달 시
- 최대 500개 항목까지 부드러운 스크롤

**코드 예시**:
```typescript
const {
  data,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage
} = useInfiniteQuery({
  queryKey: ['scores', filters],
  queryFn: ({ pageParam = 1 }) => scoreApi.getScores({ 
    page: pageParam, 
    ...filters 
  }),
  getNextPageParam: (lastPage) => lastPage.next_page
});
```

### Task 3: UI/UX 완성도 향상 (1.5주)

#### 3.1 Empty State 컴포넌트
**적용 위치**:
- 악보 목록이 비었을 때
- 검색 결과가 없을 때
- 세트리스트가 비었을 때
- 필터링 결과가 없을 때

**디자인 요소**:
- 상황별 일러스트레이션
- 명확한 안내 문구
- 행동 유도 버튼 (CTA)
- 도움말 링크

#### 3.2 로딩 및 에러 상태 개선
**구현 사항**:
- 전역 로딩 바 (NProgress 스타일)
- 컴포넌트별 스켈레톤 UI
- 에러 바운더리 구현
- 토스트 메시지 시스템 개선
- 네트워크 오류 시 자동 재시도

#### 3.3 키보드 접근성 개선
**구현 사항**:
- 모든 인터랙티브 요소에 tabindex 설정
- 키보드 단축키 구현:
  - `Ctrl+K`: 검색
  - `Ctrl+N`: 새 악보 업로드
  - `Esc`: 모달 닫기
  - `Space`: 선택/선택 해제
- ARIA 레이블 추가
- 포커스 트랩 구현 (모달)

## 🔧 기술적 구현 세부사항

### API 엔드포인트 확장
```typescript
// 개별 메타데이터 수정
PATCH /api/scores/{id}/
{
  title?: string,
  composer?: string,
  genre?: string,
  difficulty?: number,
  tags?: string[],
  description?: string
}

// 일괄 메타데이터 수정
POST /api/scores/bulk-update/
{
  score_ids: number[],
  updates: {
    add_tags?: string[],
    remove_tags?: string[],
    genre?: string,
    difficulty?: number
  }
}
```

### 상태 관리 전략
- **React Query**: 서버 상태 관리
- **Zustand**: 선택 상태, UI 상태 관리
- **Context API**: 테마, 사용자 설정

### 컴포넌트 구조
```
components/
├── metadata/
│   ├── MetadataEditForm.tsx
│   ├── BulkEditModal.tsx
│   └── MetadataField.tsx
├── ui/
│   ├── EmptyState.tsx
│   ├── InfiniteScroll.tsx
│   ├── SkeletonLoader.tsx
│   └── Toast.tsx
└── accessibility/
    ├── KeyboardShortcuts.tsx
    └── FocusTrap.tsx
```

## 📊 성공 지표

1. **기능적 지표**
   - [ ] 모든 메타데이터 필드 편집 가능
   - [ ] 100개 이상 항목에서 벌크 작업 성공
   - [ ] 500개 항목까지 무한 스크롤 동작
   - [ ] 모든 빈 상태에 Empty State 표시

2. **성능 지표**
   - [ ] 초기 로딩 시간 < 2초
   - [ ] 스크롤 FPS > 30
   - [ ] API 응답 시간 < 500ms

3. **품질 지표**
   - [ ] 테스트 커버리지 > 80%
   - [ ] Lighthouse 접근성 점수 > 90
   - [ ] 0 Critical 버그

## 📅 타임라인

| 주차 | 날짜 | Task | 산출물 |
|------|------|------|--------|
| 1주차 | 08.21-08.28 | Task 1.1 개별 편집 | 편집 폼, API 연동 |
| 2주차 | 08.29-09.04 | Task 1.2 일괄 편집 | 벌크 편집 모달, 테스트 |
| 3주차 | 09.05-09.11 | Task 2 무한 스크롤 | 성능 최적화, 테스트 |
| 4주차 | 09.12-09.18 | Task 3 UI/UX 완성 | Empty State, 접근성 |

## 🚀 즉시 시작할 작업

1. **Backend API 확인 및 수정**
   - PATCH 엔드포인트 지원 여부 확인
   - Bulk update 엔드포인트 구현 필요 여부 확인

2. **MetadataEditForm 컴포넌트 구현**
   - 악보 상세 페이지에 편집 모드 추가
   - react-hook-form 통합
   - Optimistic Updates 구현

3. **테스트 환경 준비**
   - 메타데이터 편집 E2E 테스트 시나리오 작성
   - Mock 데이터 준비

## 📝 참고사항

- Phase 3에서 구현한 기능들과의 일관성 유지
- 기존 디자인 시스템 준수
- 모바일 반응형 디자인 고려
- 브라우저 호환성 (Chrome, Firefox, Safari)