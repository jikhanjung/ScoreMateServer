# 관리자 페이지 기능 및 구조 설계안

## 1. 개요
ScoreMate 서비스의 안정적인 운영과 관리를 위해 사용자, 콘텐츠, 시스템 상태를 총괄적으로 제어할 수 있는 관리자 전용 페이지를 구축한다. 관리자 페이지는 일반 사용자 인터페이스와 분리된 별도의 경로(`/admin`)를 통해 접근한다.

## 2. 핵심 기능 정의

### 2.1. 대시보드
관리자 로그인 시 가장 먼저 보게 될 페이지로, 서비스의 핵심 지표를 시각적으로 보여준다.
- **주요 통계:**
  - 총 사용자 수, 신규 가입자 수 (일/주/월)
  - 총 악보 및 세트리스트 수
  - 총 저장 공간 사용량
- **시스템 상태:**
  - Celery 워커 상태 (실행 중인 작업, 대기 중인 작업, 실패한 작업 수)
  - 최근 발생한 시스템 오류 로그 요약

### 2.2. 사용자 관리
- **사용자 목록 조회:**
  - 모든 사용자를 페이지네이션된 목록으로 표시
  - 이메일, 이름, 가입일, 마지막 로그인 일시 등의 정보 제공
  - 검색 및 필터링 기능 (이메일, 이름, 권한 등)
- **사용자 상세 정보 및 제어:**
  - 특정 사용자 정보 조회 (작성한 악보, 세트리스트 목록 포함)
  - 사용자 권한 변경 (일반 사용자 <-> 관리자)
  - 사용자 계정 비활성화/활성화
  - 비밀번호 초기화 기능

### 2.3. 콘텐츠 관리
- **악보(Score) 관리:**
  - 시스템에 등록된 모든 악보 목록 조회
  - 소유자와 관계없이 모든 악보의 메타데이터(제목, 작곡가 등) 수정
  - 부적절하거나 문제가 있는 악보 삭제
- **세트리스트(Setlist) 관리:**
  - 시스템에 등록된 모든 세트리스트 목록 조회
  - 소유자와 관계없이 모든 세트리스트 정보 수정 및 삭제
- **주석(Annotation) 관리:**
  - 특정 악보에 달린 모든 주석 조회 및 삭제

### 2.4. 시스템 관리
- **백그라운드 작업(Celery) 모니터링:**
  - 현재 실행/대기/실패/완료된 작업들의 상세 목록 조회
  - 실패한 작업 재시도 또는 삭제
- **서버 로그 조회:**
  - 백엔드 서버의 실시간 로그 스트림 또는 파일 조회 기능

## 3. 페이지 구조 (Sitemap)
- `/admin` -> `/admin/dashboard`로 리디렉션
- **`/admin/dashboard`**: 대시보드
- **`/admin/users`**: 사용자 목록
  - **`/admin/users/:id`**: 특정 사용자 상세 정보
- **`/admin/scores`**: 전체 악보 목록
- **`/admin/setlists`**: 전체 세트리스트 목록
- **`/admin/system`**: 시스템 관리
  - **`/admin/system/tasks`**: 백그라운드 작업 모니터링
  - **`/admin/system/logs`**: 서버 로그 조회

## 4. 기술 구현 방안
- **백엔드:**
  - 관리자 전용 API 엔드포인트 신규 개발 (`/api/admin/...`)
  - 사용자 모델에 `is_staff` 또는 `role` 필드를 추가하여 관리자 권한 구분
  - 관리자 권한을 가진 사용자만 해당 API를 호출할 수 있도록 권한(Permission) 클래스 적용
- **프론트엔드:**
  - `/admin` 경로를 위한 별도의 레이아웃(Layout) 구성
  - 관리자 페이지 전용 UI 컴포넌트 개발
  - 관리자 권한이 있는 사용자인지 확인하여 네비게이션 메뉴에 '관리자 페이지' 링크 표시

## 5. 보완 사항 및 세부 설계
- **권한/인증 강화를 서버 중심으로 처리:**
  - 모든 `/api/admin/*` 엔드포인트에 DRF `IsAdminUser`(또는 동등 커스텀 Permission) 적용. 클라이언트 가드는 보조수단이며, 최종 권한 검증은 서버가 수행.
