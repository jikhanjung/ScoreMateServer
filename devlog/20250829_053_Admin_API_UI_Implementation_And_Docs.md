# 2025-08-29 — Admin API/UI 구현 및 문서 정리

## 개요
오늘은 관리자 기능 전반(백엔드 Admin API + 프런트 관리자 UI)을 구축하고, 저장소 가이드 문서들을 정비했다. 또한 운영 편의를 위해 관리자 링크/네비를 통합 UI에 맞춰 정리했다.

## 주요 변경 사항
- 문서/가이드
  - `AGENTS.md`: 저장소 가이드 신규 작성(프로젝트 구조, 명령어, 스타일, 테스트).
  - `CONTRIBUTING.md`: 기여 가이드 신설(브랜치/커밋/PR 체크리스트, 명령어).
  - `README.md`: 한국어로 전면 개선(개요/빠른 시작/명령어/구성).
  - `ARCHITECTURE.md`: 로컬 개발 명령어/디렉토리 구조 정합성 보완.
- 백엔드(Admin API)
  - 라우팅: `scoremateserver/urls.py`에 `api/v1/admin/` 추가.
  - 앱: `scoremate_admin` 시리얼라이저/뷰/URL 구성.
    - Users: 목록/상세/부분수정/비밀번호 초기화(`reset_password`).
    - Tasks: 목록/필터/검색/정렬, `retry` 액션(실제 Celery 재큐잉은 TODO).
    - Scores/Setlists: 목록/상세/부분수정/삭제.
  - 권한: 모든 엔드포인트 `IsAdminUser` 적용.
  - 프로필: `UserProfileSerializer`에 `is_staff` 노출(프런트 관리자 가드용).
- 프런트(관리자 UI)
  - 관리자 라우트: `/admin` 전역 레이아웃 + 대시보드/Users/Scores/Setlists/Tasks 페이지 스캐폴딩.
  - Admin API 클라이언트 추가(`adminApi`): Users/Tasks/Scores/Setlists CRUD/액션.
  - UI 통일: `ProtectedLayout` 적용, 버튼 컴포넌트(`Button`)로 액션 일관화.
  - 네비게이션: 
    - 상단 헤더에 `user.is_staff` 시 ‘관리자’ 링크 노출(`/admin/dashboard`).
    - 관리자 전용 탭바 `AdminNav` 추가.
  - 타입: `User` 타입에 `is_staff?: boolean` 반영.
  - 테스트: `tests/e2e/18-admin-nav.spec.ts` 추가(관리자 링크 노출/가드 검증).
- 운영
  - `admin@scoremate.com` 임시 비밀번호 초기화.
  - 일시적 토큰 만료/리로드 이슈 점검 및 컨테이너 재기동.

## 실행/테스트
- 전체 개발 환경: `npm run dev` (또는 `dev:detached`).
- 관리자 페이지 접근: 로그인 후 헤더 ‘관리자’ → `/admin/dashboard`.
- 테스트: `npm run test:frontend`(E2E), `npm run test:backend`(pytest).

## 남은 작업(TODO)
- Tasks `retry` 시 Celery 실제 재큐잉 연결.
- 관리자 테이블 정렬/로딩/에러 UX 보완, 공통 테이블 컴포넌트 적용.
- 관리자 접근/조작 E2E 시나리오 추가(Users 권한 토글, Tasks 재시도 등).