- **관리자 여부 노출:**
  - `UserProfileSerializer`에 `is_staff`(또는 `role`) 필드를 포함하여 프런트가 안전하게 관리자 여부를 판별할 수 있도록 함. 프런트의 `User` 타입에도 동일 필드 추가.
- **로그 화면 보안 가이드:**
  - 운영 로그의 원문 스트리밍/파일 노출은 최소화. 대안으로 DB 기반 `AccessLog`/에러 이벤트 요약 리스트 제공(검색/필터/페이지네이션).
  - 프로덕션은 중앙집중 로깅 스택(예: CloudWatch/ELK/Sentry) 링크로 대체.
- **태스크 재시도 정책:**
  - `tasks.Task` 기준 “재시도”는 새로운 Celery 태스크를 enqueue(원본 row는 상태 보존). 필요 시 `parent_task_id`/`retry_count`로 트래킹.
- **목록 성능/사용성:**
  - 모든 대용량 목록(Users/Scores/Setlists/Tasks)에 `django-filter` + 페이지네이션 적용, 대표 컬럼 인덱스 재점검.
- **감사 로깅:**
  - 관리자 행위(권한변경, 콘텐츠 수정/삭제)는 `AccessLog`에 관리자 ID/대상/행위/사유를 남김.

## 6. Admin API 스케치(초안)
- Users
  - `GET /api/admin/users?q=&is_active=&is_staff=`
  - `GET /api/admin/users/{id}`
  - `PATCH /api/admin/users/{id}`(예: `{"is_active": false, "is_staff": true}`)
  - `POST /api/admin/users/{id}/reset-password`
- Scores / Setlists
  - `GET /api/admin/scores?owner=&tag=&created_after=&ordering=`
  - `PATCH /api/admin/scores/{id}`
  - `DELETE /api/admin/scores/{id}`
  - 세트리스트도 동일 패턴(`/api/admin/setlists*`)
- Tasks
  - `GET /api/admin/tasks?status=&kind=&user=`
  - `POST /api/admin/tasks/{id}/retry`
  - `DELETE /api/admin/tasks/{id}`
- Access Logs
  - `GET /api/admin/access-logs?action=&user=&target_type=&from=&to=`

모든 엔드포인트는 `IsAdminUser` 적용, 페이지네이션/정렬/필터 지원.

## 7. 프런트 라우팅/가드 제안
- 라우트: `app/admin/layout.tsx`, `app/admin/dashboard/page.tsx`, `app/admin/users/page.tsx`, `app/admin/users/[id]/page.tsx`,
  `app/admin/scores/page.tsx`, `app/admin/setlists/page.tsx`, `app/admin/system/tasks/page.tsx`, `app/admin/system/logs/page.tsx`
- 가드: 네비게이션/레이아웃은 `user.is_staff`일 때만 노출. 라우트 접근 실패 시 403 처리 및 홈으로 유도.
- 테이블 UX: 공통 테이블(검색/정렬/페이지네이션), 위험 작업은 확인 모달, 실패 태스크 “재시도” 버튼 제공.

## 8. 테스트 전략(요약)
- 백엔드: 관리자 권한(200/403), 필터/정렬/페이지네이션, 태스크 재시도 사이드이펙트, 감사로그 기록 검증(pytest).
- 프런트: Playwright로 관리자 로그인→대시보드, 사용자 권한변경 플로우, 태스크 재시도, 비관리자 접근 403 확인.

## 9. 마일스톤
1) `is_staff` 노출 및 프런트 타입 반영
2) Admin Users API/화면(목록/상세/권한/활성화)
3) Admin Tasks API/화면(상태 필터/재시도)
4) Admin Scores/Setlists API/화면(검색/수정/삭제)
5) 대시보드 핵심 지표(사용자/콘텐츠/스토리지/태스크)
6) AccessLog 요약 뷰 + 감사기록 강화
7) 운영 로그 링크/보안 가이드 문서화
